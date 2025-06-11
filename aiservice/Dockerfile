FROM python:3.11-slim
WORKDIR /app

# Copy and install requirements first to leverage Docker layer caching
COPY ./aiservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY ./aiservice .

# Expose the port the app will run on
# The PORT env var will be set by Cloud Run, so we don't need EXPOSE.

# Run the application with Gunicorn
# Using gunicorn for a production-ready server.
# The worker class 'uvicorn.workers.UvicornWorker' is used to run our ASGI app.
# The number of workers (-w 4) is a starting point and can be tuned.
# We bind to 0.0.0.0 and the port specified by the PORT environment variable.
# Using "exec" in a shell allows for proper signal handling and environment variable substitution.
CMD ["sh", "-c", "exec gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT} main:app"] 