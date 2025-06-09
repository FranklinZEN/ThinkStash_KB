FROM python:3.11-slim
WORKDIR /app
COPY ./aiservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./aiservice/ .
CMD ["python", "-u", "worker.py"] 