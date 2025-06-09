FROM python:3.11-slim
WORKDIR /app
# Copy requirements first to leverage Docker cache
COPY aiservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy the rest of the application code
COPY aiservice/ .
# DEBUG: List all files recursively to see what's in the build context
RUN ls -laR
# Command to run the worker
CMD ["python", "-u", "worker.py"] 