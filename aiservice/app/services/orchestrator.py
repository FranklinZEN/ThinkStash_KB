import time
import json

def _update_progress(db_conn, task_id, message, progress):
    """Helper function to update task progress in the database."""
    with db_conn.cursor() as cur:
        cur.execute(
            'UPDATE "Task" SET "progressMessage" = %s, "progress" = %s WHERE id = %s',
            (message, progress, task_id)
        )
    db_conn.commit()

def run_pipeline(db_conn, task_id: str, payload: dict):
    """
    Simulates the AI processing pipeline.
    In a real scenario, this would involve calls to AI services, etc.
    """
    try:
        source_url = payload.get("sourceUrl")
        
        _update_progress(db_conn, task_id, "Starting reconstruction pipeline...", 10)
        time.sleep(2) # Simulate work

        _update_progress(db_conn, task_id, "Fetching and processing content...", 40)
        time.sleep(3) # Simulate more work

        _update_progress(db_conn, task_id, "Structuring knowledge card...", 80)
        time.sleep(2) # Simulate final work

        # The final result that will be stored in the 'result' JSON field of the Task.
        # In a real implementation, this would be the actual ID of the created KnowledgeCard.
        final_result = { "cardId": "placeholder-card-id-from-pipeline" }
        
        _update_progress(db_conn, task_id, "Pipeline completed successfully.", 100)

        return final_result
        
    except Exception as e:
        print(f"Orchestrator pipeline failed for task {task_id}: {e}")
        # In case of failure, we re-raise the exception to be handled by the worker.
        raise e 