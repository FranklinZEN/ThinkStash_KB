FROM python:3.11-slim
WORKDIR /app

# Install system dependencies required by Python packages, like libmagic for python-magic
RUN apt-get update && apt-get install -y libmagic1 && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY ./aiservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project directory to ensure all modules are available
COPY . /app/

# List the contents of the /app directory to help with debugging
RUN ls -la /app
RUN ls -la /app/aiservice

# Run the worker script
CMD ["python", "-u", "aiservice/worker.py"] 