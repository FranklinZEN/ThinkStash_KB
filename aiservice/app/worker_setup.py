from celery import Celery
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# It's good practice to have a central configuration point.
# We can use os.environ.get for robustness.
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Define the Celery application instance
app = Celery(
    'aiservice',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['aiservice.app.tasks']
)

# Optional configuration, e.g., to use the json serializer
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True, # Added for better progress tracking
)

if __name__ == '__main__':
    app.start() 