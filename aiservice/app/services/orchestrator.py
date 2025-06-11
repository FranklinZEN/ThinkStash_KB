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
        time.sleep(1)

        _update_progress(db_conn, task_id, "Fetching and processing content...", 30)
        # In a real app, this is where you'd use source_url to fetch and process content.
        processed_content = {
            "title": f"Card from {source_url}",
            "content": f"This is the reconstructed content from the source URL: {source_url}",
            "tags": ["reconstructed", "pipeline", "new-card"] # Example tags
        }
        time.sleep(1)

        _update_progress(db_conn, task_id, "Creating knowledge card in database...", 70)
        
        with db_conn.cursor() as cur:
            # Create the new KnowledgeCard and get its ID
            new_card_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO "KnowledgeCard" (id, "userId", title, content, "createdAt", "updatedAt")
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    new_card_id,
                    user_id,
                    processed_content["title"],
                    json.dumps(processed_content["content"])
                )
            )

            # Handle tags: Create them if they don't exist and link them to the card.
            for tag_name in processed_content["tags"]:
                # Check if tag exists, if not, create it
                cur.execute('INSERT INTO "Tag" (id, name, "createdAt", "updatedAt") VALUES (%s, %s, NOW(), NOW()) ON CONFLICT (name) DO NOTHING', (str(uuid.uuid4()), tag_name))
                # Link the tag to the card in the _CardTags join table
                cur.execute('INSERT INTO "_CardTags" ("A", "B") SELECT %s, id FROM "Tag" WHERE name = %s', (new_card_id, tag_name))

            final_result = { "cardId": new_card_id }
        
        db_conn.commit()
        
        _update_progress(db_conn, task_id, "Pipeline completed successfully.", 100)

        return final_result
        
    except Exception as e:
        print(f"Orchestrator pipeline failed for task {task_id}: {e}")
        # In case of failure, we re-raise the exception to be handled by the worker.
        raise e 