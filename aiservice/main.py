import asyncio
import json
import os
import sys
import platform
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Request, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, date
import logging

# Apply asyncio policy patch for Windows if applicable
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
from aiservice.app.services.task_db_service import TaskDBService
from aiservice.app.tasks import process_reconstruction_task, generate_title_task, process_rewrite_task
from .celery_app import app as celery_app
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

class TaskDispatchPayload(BaseModel):
    task_id: str
    task_type: str

class CreateTaskPayload(BaseModel):
    task_type: str
    payload: Dict[str, Any]
    user_id: Optional[str] = None

# --- Global Service Instances ---
# By creating instances here, they are shared across the application's lifespan
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

# --- FastAPI App Definition ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # This block runs on startup
    # The services are already initialized above
    print("AI Service started. Orchestrator and services are initialized.")
    yield
    # This block runs on shutdown
    print("AI Service shutting down. Closing database connection pool.")
    task_db_service.close_pool()

app = FastAPI(title="ThinkStash AI Worker Service", lifespan=lifespan)

def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# The /invoke endpoint and the functions it relies on (process_single_task, 
# background_worker_loop) are part of a legacy polling architecture and are no 
# longer needed with the Celery-based implementation. They are being removed to
# avoid confusion and architectural conflicts.

@app.post("/create-and-dispatch-task")
async def create_and_dispatch_task(payload: CreateTaskPayload = Body(...)):
    """
    Creates a new task in the database and immediately dispatches it to a Celery worker.
    This is the new preferred endpoint for frontends.
    """
    conn = None
    try:
        conn = task_db_service.get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # Prepare data for insertion
            task_id = str(uuid.uuid4())
            user_id = payload.user_id
            task_type = payload.task_type
            task_payload_json = json.dumps(payload.payload)
            
            sql = """
                INSERT INTO "Task" (id, "userId", type, status, payload, "progressMessage", "createdAt", "updatedAt")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            params = (
                task_id, user_id, task_type, 'PENDING', 
                task_payload_json, 'Task created', 
                datetime.utcnow(), datetime.utcnow()
            )
            
            cur.execute(sql, params)
            new_task_id = cur.fetchone()['id']
            conn.commit()
            
            logger.info(f"Successfully created task {new_task_id} of type {task_type} for user {user_id}")

            # Now, prepare and dispatch the task
            source_identifier = None
            source_type = None

            if task_type == 'REWRITE_CONTENT':
                if 'content_blocks' not in payload.payload:
                    raise HTTPException(status_code=400, detail="Payload for REWRITE_CONTENT must contain 'content_blocks'")
                source_identifier = f"content-rewrite-for-task-{new_task_id}"
                source_type = 'content_blocks'
            else:
                source_identifier = payload.payload.get('url') or payload.payload.get('text')
                if 'url' in payload.payload:
                    source_type = 'url'
                elif 'text' in payload.payload:
                    source_type = 'text'

            if not source_identifier:
                raise HTTPException(status_code=400, detail="Payload must contain 'url', 'text', or 'content_blocks' for the given task type.")

            task_data = {
                "task_id": new_task_id,
                "user_id": user_id,
                "task_type": task_type,
                "source_identifier": source_identifier,
                "source_type": source_type,
                "payload": payload.payload
            }

            logger.info(f"Dispatching newly created task: {task_data}")

            # a string that's a valid task name in Celery
            task_to_run = None
            task_payload_for_celery = None

            if task_type == 'RECONSTRUCT_AND_ANALYZE':
                task_to_run = 'aiservice.app.tasks.process_reconstruction_task'
                # The payload for this task is the 'payload' part of the incoming request
                task_payload_for_celery = payload.payload
            elif task_type == 'GENERATE_TITLE':
                task_to_run = 'aiservice.app.tasks.generate_title_task'
                task_payload_for_celery = payload.payload
            elif task_type == 'REWRITE_CONTENT':
                task_to_run = 'aiservice.app.tasks.process_rewrite_task'
                # The payload for this task is the 'payload' part of the incoming request
                task_payload_for_celery = payload.payload
            # Add other task types here in the future
            
            if not task_to_run:
                raise HTTPException(status_code=400, detail=f"Unknown task_type: {task_type}")

            # Send task to Celery
            celery_app.send_task(
                name=task_to_run,
                args=[task_data], # Pass the full task_data dictionary
                task_id=new_task_id
            )
            
            logger.info(f"Task {new_task_id} of type {task_type} dispatched to Celery worker.")

            return {"message": "Task created and dispatched", "task_id": new_task_id}
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"An unexpected error occurred in create_and_dispatch_task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
    finally:
        if conn:
            task_db_service.release_connection(conn)

@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """
    Retrieves the status and result of a Celery task from the celery_taskmeta table.
    """
    conn = None
    try:
        conn = task_db_service.get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT id, "userId", type, status, payload FROM "Task"
                WHERE id = %s
            """, (task_id,))
            task_record = cur.fetchone()

            if not task_record:
                raise HTTPException(status_code=404, detail="Task not found")

            # Manually construct the response to ensure all required fields,
            # especially the payload, are included. This avoids any ambiguity
            # from database driver or framework conversions.
            response_data = {
                "id": task_record["id"],
                "status": task_record["status"],
                "payload": task_record["payload"]
                # Add other fields here if the frontend needs them in the future
            }
            return response_data

    except Exception as e:
        logger.error(f"An error occurred in get_task_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred")
    finally:
        if conn:
            task_db_service.release_connection(conn)

@app.post("/dispatch-task")
async def dispatch_task(payload: TaskDispatchPayload = Body(...)):
    """
    DEPRECATED: This endpoint is problematic as it doesn't create a persistent task record
    before dispatching. Use /create-and-dispatch-task instead.
    
    Dispatches a task to a Celery worker.
    Requires the task to be registered in the Celery app.
    """
    raise HTTPException(status_code=410, detail="This endpoint is deprecated. Use /create-and-dispatch-task.")

@app.get("/")
def health_check():
    """A simple health check endpoint."""
    return {"status": "ok", "message": "AI Service is healthy."}

# Entry point for running the app with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    # This is mainly for local development. For production, use a process manager like Gunicorn.
    # The background worker loop needs to be started with the app.
    # FastAPI's lifespan context manager is the modern way to handle this.
    uvicorn.run("aiservice.main:app", host="0.0.0.0", port=8000, reload=True) 