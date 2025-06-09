FROM python:3.11-slim
WORKDIR /app
# Copy requirements first to leverage Docker cache
COPY aiservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy the rest of the application code
COPY aiservice/ .
# Command to run the worker
CMD ["python", "-u", "worker.py"] 