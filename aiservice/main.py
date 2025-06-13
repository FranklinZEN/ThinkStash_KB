import asyncio
import json
import os
import sys
import platform
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, date

# Apply asyncio policy patch for Windows if applicable
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- Service Imports from Stable Build ---
from aiservice.app.config.settings import Settings
from aiservice.app.services.orchestrator import ParallelOrchestrator
from aiservice.app.services.routing_service import RoutingService
from aiservice.app.services.acquisition.web_service import WebAcquisitionService
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService
from aiservice.app.services.acquisition.file_service import FileAcquisitionService
from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock
# --- End Service Imports ---

# --- Database and Task Models ---
# A Pydantic model to represent the incoming message from Cloud Scheduler/PubSub
class PubSubMessage(BaseModel):
    data: bytes

class TaskPayload(BaseModel):
    id: str
    userId: str
    type: str
    status: str
    payload: Dict[str, Any]

# --- FastAPI App Definition ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background task when the application starts
    asyncio.create_task(background_worker_loop())
    yield
    # (No cleanup needed for this simple case)

app = FastAPI(title="ThinkStash AI Worker Service", lifespan=lifespan)

# --- Orchestrator Factory ---
# This function creates an instance of the orchestrator and all its dependencies.
# It's based on the get_orchestrator function from the stable build's endpoints.py.
def get_orchestrator_instance() -> ParallelOrchestrator:
    settings = Settings()
    routing_s = RoutingService(settings=settings)
    web_acq_s = WebAcquisitionService(settings=settings)
    pdf_acq_s = PDFAcquisitionService(settings=settings)
    file_acq_s = FileAcquisitionService(settings=settings)
    img_proc_s = ImageProcessingService(settings=settings)
    content_struct_s = ContentStructuringService(settings=settings)
    
    return ParallelOrchestrator(
        routing_service=routing_s,
        web_acquisition_service=web_acq_s,
        pdf_acquisition_service=pdf_acq_s,
        file_acquisition_service=file_acq_s,
        image_processing_service=img_proc_s,
        content_structuring_service=content_struct_s,
        settings=settings
    )

def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(database_url)

async def process_single_task():
    """
    This function fetches and processes one pending task from the database.
    It's the core logic that was previously in the /invoke endpoint.
    """
    conn = None
    task_id = None
    try:
        conn = get_db_connection()
        conn.autocommit = False

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT id, "userId", type, status, payload FROM "Task"
                WHERE status = 'PENDING'
                ORDER BY "createdAt" ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED;
            """)
            task_record = cur.fetchone()

            if not task_record:
                # No pending tasks, which is a normal state.
                return

            task = TaskPayload(**task_record)
            task_id = task.id

            print(f"Processing task: {task_id} of type {task.type}")
            cur.execute(
                'UPDATE "Task" SET status = %s, "progressMessage" = %s WHERE id = %s',
                ('PROCESSING', 'Worker picked up task...', task_id)
            )
            conn.commit()

        orchestrator = get_orchestrator_instance()
        orchestration_input = None
        
        # --- Task Routing ---
        if task.type == 'RECONSTRUCT_AND_ANALYZE':
            source_url = task.payload.get("sourceUrl")
            if not source_url:
                raise ValueError("Task payload for RECONSTRUCT_AND_ANALYZE is missing 'sourceUrl'")
            orchestration_input = OrchestrationInput(
                source_identifier=source_url,
                source_type='url',
                user_id=task.userId,
                job_id=task_id
            )
        elif task.type == 'RECONSTRUCT_AND_ANALYZE_FILE':
            gcs_path = task.payload.get("gcsPath")
            file_type = task.payload.get("fileAcquisitionType") # e.g., 'pdf', 'docx'
            if not gcs_path or not file_type:
                raise ValueError("Task payload for RECONSTRUCT_AND_ANALYZE_FILE is missing 'gcsPath' or 'fileAcquisitionType'")
            orchestration_input = OrchestrationInput(
                source_identifier=gcs_path,
                source_type=file_type,
                user_id=task.userId,
                job_id=task_id
            )
        # Add routing for other task types here in the future
        elif task.type in ['REWRITE_CONTENT', 'GENERATE_KEYWORDS', 'GENERATE_TITLE']:
            raise NotImplementedError(f"Task type '{task.type}' is not yet implemented in the worker.")
        else:
            raise ValueError(f"Unknown or unsupported task type: {task.type}")

        orchestrator_result = await orchestrator.process(orchestration_input)

        if not orchestrator_result.is_success() or not orchestrator_result.data:
            error_message = orchestrator_result.error_message or "Orchestration failed without a message."
            raise ValueError(error_message)

        # Correctly unpack the OrchestrationOutput object
        orchestration_output: OrchestrationOutput = orchestrator_result.data
        
        # The content blocks are already structured with images.
        content_blocks_as_dicts = [block.model_dump(exclude_none=True) for block in orchestration_output.original_content_blocks]

        # Use a more generic result structure based on task type
        final_result = {}
        if task.type == 'RECONSTRUCT_AND_ANALYZE':
             card_title = orchestration_output.extracted_title or "Untitled Card"
             final_result = {
                 "title": card_title,
                 "contentBlocks": content_blocks_as_dicts,
                 "keywords": [], # Placeholder for now
                 "document_metadata": orchestration_output.document_metadata.model_dump(exclude_none=True) if orchestration_output.document_metadata else None
             }

        with conn.cursor() as cur:
            cur.execute(
                'UPDATE "Task" SET status = %s, "progressMessage" = %s, result = %s WHERE id = %s',
                ('COMPLETED', 'Task finished successfully', json.dumps(final_result, default=json_serializer), task_id)
            )
            conn.commit()
            print(f"Task {task_id} completed successfully.")

    except Exception as e:
        print(f"Processing failed for task {task_id}: {e}")
        if conn and task_id:
            conn.rollback()
            error_payload = json.dumps({
                "userMessage": f"Processing failed for task {task_id}.",
                "errorCode": "PIPELINE_FAILURE",
                "details": str(e)
            })
            with conn.cursor() as cur:
                cur.execute(
                    'UPDATE "Task" SET status = %s, error = %s WHERE id = %s',
                    ('FAILED', error_payload, task_id)
                )
            conn.commit()
    finally:
        if conn:
            conn.close()

async def background_worker_loop():
    """A loop that runs in the background to process tasks."""
    print("Background worker loop started.")
    while True:
        try:
            await process_single_task()
        except Exception as e:
            # This catches errors in the processing logic itself, so the loop doesn't die.
            print(f"An error occurred in the worker processing loop: {e}")
        await asyncio.sleep(5) # Poll every 5 seconds

# --- API Endpoints ---
# The /invoke endpoint is kept for cloud deployments but not used for local dev.
@app.post("/invoke")
async def invoke_worker_for_cloud(request: Request):
    """
    This endpoint is for single-shot invocation in a cloud environment.
    For local development, the background loop is used instead.
    """
    try:
        # This provides a way to manually trigger processing for one task
        await process_single_task()
        return {"status": "ok", "message": "Processed one task batch."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "ok"}

# This part is for local development if needed
if __name__ == "__main__":
    import uvicorn
    # It's recommended to set DATABASE_URL via an environment variable
    # e.g., export DATABASE_URL=...
    if not os.getenv("DATABASE_URL"):
        print("Warning: DATABASE_URL is not set. The worker will fail if it needs the database.")
    uvicorn.run(app, host="0.0.0.0", port=8080) 