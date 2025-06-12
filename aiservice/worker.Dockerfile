FROM python:3.11-slim
WORKDIR /app

# Install system dependencies required by Python packages, like libmagic for python-magic
RUN apt-get update && apt-get install -y libmagic1 && rm -rf /var/lib/apt/lists/*

COPY ./aiservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./aiservice/ /app/

# List the contents of the /app directory to help with debugging
RUN ls -la /app

CMD ["python", "-u", "worker.py"] 