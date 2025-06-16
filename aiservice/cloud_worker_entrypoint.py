import os
import threading
import uvicorn
from fastapi import FastAPI, status
from fastapi.responses import PlainTextResponse
from aiservice.celery_app import app as celery_app

# --- Celery Worker ---
def run_celery_worker():
    """Starts the Celery worker."""
    print("Starting Celery worker in a background thread...")
    # The worker is configured via aiservice.celery_app
    worker = celery_app.Worker(loglevel="info")
    worker.start()

# --- Health Check Server ---
# A minimal FastAPI app to respond to Cloud Run's health checks.
health_app = FastAPI()

@health_app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Simple health check endpoint that Cloud Run can probe."""
    return PlainTextResponse("ok")

@health_app.get("/", status_code=status.HTTP_200_OK)
async def root():
    """Root endpoint to verify service is running."""
    return PlainTextResponse("Celery worker service is running.")

def run_health_check_server():
    """Starts the FastAPI health check server on the port specified by the PORT env var."""
    port = int(os.environ.get("PORT", 8080))
    print(f"Health check server starting on host 0.0.0.0, port {port}...")
    uvicorn.run(health_app, host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    print("Starting Cloud Run worker entrypoint...")
    
    # Uvicorn should run in the main thread to properly handle signals and manage the process.
    # The Celery worker can run as a daemon thread in the background.
    
    # 1. Start the celery worker in a background thread.
    worker_thread = threading.Thread(target=run_celery_worker, daemon=True)
    worker_thread.start()

    # 2. Start the health check server in the main thread.
    # This will block and keep the container alive.
    run_health_check_server() 