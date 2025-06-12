from fastapi import APIRouter, HTTPException, Body, Depends, BackgroundTasks
from fastapi.concurrency import run_in_threadpool # Added for non-blocking execution
from typing import List, Optional, Union, Dict
import logging # For general logging
import uuid # For generating unique IDs if needed for some operations
import psycopg2
import psycopg2.extras # For dictionary cursor
import json # For serializing data to JSON for DB
import datetime

# Pydantic Models for request/response bodies
from aiservice.app.models.insight_generation_models import (
    RewriteContentInput, RewriteContentOutput,
    TitleGenerationRequest, TitleGenerationResponse,
    KeywordExtractionRequest, KeywordExtractionResponse
)
from aiservice.app.models.orchestration_models import ContentBlock, OrchestrationInput, OrchestrationOutput, OrchestrationStatusCodeEnum # Added OrchestrationStatusCodeEnum
from aiservice.app.models.pipeline_models import DocumentMetadata, RawImageInput # Added DocumentMetadata, RawImageInput
from aiservice.app.models.task_models import TaskStatus # Enum for task statuses

# LLM Configuration - This might be handled within the crew/agents now
# from aiservice.app.config.llm_config import get_configured_llm # Commented out as manager should handle LLM

# Crews
from aiservice.app.crews.content_rewrite_crew import ContentRewriteCrewManager # Changed import
from aiservice.app.crews.title_generation_crew import GeneralPurposeTitleGenerationCrew as TitleGenerationCrew
from aiservice.app.crews.keyword_extraction_crew import GeneralPurposeKeywordExtractionCrew

# Settings and Services for Orchestrator
from aiservice.app.config.settings import Settings, settings # To get DATABASE_URL
from aiservice.app.services.orchestrator import ParallelOrchestrator
from aiservice.app.services.routing_service import RoutingService
from aiservice.app.services.acquisition.web_service import WebAcquisitionService
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService
from aiservice.app.services.acquisition.file_service import FileAcquisitionService
from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService
from aiservice.app.config.logging_config import get_logger # Corrected local import
# TODO: Check if any of the above services require additional tool imports for their instantiation if not using DI

# --- Imports for DB Utils ---
from aiservice.app.services.task_db_service import (
    get_db_connection,
    update_task_status_processing,
    update_task_status_completed,
    update_task_status_failed,
    update_task_status_failed_background_error
)
# --- End Imports for DB Utils ---

router = APIRouter()

logger = get_logger(__name__) # Instantiate logger at module level

# --- Dependency Provider for Settings (Example, can be expanded for other services) ---
# This is a more robust way to handle dependencies like settings.
# For now, we will instantiate directly in the endpoint for simplicity,
# but this is a good pattern for future refactoring.
# async def get_settings() -> Settings:
# return Settings()

async def get_orchestrator() -> ParallelOrchestrator:
    settings = Settings()
    # Instantiate all services needed by ParallelOrchestrator
    # This assumes these services can be instantiated simply with settings or no args
    # This might need adjustment if services have more complex dependencies
    routing_s = RoutingService(settings=settings)
    web_acq_s = WebAcquisitionService(settings=settings)
    pdf_acq_s = PDFAcquisitionService(settings=settings) # Assuming PDF service init
    file_acq_s = FileAcquisitionService(settings=settings) # Assuming File service init
    img_proc_s = ImageProcessingService(settings=settings)
    content_struct_s = ContentStructuringService(settings=settings) # Assuming Content Structuring service init
    
    return ParallelOrchestrator(
        routing_service=routing_s,
        web_acquisition_service=web_acq_s,
        pdf_acquisition_service=pdf_acq_s,
        file_acquisition_service=file_acq_s,
        image_processing_service=img_proc_s,
        content_structuring_service=content_struct_s,
        settings=settings
    )


# --- AI Insight Generation Endpoints --- #

@router.post("/rewrite-content", response_model=RewriteContentOutput,
              summary="Rewrite/Summarize Content Blocks",
              description="Takes a list of content blocks and uses an AI crew to rewrite or summarize them.")
async def rewrite_content(payload: RewriteContentInput = Body(...)) -> RewriteContentOutput:
    """
    Endpoint to rewrite content using the ContentRewriteCrewManager.
    Performance Target for this "Rewrite Content" action: P99 latency under 30 seconds, average latency 10-15 seconds.
    """
    # The ContentRewriteCrewManager is expected to handle LLM configuration internally or via its agents.
    # llm = get_configured_llm()
    # if not llm:
    #     raise HTTPException(status_code=500, detail="LLM service not available or configured correctly.")

    manager = ContentRewriteCrewManager(rewrite_input=payload)
    
    try:
        # The manager.run() method is synchronous and potentially long-running.
        # Execute it in a thread pool to avoid blocking the FastAPI event loop.
        result: RewriteContentOutput = await run_in_threadpool(manager.run)
        
        # The manager's run method returns a RewriteContentOutput which includes status and error messages.
        # We can directly return this. If there are specific error statuses from the crew
        # that should translate to HTTP errors, that logic can be added here.
        # For example, if result.status_code indicates a specific type of failure:
        # if result.status_code == "error_some_specific_crew_failure":
        #     raise HTTPException(status_code=400, detail=result.error_message or "Crew processing failed")

        return result
        
    except Exception as e:
        # This catches unexpected errors during manager instantiation, run_in_threadpool, or if manager.run() itself raises an unhandled exception.
        print(f"Error during content rewrite endpoint: {e}") # Log the full error for debugging
        # import traceback
        # traceback.print_exc() # For more detailed logs if needed
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during content rewriting: {str(e)}")

@router.post("/generate-title", response_model=TitleGenerationResponse,
              summary="Generate AI-Suggested Title",
              description="Generates an AI-suggested title for the given content blocks.")
async def generate_title_endpoint(request_data: TitleGenerationRequest = Body(...)) -> TitleGenerationResponse:
    """
    Receives a list of content blocks and returns an AI-generated title.
    Processes the request using the GeneralPurposeTitleGenerationCrew.
    Endpoint aligns with V2.6 Plan - Iteration 1.2.
    """
    if not request_data.content_blocks:
        raise HTTPException(status_code=400, detail="No content blocks provided.")

    try:
        # Assuming user_id might be extracted from a JWT token or similar in a real app
        # For now, using a placeholder or deriving if possible. The crew itself has a default.
        # user_id_for_crew = "api_user" # Placeholder
        # title_crew = GeneralPurposeTitleGenerationCrew(user_id=user_id_for_crew)
        
        # Per Iteration 1.2, the crew takes content_blocks in its run method.
        # The crew constructor might take user_id if needed, but the run method is key for data.
        title_crew = TitleGenerationCrew() # Use default user_id from crew if not passed
        
        # Convert Pydantic models to dictionaries for the crew
        content_as_dicts = [block.model_dump(exclude_none=True) for block in request_data.content_blocks]

        # Run synchronous crew method in thread pool with corrected argument name
        title_generation_result: TitleGenerationOutput = await run_in_threadpool(
            title_crew.run, 
            content_block_dicts=content_as_dicts
        )

        # Access the suggested_title attribute from the result object
        final_suggested_title = title_generation_result.suggested_title

        if final_suggested_title.startswith("Error:"):
            # Log the error server-side as well
            print(f"Error from TitleGenerationCrew: {final_suggested_title}")
            # Return a more generic error to the client for now, or a specific one if appropriate
            raise HTTPException(status_code=500, detail=f"AI title generation failed: {final_suggested_title}")

        return TitleGenerationResponse(suggested_title=final_suggested_title)
    
    except HTTPException as http_exc: # Re-raise HTTPException
        raise http_exc
    except Exception as e:
        print(f"Error in /generate-title endpoint: {e}")
        # import traceback # For detailed logging
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during title generation: {str(e)}")

@router.post("/generate-keywords", response_model=KeywordExtractionResponse,
              summary="Generate AI-Suggested Keywords",
              description="Generates a list of AI-suggested keywords for the given content blocks.")
async def generate_keywords_endpoint(request_data: KeywordExtractionRequest = Body(...)) -> KeywordExtractionResponse:
    """
    Receives a list of content blocks and returns AI-generated keywords.
    Processes the request using the GeneralPurposeKeywordExtractionCrew.
    Endpoint aligns with V2.6 Plan - Iteration 1.3.
    """
    if not request_data.content_blocks:
        raise HTTPException(status_code=400, detail="No content blocks provided.")

    try:
        # Convert Pydantic models to dictionaries for the crew's constructor
        content_as_dicts = [block.model_dump(exclude_none=True) for block in request_data.content_blocks]

        # Instantiate the crew, passing content_blocks to its constructor
        keyword_crew = GeneralPurposeKeywordExtractionCrew(content_blocks=content_as_dicts)
        
        # Run synchronous crew method in thread pool; run() takes no arguments itself
        result: Union[List[str], str] = await run_in_threadpool(keyword_crew.run)
        
        if isinstance(result, str): # Indicates an error message was returned
            if result.startswith("Error:"):
                print(f"Error from KeywordExtractionCrew: {result}")
                raise HTTPException(status_code=500, detail=f"AI keyword generation failed: {result}")
            else:
                # Should ideally not happen if errors are prefixed, but handle unexpected string
                print(f"Unexpected string result from KeywordExtractionCrew: {result}")
                raise HTTPException(status_code=500, detail="AI keyword generation produced an unexpected string result.")
        
        # If it's not a string, it should be List[str]
        suggested_keywords_list = result

        return KeywordExtractionResponse(suggested_keywords=suggested_keywords_list)
    
    except HTTPException as http_exc: # Re-raise HTTPException
        raise http_exc
    except Exception as e:
        print(f"Error in /generate-keywords endpoint: {e}")
        # import traceback
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during keyword generation: {str(e)}")

# Remove the example hello_world endpoint if it's no longer needed
# @router.get("/hello")
# async def hello_world():
#     return {"message": "Hello from AI Service API"}

# Endpoint for Content Rewrite (Iteration 1.1)
# @router.post("/rewrite-content", response_model=RewriteContentOutput) # Define RewriteContentOutput model
# async def rewrite_content(payload: RewriteContentInput): # Define RewriteContentInput model
#     # Logic to call ContentRewriteCrew
#     pass

# Endpoint for Title Generation (Iteration 1.2)
# @router.post("/generate-title", response_model=GenerateTitleOutput)
# async def generate_title(payload: GenerateTitleInput):
#     # Logic to call GeneralPurposeTitleGenerationCrew
#     pass

# Endpoint for Keyword Generation (Iteration 1.3)
# @router.post("/generate-keywords", response_model=GenerateKeywordsOutput)
# async def generate_keywords(payload: GenerateKeywordsInput):
#     # Logic to call GeneralPurposeKeywordExtractionCrew
#     pass 

# --- Background Task for Content Rewrite (Refactored to use task_db_service) ---
async def process_rewrite_task_in_background(
    task_id: str,
    user_id: Optional[str],
    content_blocks_to_rewrite_dict: List[Dict],
    document_metadata_dict: Optional[Dict],
    correlation_id: Optional[str]
):
    logger.info("Background processing starting for rewrite task", extra={
        'task_id': task_id, 
        'user_id': user_id, 
        'correlation_id': correlation_id
    })
    db_conn = None
    try:
        db_conn = get_db_connection()
        if not db_conn:
            logger.error("Failed to get DB connection in background task", extra={'task_id': task_id, 'correlation_id': correlation_id})
            return

        update_task_status_processing(task_id, db_conn)
        logger.info("Updated task status to PROCESSING", extra={'task_id': task_id, 'correlation_id': correlation_id})

        rewrite_input_data = {
            "user_id": user_id,
            "content_blocks_to_rewrite": content_blocks_to_rewrite_dict,
            "document_metadata": document_metadata_dict,
            "correlation_id": correlation_id
        }
        try:
            current_rewrite_input = RewriteContentInput(**rewrite_input_data)
        except Exception as pydantic_exc:
            logger.error("Failed to reconstruct RewriteContentInput in background task", 
                         extra={'task_id': task_id, 'correlation_id': correlation_id, 'error': str(pydantic_exc), 'data': rewrite_input_data}, exc_info=True)
            update_task_status_failed_background_error(
                task_id, 
                f"Input data validation error: {str(pydantic_exc)}", 
                db_conn
            )
            return

        manager = ContentRewriteCrewManager(
            rewrite_input=current_rewrite_input, 
            task_id=task_id, 
            db_connection=db_conn,
            correlation_id=correlation_id
        )
        
        logger.info("ContentRewriteCrewManager instantiated, starting run()", extra={'task_id': task_id, 'correlation_id': correlation_id})
        result: RewriteContentOutput = await run_in_threadpool(manager.run)
        logger.info("ContentRewriteCrewManager run finished", extra={'task_id': task_id, 'correlation_id': correlation_id, 'status_code': result.status_code})

        if result.status_code == OrchestrationStatusCodeEnum.REWRITE_SUCCESS.value:
            logger.info("Rewrite successful. Storing results.", extra={'task_id': task_id, 'correlation_id': correlation_id})
            update_task_status_completed(
                task_id, 
                result.model_dump_json(),
                db_conn
            )
        else:
            error_message = result.error_message or "Rewrite failed with no specific error message."
            # The status code from the result is the most specific error we have.
            status_code_for_log = result.status_code or "unknown_failure_status"
            logger.error(f"Rewrite failed by manager: {error_message}", 
                         extra={'task_id': task_id, 'correlation_id': correlation_id, 'status_code': status_code_for_log, 'error_details': result.model_dump_json()})
            update_task_status_failed(task_id, error_message, db_conn)
        
        logger.info("Database updated with final status via db_service.", extra={'task_id': task_id, 'correlation_id': correlation_id})

    except Exception as e:
        logger.error(f"Unexpected error in background rewrite task: {str(e)}", extra={'task_id': task_id, 'correlation_id': correlation_id}, exc_info=True)
        if db_conn:
            try:
                update_task_status_failed_background_error(
                    task_id, 
                    f"Unexpected background processing error: {str(e)}", 
                    db_conn
                )
            except Exception as db_err:
                logger.error(f"Failed to update task status to FAILED after unexpected error: {str(db_err)}", extra={'task_id': task_id, 'correlation_id': correlation_id}, exc_info=True)
    finally:
        if db_conn:
            db_conn.close()
            logger.debug("DB connection closed in background task", extra={'task_id': task_id, 'correlation_id': correlation_id})
    
    logger.info("Background processing finished for rewrite task", extra={'task_id': task_id, 'correlation_id': correlation_id})


# --- New Asynchronous Task Submission Endpoint (Uses its own get_db_connection for initial insert) ---
@router.post("/submit-rewrite-task", 
              status_code=202, 
              response_model=dict, 
              summary="Submit a Content Rewrite Task Asynchronously",
              description="Accepts content for rewriting, creates a task, and processes it in the background.")
async def submit_rewrite_task(
    payload: RewriteContentInput, 
    background_tasks: BackgroundTasks
):
    db_task_id = str(uuid.uuid4()) 
    user_id_to_store = payload.user_id
    correlation_id_from_payload = payload.correlation_id

    logger.info("Submit rewrite task request received", extra={
        'generated_task_id': db_task_id, 
        'user_id': user_id_to_store, 
        'correlation_id': correlation_id_from_payload,
        'input_payload_preview': payload.model_dump_json(indent=2)[:200] + "..."
    })

    db_conn = None
    try:
        db_conn = get_db_connection()
        if not db_conn:
            logger.error("Failed to get DB connection for task submission", extra={'generated_task_id': db_task_id, 'correlation_id': correlation_id_from_payload})
            raise HTTPException(status_code=503, detail="Database connection unavailable. Please try again later.")

        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            input_data_json = payload.model_dump_json() 
            
            cur.execute(
                """INSERT INTO \"AITask\" (id, \"userId\", \"taskType\", status, \"inputData\", \"createdAt\", \"updatedAt\")
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (db_task_id, user_id_to_store, 'REWRITE_CONTENT', TaskStatus.PENDING.value, input_data_json, datetime.datetime.utcnow(), datetime.datetime.utcnow())
            )
            db_conn.commit()
            logger.info("New rewrite task created in DB with PENDING status", extra={'task_id': db_task_id, 'correlation_id': correlation_id_from_payload})

        background_tasks.add_task(
            process_rewrite_task_in_background, 
            task_id=db_task_id,
            user_id=user_id_to_store,
            content_blocks_to_rewrite_dict=[block.model_dump() for block in payload.content_blocks_to_rewrite],
            document_metadata_dict=payload.document_metadata.model_dump() if payload.document_metadata else None,
            correlation_id=correlation_id_from_payload
        )
        logger.info("Rewrite task added to background processing queue", extra={'task_id': db_task_id, 'correlation_id': correlation_id_from_payload})
        
        return {"task_id": db_task_id, "message": "Rewrite task accepted and is being processed."}

    except psycopg2.Error as db_err:
        logger.error(f"Database error during task submission: {str(db_err)}", extra={'generated_task_id': db_task_id, 'correlation_id': correlation_id_from_payload}, exc_info=True)
        if db_conn: db_conn.rollback() 
        raise HTTPException(status_code=500, detail=f"Database error during task submission: {str(db_err)}")
    except Exception as e:
        logger.error(f"Unexpected error during task submission: {str(e)}", extra={'generated_task_id': db_task_id, 'correlation_id': correlation_id_from_payload}, exc_info=True)
        if db_conn: db_conn.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        if db_conn:
            db_conn.close()
            logger.debug("DB connection closed after task submission attempt", extra={'generated_task_id': db_task_id, 'correlation_id': correlation_id_from_payload})


# Ensure this new endpoint is registered with the main FastAPI app
# This is usually done by including this router in aiservice/main.py
# e.g., app.include_router(endpoints_router, prefix="/api/v1/ai", tags=["AI Endpoints"])
# The path for this new endpoint will be /api/v1/ai/api/v1/ai/submit-rewrite-task if the prefix is /api/v1/ai for the router
# Or, if the main app includes this router at / , then the path would be /api/v1/ai/submit-rewrite-task
# Let's adjust the endpoint path to be relative to the router's prefix.
# The router prefix is typically defined in main.py when including the router.
# Assuming the router is mounted at /api/v1/ai, then the endpoint path should be /submit-rewrite-task

# Corrected path for the new endpoint, assuming router is mounted at /api/v1/ai
# @router.post("/submit-rewrite-task", ...)
# The previous @router.post("/api/v1/ai/submit-rewrite-task" was likely too specific if the router has a prefix.
# Let's remove the /api/v1/ai part from the decorator path as it will be handled by the main app's router inclusion.
# (Correcting the endpoint path in the edit block if it's wrong there) 