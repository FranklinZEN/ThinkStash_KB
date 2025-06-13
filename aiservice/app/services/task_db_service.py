import psycopg2
import psycopg2.extras
import psycopg2.pool
import datetime
import json
from typing import Optional, Dict, Any

from aiservice.app.config.settings import settings
from aiservice.app.config.logging_config import get_logger
from aiservice.app.models.task_models import TaskStatus

logger = get_logger(__name__)

def json_serial_converter(o):
    """A JSON serializer that can handle datetimes."""
    if isinstance(o, datetime.datetime):
        return o.isoformat()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

class TaskDBService:
    """
    Manages all database interactions for AITasks using a connection pool.
    This class is responsible for executing DB commands but does not manage
    transactions (commit/rollback), which is left to the calling service (e.g., Orchestrator).
    """
    def __init__(self, min_conn=1, max_conn=10):
        if not settings.database_url:
            logger.error("DATABASE_URL is not configured in settings.", extra={'error_type': 'configuration', 'setting_name': 'DATABASE_URL'})
            raise ValueError("Database configuration error: DATABASE_URL not set.")
        
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                min_conn,
                max_conn,
                dsn=settings.database_url
            )
            logger.info(f"Database connection pool created with min={min_conn}, max={max_conn}")
        except Exception as e:
            logger.error("Failed to create database connection pool", extra={'error_type': 'connection_pool', 'exception_message': str(e)}, exc_info=True)
            raise ConnectionError(f"Database pool creation error: {e}")

    def get_connection(self):
        """Gets a connection from the pool."""
        try:
            return self.pool.getconn()
        except Exception as e:
            logger.error("Failed to get connection from pool", exc_info=True)
            raise ConnectionError(f"Could not get DB connection from pool: {e}")

    def release_connection(self, conn):
        """Releases a connection back to the pool."""
        try:
            self.pool.putconn(conn)
        except Exception as e:
            logger.error("Failed to release connection back to pool", exc_info=True)

    def _execute_update(self, conn, sql: str, params: tuple, task_id: str, operation_desc: str):
        """
        Helper function to execute update statements.
        IMPORTANT: This function NO LONGER commits.
        """
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            logger.info(f"Successfully executed DB command for {operation_desc}", extra={'task_id': task_id, 'db_operation': operation_desc})
        except Exception as e:
            logger.error(f"Failed to execute DB command for {operation_desc}", extra={'task_id': task_id, 'db_operation': operation_desc, 'error_message': str(e)}, exc_info=True)
            raise

    def update_task_status_processing(self, task_id: str, conn):
        """Updates the task status to PROCESSING."""
        sql = 'UPDATE "Task" SET status = %s, "updatedAt" = %s WHERE id = %s'
        params = (TaskStatus.PROCESSING.value, datetime.datetime.utcnow(), task_id)
        self._execute_update(conn, sql, params, task_id, "update status to PROCESSING")

    def update_task_status_completed(self, task_id: str, result_data: Dict[str, Any], conn):
        """Updates the task status to COMPLETED and stores the result data."""
        result_data_json = json.dumps(result_data, default=json_serial_converter)
        sql = 'UPDATE "Task" SET status = %s, result = %s, error = NULL, "updatedAt" = %s WHERE id = %s'
        params = (TaskStatus.COMPLETED.value, result_data_json, datetime.datetime.utcnow(), task_id)
        self._execute_update(conn, sql, params, task_id, "update status to COMPLETED with results")

    def update_task_status_failed(self, task_id: str, error_message: str, conn):
        """Updates the task status to FAILED and stores the error message."""
        error_json = json.dumps({"userMessage": error_message, "details": "Pipeline execution failed."})
        sql = 'UPDATE "Task" SET status = %s, error = %s, "updatedAt" = %s WHERE id = %s'
        params = (TaskStatus.FAILED.value, error_json, datetime.datetime.utcnow(), task_id)
        self._execute_update(conn, sql, params, task_id, "update status to FAILED with error message")

    def update_task_progress_stage(self, task_id: str, stage_message: str, conn):
        """Updates the task's progressMessage field."""
        sql = 'UPDATE "Task" SET "progressMessage" = %s, "updatedAt" = %s WHERE id = %s'
        params = (stage_message, datetime.datetime.utcnow(), task_id)
        self._execute_update(conn, sql, params, task_id, f"update progressMessage to '{stage_message}'")
        
    def create_knowledge_card_from_blocks(self, user_id: str, title: str, blocks: list, conn) -> str:
        """
        Creates a new KnowledgeCard in the database from the processed content blocks.
        Returns the ID of the newly created card.
        """
        card_id = None
        try:
            with conn.cursor() as cur:
                # The 'content' column in KnowledgeCard is JSON
                content_json = json.dumps(blocks, default=json_serial_converter)
                
                sql = """
                    INSERT INTO "KnowledgeCard" (id, title, content, "userId", "createdAt", "updatedAt")
                    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
                    RETURNING id;
                """
                params = (title, content_json, user_id, datetime.datetime.utcnow(), datetime.datetime.utcnow())
                
                cur.execute(sql, params)
                card_id = cur.fetchone()[0]
                logger.info(f"Successfully created KnowledgeCard with id {card_id} for user {user_id}", extra={'user_id': user_id, 'card_id': card_id})
        except Exception as e:
            logger.error(f"Failed to create KnowledgeCard for user {user_id}", extra={'user_id': user_id, 'error_message': str(e)}, exc_info=True)
            # We re-raise the exception so the orchestrator's transaction will be rolled back.
            raise
        
        return card_id

    def close_pool(self):
        """Closes all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed.")

# Potential future additions:
# def create_ai_task(...) -> str:
#     # For creating the initial task record, currently handled in endpoints.py
#     pass

# def get_ai_task(task_id: str, conn) -> Optional[Dict]:
#     # For fetching task details if the background worker needs to pull them,
#     # currently, details are passed as arguments to the background function.
#     pass 