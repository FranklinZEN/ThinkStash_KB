import logging
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
import psycopg2
import psycopg2.extras
import json
import asyncio

logger = logging.getLogger(__name__)

# It's crucial to initialize services within the task function for process safety.
# This ensures that each Celery worker process has its own service instances
# and database connection pools, avoiding shared state issues.

def _initialize_services():
    """Initializes and returns all necessary services for a task."""
    settings = Settings()
    task_db_service = TaskDBService(min_conn=settings.db_pool_min_size, max_conn=settings.db_pool_max_size)
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
    """Creates and returns a new instance of the orchestrator and its dependencies."""
    settings = Settings()
    task_db_service = TaskDBService(min_conn=settings.db_pool_min_size, max_conn=settings.db_pool_max_size)
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
    
    # The main payload from the API is nested inside the 'payload' key of the task data
    main_payload = task_payload_dict.get('payload', {})
    
    # Extract necessary info
    task_id = task_payload_dict.get('task_id')
    user_id = task_payload_dict.get('user_id')
    source_identifier = main_payload.get('url') # Correctly get URL from nested payload
    source_type = 'url' if source_identifier else 'text' # Determine source type
    
    logger.info(f"Starting reconstruction task for task_id: {task_id}")

    try:
        # Construct OrchestrationInput using the unpacked main_payload
        # This allows flags like 'run_title_generation' to be passed through
        orchestrator_input = OrchestrationInput(
            source_identifier=source_identifier,
            source_type=source_type,
            user_id=user_id,
            job_id=task_id,
            **main_payload  # Unpack the rest of the payload here
        )
        
        # Since orchestrator.process is async, we need to run it in an event loop
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
def generate_title_task(self, task_id: str):
    """
    Celery task to generate a title for a given document/card.
    (Implementation to follow)
    """
    logger.info(f"Received title generation task for: {task_id}")
    # TODO: Implement title generation logic
    # 1. Fetch card content from DB using task_id (which might be the card_id)
    # 2. Instantiate and run the TitleGenerationCrew
    # 3. Update the card with the new title
    return {"status": "success", "message": f"Title generation for {task_id} completed."}

@app.task(bind=True)
def process_rewrite_task(self, task_payload_dict: dict):
    """
    Celery task to process a content rewrite request asynchronously.
    """
    task_db_service, orchestrator = _initialize_services()
    
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