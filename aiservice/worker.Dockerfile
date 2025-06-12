# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed by your packages
RUN apt-get update && apt-get install -y libmagic1 && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file to leverage Docker cache
COPY ./aiservice/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the worker script first
COPY ./aiservice/worker.py /app/worker.py

# Copy the rest of the application code
COPY ./aiservice/ /app/

# Debug: Show the contents of the /app directory
RUN echo "=== Contents of /app ===" && \
    ls -la /app && \
    echo "=== Contents of /app/aiservice (if exists) ===" && \
    ls -la /app/aiservice || true && \
    echo "=== Python path ===" && \
    python -c "import sys; print('\n'.join(sys.path))"

# Command to run the application
CMD ["python", "-u", "/app/worker.py"] 