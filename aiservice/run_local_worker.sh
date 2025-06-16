#!/bin/bash
# This script is used to run the Celery worker for local development.
# It assumes you have a virtual environment set up and activated.

echo "Starting Celery worker for AI service..."

# The -A flag specifies the application instance to use.
# The worker command starts the worker process.
# --loglevel=info sets the logging level.
# -P gevent specifies the gevent pool for concurrency (good for I/O-bound tasks).
# -c 4 specifies the number of worker processes/threads.
celery -A aiservice.celery_app worker --loglevel=info -P threads -c 4 