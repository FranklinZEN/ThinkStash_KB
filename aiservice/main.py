import sys
import asyncio
from contextlib import asynccontextmanager
import psycopg2
import psycopg2.pool
import psycopg2.extras
import json
from datetime import datetime, date
from functools import lru_cache
from typing import Dict, Any
import uuid

from fastapi import FastAPI, Depends, HTTPException
from psycopg2.extensions import connection as Connection
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from aiservice.app.config.settings import Settings
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput
from aiservice.app.models.task_models import TaskRequest
from aiservice.app.services.task_db_service import TaskDBService
from aiservice.app.services.orchestrator import ParallelOrchestrator
from aiservice.app.services.routing_service import RoutingService
from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService
from .celery_app import app as celery_app
from aiservice.app.tasks import process_reconstruction_task, generate_title_task, generate_keywords_task, process_rewrite_task
import logging

# --- Pydantic Models for API ---
class TaskRequest(BaseModel):
    task_type: str
    payload: Dict[str, Any]
    user_id: str

# --- App Initialization & Lifespan ---
db_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    logging.info("AI Service starting up...")
    settings = Settings()
    db_pool = psycopg2.pool.SimpleConnectionPool(
        minconn=settings.db_pool_min_size,
        maxconn=settings.db_pool_max_size,
        dsn=settings.database_url
    )
    logging.info("Database connection pool created.")
    yield
    logging.info("AI Service shutting down...")
    if db_pool:
        db_pool.closeall()
        logging.info("Database connection pool closed.")

app = FastAPI(title="ThinkStash AI Service", lifespan=lifespan)

# --- Dependency Injectors ---
@lru_cache()
def get_settings() -> Settings:
    return Settings()

def get_task_db_service() -> TaskDBService:
    if db_pool is None:
        raise RuntimeError("Database connection pool is not initialized.")
    return TaskDBService(db_pool=db_pool)

def get_orchestrator(
    settings: Settings = Depends(get_settings),
    task_db_service: TaskDBService = Depends(get_task_db_service)
) -> ParallelOrchestrator:
    routing_service = RoutingService(settings)
    image_processing_service = ImageProcessingService(settings)
    content_structuring_service = ContentStructuringService(settings)
    return ParallelOrchestrator(
        task_db_service=task_db_service,
        routing_service=routing_service,
        image_processing_service=image_processing_service,
        content_structuring_service=content_structuring_service,
        settings=settings
    )

# --- API Endpoints ---
@app.get("/")
def health_check():
    return {"status": "ok", "message": "AI Service is healthy."}

@app.post("/process", response_model=OrchestrationOutput)
async def process_synchronously(
    input_data: OrchestrationInput,
    orchestrator: ParallelOrchestrator = Depends(get_orchestrator)
):
    result = await orchestrator.process(input_data)
    if result.is_success() and result.data:
        return result.data
    error_detail = result.error_details or result.error_message or "An unknown error occurred."
    raise HTTPException(status_code=500, detail=jsonable_encoder(error_detail))

@app.post("/create-and-dispatch-task", status_code=202)
async def create_and_dispatch_task(
    task_request: TaskRequest,
    task_db_service: TaskDBService = Depends(get_task_db_service)
):
    conn = None
    task_id = str(uuid.uuid4())
    try:
        conn = task_db_service.get_connection()
        
        # Prepare the payload once
        celery_payload = {
            "task_id": task_id,
            "user_id": task_request.user_id,
            "payload": task_request.payload or {}
        }
        
        # Determine the target task based on the task_type
        if task_request.task_type == "RECONSTRUCT_AND_ANALYZE":
            target_task = process_reconstruction_task
        elif task_request.task_type == "GENERATE_TITLE":
            target_task = generate_title_task
        elif task_request.task_type == "GENERATE_KEYWORDS":
            target_task = generate_keywords_task
        elif task_request.task_type == "REWRITE_CONTENT":
            target_task = process_rewrite_task
        else:
            raise HTTPException(status_code=400, detail=f"Unknown task type: {task_request.task_type}")

        # Use a single, consistent payload structure for the database
        task_payload_for_db = json.dumps(
            task_request.payload, 
            default=lambda o: o.isoformat() if isinstance(o, (datetime, date)) else None
        )

        with conn.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "Task" (id, "userId", type, payload, status, "createdAt", "updatedAt") VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (task_id, task_request.user_id, task_request.task_type, task_payload_for_db, 'PENDING', datetime.utcnow(), datetime.utcnow())
            )
            conn.commit()

        # Send the task to Celery
        target_task.apply_async(args=[celery_payload], task_id=task_id)
        
        return {"task_id": task_id}
    except Exception as e:
        logging.error(f"Error in create_and_dispatch_task: {e}", exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to create and dispatch task.")
    finally:
        if conn:
            task_db_service.release_connection(conn)

@app.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    include_result: bool = False,
    task_db_service: TaskDBService = Depends(get_task_db_service),
):
    """
    Retrieves the status and result of a task from the database.
    If include_result is true, it will return the full result payload.
    """
    conn = None
    try:
        conn = task_db_service.get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(
                'SELECT id, status, result, type as task_type, "progressMessage" FROM "Task" WHERE id = %s',
                (task_id,),
            )
            task_record = cursor.fetchone()

        if not task_record:
            # Fallback to Celery backend if not in DB, though DB should be the source of truth
            celery_result = celery_app.AsyncResult(task_id)
            if not celery_result:
                 raise HTTPException(status_code=404, detail="Task not found in database or Celery backend.")
            return {
                "task_id": task_id,
                "status": celery_result.status,
                "result": celery_result.result if celery_result.successful() else None,
                "error": str(celery_result.result) if celery_result.failed() else None,
                "progressMessage": None, 
                "task_type": None
            }
        
        db_status = task_record["status"]
        
        # Translate internal DB status to the public API status contract
        api_status = db_status
        if db_status == "COMPLETED":
            api_status = "SUCCESS"
        # The frontend handles PENDING, so we don't need to map PROCESSING for now.
        # If we did, it would be:
        # elif db_status == "PROCESSING":
        #     api_status = "PENDING"

        response_data = {
            "task_id": task_record["id"],
            "status": api_status,
            "progressMessage": task_record["progressMessage"],
            "task_type": task_record["task_type"],
            "result": None,
            "error": None,
        }

        if db_status == "COMPLETED" and include_result:
            response_data["result"] = task_record["result"]
        elif db_status == "FAILED":
            # The 'result' column stores the error message on failure
            response_data["error"] = str(task_record["result"])

        return response_data
    except Exception as e:
        logging.error(
            f"Error fetching task status for {task_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Internal server error while fetching task status."
        )
    finally:
        if conn:
            task_db_service.release_connection(conn) 