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
from aiservice.app.models.orchestration_models import ContentBlock, OrchestrationInput, OrchestrationOutput # Added OrchestrationInput, OrchestrationOutput
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

@router.post("/reconstruct-and-analyze", response_model=OrchestrationOutput,
              summary="Reconstruct and Analyze Content",
              description="Takes a source (URL or file_id) and uses the ParallelOrchestrator to reconstruct and analyze content.")
async def reconstruct_and_analyze_content(
    payload: OrchestrationInput = Body(...),
    orchestrator: ParallelOrchestrator = Depends(get_orchestrator) # Use dependency injection
) -> OrchestrationOutput:
    """
    Endpoint to reconstruct and analyze content using the ParallelOrchestrator.
    This service is responsible for the full pipeline: routing, acquisition, processing, structuring.
    """
    try:
        # The orchestrator.process method returns a ServiceResult
        orchestrator_result = await orchestrator.process(payload)
        
        if orchestrator_result.is_success() and orchestrator_result.data:
            return orchestrator_result.data # OrchestrationOutput
        else:
            # Log the error for server-side diagnosis
            print(f"Orchestration failed: {orchestrator_result.error_message}")
            print(f"Error details: {orchestrator_result.error_details}")
            
            # Try to return the OrchestrationOutput even on failure, if it's in error_details
            if isinstance(orchestrator_result.error_details, dict):
                try:
                    # Attempt to parse the error_details as OrchestrationOutput if it contains one
                    # This is common if _prepare_final_output was called before failure
                    failed_output = OrchestrationOutput(**orchestrator_result.error_details)
                    # Determine an appropriate HTTP status code based on the failure
                    # For simplicity, using 500 for now, but could be more specific (e.g., 400 for bad input if status indicates)
                    # We need to decide how to map OrchestrationOutput.status_code to HTTP status codes
                    http_status_code = 500 
                    if failed_output.status_code == "failure_routing" or failed_output.status_code == "failure_acquisition":
                        http_status_code = 400 # Example: Bad request if routing/acquisition fails due to input
                    elif failed_output.status_code == "unsupported_type":
                         http_status_code = 415 # Unsupported Media Type

                    # To return the OrchestrationOutput model as the body of an HTTPException,
                    # we need to make sure it's serializable or manually construct the detail.
                    # For now, returning the error message.
                    raise HTTPException(
                        status_code=http_status_code, 
                        detail=failed_output.error_message or "Orchestration process failed."
                    )
                except Exception as e_parse:
                    print(f"Could not parse error_details into OrchestrationOutput: {e_parse}")
                    # Fallback if error_details is not a valid OrchestrationOutput
                    raise HTTPException(
                        status_code=500, 
                        detail=orchestrator_result.error_message or "Orchestration process failed and error details were not parsable as OrchestrationOutput."
                    )
            else: # If error_details is not a dict or not present
                 raise HTTPException(
                    status_code=500, 
                    detail=orchestrator_result.error_message or "Orchestration process failed."
                )

    except HTTPException as http_exc: # Re-raise HTTPExceptions directly
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected error during content reconstruction: {e}")
        # import traceback
        # traceback.print_exc() # For more detailed logs
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during content reconstruction: {str(e)}")

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
    document_metadata_dict: Optional[Dict]
):
    logger = get_logger(__name__)
    logger.info(f"[Task {task_id}] Background processing started.")
    conn = None
    try:
        conn = get_db_connection() # Now from task_db_service
        
        update_task_status_processing(task_id, conn)
        logger.info(f"[Task {task_id}] Status updated to PROCESSING via db_service.") # Updated log message

        # Reconstruct RewriteContentInput for the manager
        from aiservice.app.models.insight_generation_models import RewriteContentInput
        from aiservice.app.models.orchestration_models import ContentBlock 
        from aiservice.app.models.pipeline_models import DocumentMetadata 

        parsed_content_blocks = []
        if content_blocks_to_rewrite_dict:
            for block_dict in content_blocks_to_rewrite_dict:
                parsed_content_blocks.append(ContentBlock(**block_dict))
        
        parsed_doc_metadata = None
        if document_metadata_dict:
            parsed_doc_metadata = DocumentMetadata(**document_metadata_dict)
        
        actual_rewrite_input = RewriteContentInput(
            content_blocks_to_rewrite=parsed_content_blocks,
            document_metadata=parsed_doc_metadata,
            user_id=user_id,
            original_content_blocks_json_string=None 
        )
        
        # Pass task_id and conn to the manager for progress updates
        manager = ContentRewriteCrewManager(
            rewrite_input=actual_rewrite_input,
            task_id=task_id,
            db_connection=conn
        )
        output: RewriteContentOutput = manager.run()

        logger.info(f"[Task {task_id}] Rewrite processing completed by manager.")

        if output.error_message:
            logger.error(f"[Task {task_id}] Rewrite failed: {output.error_message}")
            update_task_status_failed(task_id, output.error_message, conn)
        else:
            logger.info(f"[Task {task_id}] Rewrite successful. Storing results.")
            result_payload_for_db = {
                "ai_rewritten_content_blocks": [block.model_dump() for block in output.ai_rewritten_content_blocks],
                "usage_metrics": output.usage_metrics,
                "processing_time_ms": output.processing_time_ms,
                "trace_id": output.trace_id
            }
            update_task_status_completed(task_id, result_payload_for_db, conn)
        
        logger.info(f"[Task {task_id}] Database updated with final status via db_service.") # Updated log message

    except Exception as e:
        logger.error(f"[Task {task_id}] Error in background task: {e}", exc_info=True)
        if conn: # conn might be None if get_db_connection() failed
            try:
                error_msg_for_db = f"Background processing error: {str(e)}"
                update_task_status_failed_background_error(task_id, error_msg_for_db, conn)
            except Exception as db_service_err:
                logger.error(f"[Task {task_id}] CRITICAL: Failed to update task status to FAILED via db_service after background error: {db_service_err}", exc_info=True)
    finally:
        if conn:
            conn.close()
        logger.info(f"[Task {task_id}] Background processing finished.")


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
    logger = get_logger(__name__)
    task_id = str(uuid.uuid4())
    conn = None
    # For the initial insert, we'll still use a local connection logic or could also use get_db_connection from service
    # Let's switch this to use the shared get_db_connection as well for consistency
    
    logger.info(f"Received submission for rewrite task. Assigning task_id: {task_id}")

    try:
        conn = get_db_connection() # Use the one from task_db_service
        
        input_data_dict = {
            "original_content_blocks": [block.model_dump(exclude_none=True) for block in payload.content_blocks_to_rewrite],
            "document_metadata": payload.document_metadata.model_dump(exclude_none=True) if payload.document_metadata else None
        }
        input_data_json = json.dumps(input_data_dict)
        current_time = datetime.datetime.utcnow()

        # This part remains a direct DB call, as it's an INSERT not an UPDATE handled by current db_utils
        # Could be refactored into a create_ai_task in db_utils later if desired.
        with conn.cursor() as cur:
            sql = '''
            INSERT INTO "AITask" (id, "userId", "taskType", status, "inputData", "createdAt", "updatedAt")
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            '''
            cur.execute(sql, (
                task_id, 
                payload.user_id, 
                "CONTENT_REWRITE", 
                TaskStatus.PENDING.value, 
                input_data_json, 
                current_time, 
                current_time
            ))
            conn.commit()
        logger.info(f"[Task {task_id}] Successfully created in DB with status PENDING.")

        background_tasks.add_task(
            process_rewrite_task_in_background, 
            task_id,
            payload.user_id,
            [block.model_dump(exclude_none=True) for block in payload.content_blocks_to_rewrite],
            payload.document_metadata.model_dump(exclude_none=True) if payload.document_metadata else None
        )
        logger.info(f"[Task {task_id}] Queued for background processing.")
        
        return {"task_id": task_id}

    except Exception as e: # Catches errors from get_db_connection or the INSERT block
        logger.error(f"Failed to submit rewrite task {task_id}: {e}", exc_info=True)
        if isinstance(e, ConnectionError): # Specific error from our get_db_connection
            raise HTTPException(status_code=503, detail=str(e)) # Service Unavailable
        raise HTTPException(status_code=500, detail=f"Failed to submit rewrite task: {str(e)}")
    finally:
        if conn:
            conn.close()
            logger.info(f"[Task {task_id}] DB connection closed for submission endpoint.")


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