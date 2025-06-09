import psycopg2
import psycopg2.extras
import time
import json
from app.config.settings import settings
from app.services.orchestrator import run_pipeline

def get_db_connection():
    return psycopg2.connect(settings.DATABASE_URL)

def process_single_task():
    conn = get_db_connection()
    conn.autocommit = False
    task_id = None
    task_found = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                BEGIN;
                SELECT id, payload FROM "Task" WHERE status = 'PENDING' ORDER BY "createdAt" ASC LIMIT 1 FOR UPDATE SKIP LOCKED;
            """)
            task_record = cur.fetchone()

            if task_record:
                task_found = True
                task_id = task_record['id']
                payload = task_record['payload']
                cur.execute('UPDATE "Task" SET status = %s, "progressMessage" = %s WHERE id = %s', ('PROCESSING', 'Worker picked up task', task_id))
                conn.commit()
                  
                # Now run the pipeline with the same connection
                final_result = run_pipeline(conn, task_id, payload)
                  
                # If pipeline succeeds
                cur.execute('UPDATE "Task" SET status = %s, "progressMessage" = %s, result = %s WHERE id = %s', ('COMPLETED', 'Task finished successfully', json.dumps(final_result), task_id))
                print(f"Task {task_id} completed successfully.")
            conn.commit()
    except Exception as e:
        print(f"Processing failed for task {task_id}: {e}")
        if conn and task_id:
            conn.rollback() # Rollback any partial changes from the failed pipeline
            error_payload = json.dumps({"userMessage": "An unexpected error occurred during processing.", "errorCode": "PIPELINE_FAILURE", "details": str(e)})
            with conn.cursor() as cur:
                cur.execute('UPDATE "Task" SET status = %s, error = %s WHERE id = %s', ('FAILED', error_payload, task_id))
            conn.commit()
    finally:
        if conn:
            conn.close()
    return task_found

if __name__ == "__main__":
    print("Starting ThinkStash Worker run...")
    processed_a_task = process_single_task()
    if not processed_a_task:
        print("No pending tasks found.")
    print("ThinkStash Worker run finished.") 