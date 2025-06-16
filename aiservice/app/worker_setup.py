from celery import Celery
from aiservice.app.config.settings import settings

# Define the Celery application instance
app = Celery(
    'aiservice',
    broker=settings.redis_url,
    backend=settings.redis_url,
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