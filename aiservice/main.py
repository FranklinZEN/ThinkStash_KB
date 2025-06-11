import psycopg2
import psycopg2.extras
import json
import os
from fastapi import FastAPI, HTTPException, Request
from app.config.settings import settings
from app.services.orchestrator import run_pipeline

app = FastAPI()

def get_db_connection():
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Could not connect to database: {e}")
        # In a real app, you'd want more robust error handling or a retry mechanism.
        raise

@app.post("/invoke")
async def invoke_worker(request: Request):
    # Authentication is now handled by Cloud Run's built-in IAM.
    # The service is configured to not allow unauthenticated requests,
    # and we will grant our Cloud Scheduler the necessary 'run.invoker' role.
    
    conn = get_db_connection()
    conn.autocommit = False
    task_id = None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Find and lock one pending task
            cur.execute("""
                BEGIN;
                SELECT id, payload FROM "Task" WHERE status = 'PENDING' ORDER BY "createdAt" ASC LIMIT 1 FOR UPDATE SKIP LOCKED;
            """)
            task_record = cur.fetchone()

            if not task_record:
                # No pending tasks, which is a normal and expected outcome.
                print("No pending tasks found.")
                return {"status": "success", "message": "No pending tasks."}

            task_id = task_record['id']
            payload = task_record['payload']

            # Mark task as processing
            cur.execute('UPDATE "Task" SET status = %s, "progressMessage" = %s WHERE id = %s',
                        ('PROCESSING', 'Worker picked up task', task_id))
            conn.commit()

            # Run the main processing pipeline
            final_result = run_pipeline(conn, task_id, payload)

            # Mark task as completed
            cur.execute('UPDATE "Task" SET status = %s, "progressMessage" = %s, result = %s WHERE id = %s',
                        ('COMPLETED', 'Task finished successfully', json.dumps(final_result), task_id))
            print(f"Task {task_id} completed successfully.")
            conn.commit()
            return {"status": "success", "processed_task_id": task_id}

    except Exception as e:
        print(f"Processing failed for task {task_id}: {e}")
        if conn and task_id:
            conn.rollback()  # Rollback transaction on error
            error_payload = json.dumps({
                "userMessage": "An unexpected error occurred during processing.",
                "errorCode": "PIPELINE_FAILURE",
                "details": str(e)
            })
            with conn.cursor() as cur:
                cur.execute('UPDATE "Task" SET status = %s, error = %s WHERE id = %s', ('FAILED', error_payload, task_id))
            conn.commit()
        # We raise an HTTPException so Cloud Run knows the invocation failed.
        raise HTTPException(status_code=500, detail=f"Failed to process task {task_id}")

    finally:
        if conn:
            conn.close()

@app.get("/health")
def health_check():
    # Simple health check endpoint for Cloud Run to verify the service is up.
    return {"status": "ok"} 