import time
import json
import uuid

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
    Executes the full AI pipeline to create a Knowledge Card.
    """
    try:
        source_url = payload.get("sourceUrl")
        user_id = payload.get("userId") # We need the user ID to associate the card

        if not user_id:
            raise ValueError("userId is missing from the task payload")

        _update_progress(db_conn, task_id, "Starting reconstruction pipeline...", 10)
        time.sleep(2)

        _update_progress(db_conn, task_id, "Fetching and processing content...", 40)
        # In a real app, this is where you'd use source_url to fetch and process content.
        # For now, we'll create some dummy content.
        processed_content = {
            "title": f"Card from {source_url}",
            "content": f"This is the reconstructed content from the source URL: {source_url}",
            "summary": "This is a summary of the content.",
            "tags": ["reconstructed", "pipeline"]
        }
        time.sleep(3)

        _update_progress(db_conn, task_id, "Creating knowledge card in database...", 80)
        
        with db_conn.cursor() as cur:
            # Create the new KnowledgeCard and get its ID
            new_card_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO "KnowledgeCard" (id, "userId", title, content, summary, tags, "sourceUrl")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    new_card_id,
                    user_id,
                    processed_content["title"],
                    json.dumps(processed_content["content"]), # Assuming content is stored as JSON
                    processed_content["summary"],
                    processed_content["tags"],
                    source_url
                )
            )
            
            # The final result is the ID of the card we just created.
            final_result = { "cardId": new_card_id }
        
        db_conn.commit()
        
        _update_progress(db_conn, task_id, "Pipeline completed successfully.", 100)

        return final_result
        
    except Exception as e:
        print(f"Orchestrator pipeline failed for task {task_id}: {e}")
        # In case of failure, we re-raise the exception to be handled by the worker.
        raise e 