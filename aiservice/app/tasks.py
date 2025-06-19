import logging
import psycopg2.pool
from .worker_setup import app
from aiservice.app.config.settings import Settings
from aiservice.app.services.orchestrator import ParallelOrchestrator
from aiservice.app.services.routing_service import RoutingService
from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService
from aiservice.app.models.orchestration_models import OrchestrationInput
from aiservice.app.services.task_db_service import TaskDBService
from aiservice.app.crews.title_generation_crew import GeneralPurposeTitleGenerationCrew as TitleGenerationCrew
from aiservice.app.models.task_models import TaskPayload
import psycopg2.extras
import json
import asyncio
from aiservice.app.models.task_models import TaskStatus
import os

logger = logging.getLogger(__name__)

# --- Worker-Global State ---
# Each Celery worker process will have its own instance of these globals.
# This prevents creating new connection pools for every single task.
_worker_db_pool = None
_task_db_service = None

def get_worker_db_pool():
    """Initializes and returns a singleton DB pool for the worker process."""
    global _worker_db_pool
    if _worker_db_pool is None:
        settings = Settings()
        _worker_db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=settings.db_pool_min_size,
            maxconn=settings.db_pool_max_size,
            dsn=settings.database_url,
        )
        logger.info(f"Celery worker (PID: {os.getpid()}) created a new DB connection pool.")
    return _worker_db_pool

def get_task_db_service_for_worker():
    """Initializes and returns a singleton TaskDBService for the worker process."""
    global _task_db_service
    if _task_db_service is None:
        pool = get_worker_db_pool()
        _task_db_service = TaskDBService(db_pool=pool)
    return _task_db_service

def _initialize_services():
    """Initializes and returns all necessary services for a task."""
    settings = Settings()
    task_db_service = get_task_db_service_for_worker()
    routing_s = RoutingService(settings=settings)
    img_proc_s = ImageProcessingService(settings=settings)
    content_struct_s = ContentStructuringService(settings=settings)
    orchestrator_instance = ParallelOrchestrator(
        task_db_service=task_db_service,
        routing_service=routing_s,
        image_processing_service=img_proc_s,
        content_structuring_service=content_struct_s,
        settings=settings
    )
    return task_db_service, orchestrator_instance

def get_orchestrator_instance() -> ParallelOrchestrator:
    """
    Creates and returns a new instance of the orchestrator, reusing worker-level services.
    """
    settings = Settings()
    task_db_service = get_task_db_service_for_worker()
    routing_s = RoutingService(settings=settings)
    img_proc_s = ImageProcessingService(settings=settings)
    content_struct_s = ContentStructuringService(settings=settings)
    
    orchestrator = ParallelOrchestrator(
        task_db_service=task_db_service,
        routing_service=routing_s,
        image_processing_service=img_proc_s,
        content_structuring_service=content_struct_s,
        settings=settings
    )
    return orchestrator

@app.task(bind=True)
def process_reconstruction_task(self, task_payload_dict: dict):
    """
    Celery task to process a reconstruction request.
    It reconstructs content from a URL or text and stores it.
    """
    orchestrator = get_orchestrator_instance()
    
    # The authoritative task ID comes from the Celery context
    task_id = self.request.id
    
    # The main payload from the API is nested inside the 'payload' key of the task data
    main_payload = task_payload_dict.get('payload', {})
    
    # Extract other necessary info from the original payload
    user_id = task_payload_dict.get('user_id')
    source_identifier = main_payload.get('sourceUrl') or main_payload.get('url') or main_payload.get('text')
    source_type = 'url' if main_payload.get('sourceUrl') or main_payload.get('url') else 'text'
    
    # Extract run flags for synchronous AI services
    run_title_generation = main_payload.get('run_title_generation', False)
    run_keyword_extraction = main_payload.get('run_keyword_extraction', False)

    # Extract the save_to_db flag, defaulting to True if not present
    save_to_db = main_payload.get('save_to_db', True)
    
    logger.info(f"Starting reconstruction task for task_id: {task_id}")

    try:
        # Update the payload with the correct task ID before creating the input object
        task_payload_dict['job_id'] = task_id
        
        orchestrator_input = OrchestrationInput(
            job_id=task_id,
            user_id=user_id,
            source_type=source_type,
            source_identifier=source_identifier,
            run_title_generation=run_title_generation,
            run_keyword_extraction=run_keyword_extraction,
            save_to_db=save_to_db
        )
        
        # Now, you can call the orchestrator with the prepared input
        result_service = asyncio.run(orchestrator.process(orchestrator_input))
        
        if not result_service.is_success() or not result_service.data:
            raise Exception(f"Orchestration pipeline failed: {result_service.error_message}")

        # The data is our OrchestrationOutput model
        orchestration_output = result_service.data

        logger.info(f"Task {task_id} completed successfully. Returning structured content.")
        
        # We return the full OrchestrationOutput, which will be serialized by Celery.
        # This ensures the result in the Celery backend matches the one in our DB.
        final_output_dict = json.loads(orchestration_output.model_dump_json())
        logger.info(f"Final task output for {task_id}: {json.dumps(final_output_dict, indent=2)}")
        return final_output_dict

    except Exception as e:
        logger.error(f"An unexpected error occurred in task {task_id}: {e}", exc_info=True)
        # Use the task's DB service to mark failure
        task_db_service = orchestrator.task_db_service
        conn = None
        try:
            conn = task_db_service.get_connection()
            task_db_service.update_task_status_failed(task_id, str(e), conn)
            conn.commit()
        finally:
            if conn:
                task_db_service.release_connection(conn)
        
        # Propagate the exception to let Celery know the task failed
        raise

@app.task(bind=True)
def generate_title_task(self, task_payload_dict: dict):
    """
    Celery task to generate a title for a given document's content.
    """
    task_db_service = get_task_db_service_for_worker()
    orchestrator = get_orchestrator_instance()
    
    task_id = self.request.id
    if not task_id:
        logger.error("Could not find task_id in request context.")
        # If there's no task_id, we can't update the status, so we just log and exit.
        return

    main_payload = task_payload_dict.get('payload', {})
    content_blocks = main_payload.get('content_blocks')

    logger.info(f"Starting title generation task for task_id: {task_id}")

    if not content_blocks:
        logger.error(f"Task {task_id} failed: No 'content_blocks' found in payload.")
        # We must use a connection to update the status to FAILED
        conn = None
        try:
            conn = task_db_service.get_connection()
            task_db_service.update_task_status_failed(task_id, "Payload missing 'content_blocks'.", conn)
            conn.commit()
        except Exception as db_e:
            logger.error(f"DB Error while failing task {task_id}: {db_e}", exc_info=True)
            if conn: conn.rollback()
        finally:
            if conn: task_db_service.release_connection(conn)
        return

    conn = None
    try:
        conn = task_db_service.get_connection()
        task_db_service.update_task_progress_stage(task_id, "Starting AI Title Generation", conn)
        conn.commit() # Commit progress update

        task_result = asyncio.run(
            orchestrator._run_title_generation_pipeline(
                content_blocks_data=content_blocks,
                job_id=task_id
            )
        )
        
        if task_result.status == TaskStatus.COMPLETED and task_result.result:
            generated_title = task_result.result.get("title")
            # On success, update the task with the final result
            task_db_service.update_task_with_title_result(task_id, generated_title, conn)
            conn.commit()
            logger.info(f"Task {task_id} (title generation) completed successfully.")
            return {"status": "success", "result": {"title": generated_title}}
        else:
            # If the pipeline returned a FAILED status, log it and update the DB
            error_message = task_result.message or "Title generation failed with no specific message."
            logger.error(f"Title generation pipeline failed for task {task_id}: {error_message}")
            task_db_service.update_task_status_failed(task_id, error_message, conn)
            conn.commit()
            return {"status": "failed", "error": error_message}

    except Exception as e:
        logger.error(f"An unexpected error occurred in title generation task {task_id}: {e}", exc_info=True)
        if conn:
            conn.rollback() # Rollback any partial changes from the try block
        # Use a fresh connection for final error reporting
        error_conn = None
        try:
            error_conn = task_db_service.get_connection()
            task_db_service.update_task_status_failed(task_id, str(e), error_conn)
            error_conn.commit()
        except Exception as db_e:
            logger.error(f"DB Error while failing task {task_id} on exception: {db_e}", exc_info=True)
            if error_conn: error_conn.rollback()
        finally:
            if error_conn:
                task_db_service.release_connection(error_conn)
        raise # Re-raise the original exception for Celery to mark as failed

@app.task(bind=True)
def generate_keywords_task(self, task_payload_dict: dict):
    """
    Celery task to generate keywords for a given document's content.
    """
    task_db_service = get_task_db_service_for_worker()
    orchestrator = get_orchestrator_instance()
    
    task_id = self.request.id
    if not task_id:
        logger.error("Could not find task_id in request context.")
        return

    main_payload = task_payload_dict.get('payload', {})
    content_blocks = main_payload.get('content_blocks')

    logger.info(f"Starting keyword generation task for task_id: {task_id}")

    if not content_blocks:
        logger.error(f"Task {task_id} failed: No 'content_blocks' found in payload.")
        conn = None
        try:
            conn = task_db_service.get_connection()
            task_db_service.update_task_status_failed(task_id, "Payload missing 'content_blocks'.", conn)
            conn.commit()
        except Exception as db_e:
            logger.error(f"DB Error while failing task {task_id}: {db_e}", exc_info=True)
            if conn: conn.rollback()
        finally:
            if conn: task_db_service.release_connection(conn)
        return

    conn = None
    try:
        conn = task_db_service.get_connection()
        task_db_service.update_task_progress_stage(task_id, "Starting AI Keyword Generation", conn)
        conn.commit()

        task_result = asyncio.run(
            orchestrator._run_keyword_extraction_pipeline(
                content_blocks_data=content_blocks,
                job_id=task_id
            )
        )
        
        if task_result.status == TaskStatus.COMPLETED and task_result.result:
            # THIS IS THE CRITICAL FIX: The pipeline now returns 'keywords'
            # and the DB service expects 'generated_keywords'. We must align them.
            # The most robust fix is to ensure the DB service receives what it expects.
            final_keywords = task_result.result.get("keywords")
            
            # Call the correct database update function
            task_db_service.update_task_with_keywords_result(task_id, final_keywords, conn)
            conn.commit()
            
            logger.info(f"Task {task_id} (keyword generation) completed successfully.")
            
            # The return value for Celery's own backend result store.
            # This should also be consistent for debugging purposes.
            return {"status": "success", "result": {"generated_keywords": final_keywords}}
        else:
            error_message = task_result.message or "Keyword generation failed with no specific message."
            logger.error(f"Keyword generation pipeline failed for task {task_id}: {error_message}")
            task_db_service.update_task_status_failed(task_id, error_message, conn)
            conn.commit()
            return {"status": "failed", "error": error_message}

    except Exception as e:
        logger.error(f"An unexpected error occurred in keyword generation task {task_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        error_conn = None
        try:
            error_conn = task_db_service.get_connection()
            task_db_service.update_task_status_failed(task_id, str(e), error_conn)
            error_conn.commit()
        except Exception as db_e:
            logger.error(f"DB Error while failing task {task_id} on exception: {db_e}", exc_info=True)
            if error_conn: error_conn.rollback()
        finally:
            if error_conn:
                task_db_service.release_connection(error_conn)
        raise

@app.task(bind=True)
def process_rewrite_task(self, task_payload_dict: dict):
    """
    Celery task to process a content rewrite request asynchronously.
    """
    task_db_service = get_task_db_service_for_worker()
    orchestrator = get_orchestrator_instance()
    
    task_id = task_payload_dict.get('task_id')
    user_id = task_payload_dict.get('user_id')
    # The content to be rewritten is expected in the 'payload'
    main_payload = task_payload_dict.get('payload', {})
    original_content_blocks = main_payload.get('content_blocks')

    logger.info(f"Starting content rewrite task for task_id: {task_id}")

    if not original_content_blocks:
        logger.error(f"Task {task_id} failed: No 'content_blocks' found in payload.")
        task_db_service.update_task_status_failed(task_id, "Payload missing 'content_blocks'.")
        # Do not raise an exception, as this is a data error, not a processing failure.
        # Let the task succeed from Celery's perspective.
        return

    conn = None
    try:
        conn = task_db_service.get_connection()
        task_db_service.update_task_progress_stage(task_id, "Starting AI Content Rewrite", conn)
        
        # Run the dedicated rewrite pipeline
        rewritten_blocks = asyncio.run(
            orchestrator._run_content_rewrite_pipeline(
                content_blocks=original_content_blocks,
                job_id=task_id,
                conn=conn
            )
        )
        
        # On success, update the task with the final result
        task_db_service.update_task_with_rewrite_result(task_id, rewritten_blocks, conn)
        conn.commit()
        
        logger.info(f"Task {task_id} (rewrite) completed successfully.")
        return {"status": "success", "rewritten_content_blocks": rewritten_blocks}

    except Exception as e:
        logger.error(f"An unexpected error occurred in rewrite task {task_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        # Use a fresh connection for final error reporting if the original one is bad
        error_conn = None
        try:
            error_conn = task_db_service.get_connection()
            task_db_service.update_task_status_failed(task_id, str(e), error_conn)
            error_conn.commit()
        finally:
            if error_conn:
                task_db_service.release_connection(error_conn)
        raise
    finally:
        if conn:
            task_db_service.release_connection(conn) 