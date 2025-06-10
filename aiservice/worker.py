import psycopg2
import psycopg2.extras
import time
import json
import os
from app.config.settings import settings
from app.services.orchestrator import run_pipeline

def get_db_connection():
    # The DATABASE_URL is retrieved from the settings object
    return psycopg2.connect(settings.DATABASE_URL)

def process_single_task():
    conn = None
    task_id = None
    try:
        conn = get_db_connection()
        conn.autocommit = False
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Begin a transaction and lock the row
            cur.execute("""
                BEGIN;
                SELECT id, payload FROM "Task" WHERE status = 'PENDING' ORDER BY "createdAt" ASC LIMIT 1 FOR UPDATE SKIP LOCKED;
            """)
            task_record = cur.fetchone()

            if task_record:
                task_id = task_record['id']
                payload = task_record['payload']
                print(f"Processing task: {task_id}")
                
                # Mark task as processing
                cur.execute('UPDATE "Task" SET status = %s, "progressMessage" = %s WHERE id = %s', ('PROCESSING', 'Worker picked up task', task_id))
                conn.commit()
                  
                # Now run the pipeline with the same connection
                final_result = run_pipeline(conn, task_id, payload)
                  
                # If pipeline succeeds, mark as completed
                cur.execute('UPDATE "Task" SET status = %s, "progressMessage" = %s, result = %s WHERE id = %s', ('COMPLETED', 'Task finished successfully', json.dumps(final_result), task_id))
                print(f"Task {task_id} completed successfully.")
            else:
                # It's okay if there are no tasks, just print a waiting message
                print("No pending tasks found. Waiting...")
            
            # Commit the transaction (either the PROCESSING/COMPLETED update, or just ending the BEGIN)
            conn.commit()

    except Exception as e:
        print(f"Processing failed for task {task_id}: {e}")
        if conn and task_id:
            conn.rollback() # Rollback any partial changes from the failed pipeline
            error_payload = json.dumps({
                "userMessage": "An unexpected error occurred during processing.", 
                "errorCode": "PIPELINE_FAILURE", 
                "details": str(e)
            })
            with conn.cursor() as cur:
                cur.execute('UPDATE "Task" SET status = %s, error = %s WHERE id = %s', ('FAILED', error_payload, task_id))
            conn.commit()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Starting ThinkStash Worker...")
    # Initialize settings to load environment variables
    # This will raise an error if DATABASE_URL is not set
    if not settings.DATABASE_URL:
        raise ValueError("DATABASE_URL not configured in settings.")

    while True:
        process_single_task()
        # Wait for 5 seconds before checking for a new task
        time.sleep(5) 