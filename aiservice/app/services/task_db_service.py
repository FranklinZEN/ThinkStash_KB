import psycopg2
import psycopg2.extras # For dictionary cursor
import datetime
import json
from typing import Optional, Dict, Any

from aiservice.app.config.settings import settings
from aiservice.app.config.logging_config import get_logger
from aiservice.app.models.task_models import TaskStatus # Enum for task statuses

logger = get_logger(__name__)

def get_db_connection():
    """Establishes a new database connection."""
    if not settings.database_url:
        logger.error("DATABASE_URL is not configured in settings.", extra={'error_type': 'configuration', 'setting_name': 'DATABASE_URL'})
        # Re-raise a specific exception or let the caller handle it.
        # For now, raising ValueError as it's a config issue.
        raise ValueError("Database configuration error: DATABASE_URL not set.")
    try:
        conn = psycopg2.connect(settings.database_url)
        return conn
    except Exception as e:
        logger.error("Failed to connect to database", extra={'error_type': 'connection', 'exception_message': str(e)}, exc_info=True)
        raise ConnectionError(f"Database connection error: {e}") # Raise a more specific error

def _execute_update(conn, sql: str, params: tuple, task_id: str, operation_desc: str):
    """Helper function to execute update statements."""
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
        logger.info(f"Successfully {operation_desc}", extra={'task_id': task_id, 'db_operation': operation_desc})
    except Exception as e:
        logger.error(f"Failed to {operation_desc}", extra={'task_id': task_id, 'db_operation': operation_desc, 'error_message': str(e)}, exc_info=True)
        # Consider rolling back if part of a larger transaction not handled by autocommit
        # For single operations, commit failure means the operation didn't complete.
        raise # Re-raise the exception to be handled by the caller

def update_task_status_processing(task_id: str, conn):
    """Updates the task status to PROCESSING."""
    sql = 'UPDATE "AITask" SET status = %s, "updatedAt" = %s WHERE id = %s'
    params = (TaskStatus.PROCESSING.value, datetime.datetime.utcnow(), task_id)
    _execute_update(conn, sql, params, task_id, "update status to PROCESSING")

def update_task_status_completed(task_id: str, result_data: Dict[str, Any], conn):
    """Updates the task status to COMPLETED and stores the result data."""
    # ai_rewritten_content_blocks are List[ContentBlock], need to dump them
    # Assuming result_data is a dict ready for json.dumps, which includes already model_dumped blocks
    result_data_json = json.dumps(result_data)
    sql = 'UPDATE "AITask" SET status = %s, "resultData" = %s, "errorMessage" = NULL, "updatedAt" = %s WHERE id = %s'
    params = (TaskStatus.COMPLETED.value, result_data_json, datetime.datetime.utcnow(), task_id)
    _execute_update(conn, sql, params, task_id, "update status to COMPLETED with results")

def update_task_status_failed(task_id: str, error_message: str, conn):
    """Updates the task status to FAILED and stores the error message."""
    sql = 'UPDATE "AITask" SET status = %s, "errorMessage" = %s, "updatedAt" = %s WHERE id = %s'
    params = (TaskStatus.FAILED.value, error_message, datetime.datetime.utcnow(), task_id)
    _execute_update(conn, sql, params, task_id, "update status to FAILED with error message")

def update_task_progress_stage(task_id: str, stage_message: str, conn):
    """Updates the task's progressStage field."""
    sql = 'UPDATE "AITask" SET "progressStage" = %s, "updatedAt" = %s WHERE id = %s'
    params = (stage_message, datetime.datetime.utcnow(), task_id)
    _execute_update(conn, sql, params, task_id, f"update progressStage to '{stage_message}'")

def update_task_status_failed_background_error(task_id: str, error_message: str, conn):
    """Updates task to FAILED due to an unexpected background processing error."""
    # This function is distinct in case different logging or error formatting is needed.
    # Currently, it behaves the same as update_task_status_failed.
    update_task_status_failed(task_id, error_message, conn)

# Potential future additions:
# def create_ai_task(...) -> str:
#     # For creating the initial task record, currently handled in endpoints.py
#     pass

# def get_ai_task(task_id: str, conn) -> Optional[Dict]:
#     # For fetching task details if the background worker needs to pull them,
#     # currently, details are passed as arguments to the background function.
#     pass 