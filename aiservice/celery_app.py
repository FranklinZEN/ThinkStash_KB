# This file is the entry point for the Celery worker.
# It imports the Celery app instance from worker_setup and the tasks
# so that the Celery worker process can discover them.

from app.worker_setup import app
from app.tasks import process_reconstruction_task, generate_title_task

# The Celery worker will automatically detect the 'app' instance
# and the registered tasks when this module is loaded.