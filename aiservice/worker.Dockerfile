# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed by your packages
RUN apt-get update && apt-get install -y libmagic1 && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the worker script and all necessary files
COPY worker.py .
COPY main.py .
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

# Debug: Show the contents of the /app directory
RUN echo "=== Contents of /app ===" && \
    ls -la /app && \
    echo "=== Python path ===" && \
    python -c "import sys; print('\n'.join(sys.path))"

# Make port 8080 available
EXPOSE 8080

# Run worker.py when the container launches
CMD ["python", "-u", "worker.py"] 