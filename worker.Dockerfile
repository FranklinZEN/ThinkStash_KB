# Use the official Python 3.11 slim image as a parent image
FROM python:3.11-slim

# Set environment variables
# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1
# Set the path for Playwright browsers to be installed system-wide
ENV PLAYWRIGHT_BROWSERS_PATH=/var/lib/playwright

# Set the working directory in the container
WORKDIR /app

# Install system-level dependencies required for the application and Playwright
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # Dependencies for Playwright
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 \
    libatspi2.0-0 libx11-6 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
    libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 \
    # Dependencies for other packages might go here
    build-essential \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user and group for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Create and set permissions for a cache directory if needed by the app
RUN mkdir -p /app/.image_cache && \
    chown -R appuser:appgroup /app/.image_cache

# Copy the requirements file and install Python dependencies as the new user
COPY --chown=appuser:appgroup aiservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its browser dependencies.
# The --with-deps flag will attempt to install system dependencies, which we've already done.
# Running this as appuser ensures browsers are correctly cached if not using PLAYWRIGHT_BROWSERS_PATH=0
# but with PLAYWRIGHT_BROWSERS_PATH=0 it will install to a system location we can create and permission.
RUN mkdir -p /var/lib/playwright && \
    chown -R appuser:appgroup /var/lib/playwright
    
# Switch to the non-root user
USER appuser

# Now, as the non-root user, install the browser binaries.
# These will be installed in the location specified by PLAYWRIGHT_BROWSERS_PATH
RUN python -m playwright install chromium

# Copy the rest of the application code
COPY --chown=appuser:appgroup aiservice/ .

# Command to run the Celery worker
CMD ["celery", "-A", "celery_app:app", "worker", "--loglevel=info"]

# Make port 8000 available to the world outside this container
# EXPOSE 8000 # Workers don't typically need exposed ports unless for monitoring 