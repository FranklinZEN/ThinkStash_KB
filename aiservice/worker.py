import time
import logging
import os
import threading
from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tenacity import retry, stop_after_attempt, wait_fixed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App for Health Checks ---
app = Flask(__name__)

@app.route('/')
def health_check():
    """Responds to Cloud Run health checks."""
    return "Worker is running.", 200

# --- Worker Logic ---

# Database connection settings from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # This will run at import time, so if the variable is missing, the container will fail to start.
    logging.critical("DATABASE_URL environment variable is not set.")
    raise ValueError("DATABASE_URL environment variable is not set.")

# --- Mock AI Orchestration Logic ---
# In a real scenario, this would import from app.services.orchestrator
def run_pipeline(task_id: str, task_content: str):
    """
    Simulates running the AI analysis pipeline.
    This function will be replaced by the actual orchestrator call.
    """
    logging.info(f"Starting AI pipeline for task_id: {task_id}")
    # Simulate the different stages of the pipeline
    time.sleep(5)  # Simulate initial analysis
    logging.info(f"Pipeline stage 1/3 complete for task_id: {task_id}")
    time.sleep(5)  # Simulate reconstruction
    logging.info(f"Pipeline stage 2/3 complete for task_id: {task_id}")
    time.sleep(5)  # Simulate final analysis
    # Simulate a successful result
    result_json = '{"reconstructed_text": "This is the reconstructed text.", "analysis": "This is the analysis."}'
    logging.info(f"AI pipeline finished successfully for task_id: {task_id}")
    return result_json, "COMPLETED"

# --- Database Polling and Task Processing ---

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def get_db_connection():
    """Establishes and returns a database engine."""
    logging.info("Attempting to connect to the database...")
    engine = create_engine(DATABASE_URL)
    # Test the connection
    with engine.connect() as connection:
        logging.info("Database connection successful.")
    return engine

def process_pending_tasks(engine):
    """
    Polls for pending tasks, processes them, and updates their status.
    """
    Session = sessionmaker(bind=engine)
    with Session() as session:
        try:
            # Find the oldest pending task
            query = text("""
                SELECT id, content
                FROM "Task"
                WHERE status = 'PENDING'
                ORDER BY "createdAt"
                LIMIT 1
                FOR UPDATE SKIP LOCKED;
            """)
            result = session.execute(query).fetchone()

            if result:
                task_id, task_content = result
                logging.info(f"Found pending task: {task_id}")

                # 1. Update status to PROCESSING
                session.execute(text("""
                    UPDATE "Task" SET status = 'PROCESSING', "updatedAt" = NOW() WHERE id = :task_id
                """), {'task_id': task_id})
                session.commit()
                logging.info(f"Task {task_id} status updated to PROCESSING.")

                # 2. Run the AI pipeline
                result_json, final_status = run_pipeline(task_id, task_content)

                # 3. Update status to COMPLETED (or FAILED)
                session.execute(text("""
                    UPDATE "Task" SET status = :status, result = :result, "updatedAt" = NOW() WHERE id = :task_id
                """), {'status': final_status, 'result': result_json, 'task_id': task_id})
                session.commit()
                logging.info(f"Task {task_id} status updated to {final_status}.")
            else:
                logging.info("No pending tasks found. Waiting...")

        except Exception as e:
            logging.error(f"An error occurred while processing tasks: {e}")
            session.rollback()


def worker_main_loop():
    """Main worker loop that runs indefinitely."""
    logging.info("Starting AI Worker main loop in a background thread...")
    try:
        engine = get_db_connection()
        while True:
            process_pending_tasks(engine)
            # Poll every 10 seconds
            time.sleep(10)
    except Exception as e:
        logging.critical(f"Worker loop failed critically: {e}")
        # The thread will exit, but the main Flask app will keep running.
        # Cloud Run might restart the container if liveness probes fail later.

def main():
    """
    Main entry point. Starts the worker in a background thread
    and the Flask server in the main thread.
    """
    # Start the worker loop in a background thread.
    # daemon=True ensures the thread exits when the main thread exits.
    worker_thread = threading.Thread(target=worker_main_loop, daemon=True)
    worker_thread.start()

    # Start the Flask app to respond to health checks from Cloud Run.
    # The PORT environment variable is automatically set by Cloud Run.
    port = int(os.environ.get("PORT", 8080))
    logging.info(f"Starting health check server on port {port}")
    app.run(host='0.0.0.0', port=port)


if __name__ == "__main__":
    main() 