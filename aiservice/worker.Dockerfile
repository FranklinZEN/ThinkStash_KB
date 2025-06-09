FROM python:3.11-slim
WORKDIR /app
COPY ./aiservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# This copies the contents of the aiservice directory (app, worker.py etc.)
# into the current WORKDIR (/app), which is the correct structure.
COPY ./aiservice/. .
# The CMD executes the worker script from the WORKDIR.
CMD ["python", "-u", "worker.py"] 