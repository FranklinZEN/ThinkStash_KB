# Stage 1: Build stage - with dependencies and build tools
FROM python:3.11-slim as builder

# Set the working directory
WORKDIR /app

# Install uv, a fast Python package installer
RUN pip install uv

# Copy only the requirements file to leverage Docker cache
COPY aiservice/requirements.txt .

# Install dependencies using uv
# This is much faster than pip
RUN uv pip install --system --no-cache -r requirements.txt

# Stage 2: Final stage - minimal runtime environment
FROM python:3.11-slim as final

# Set the working directory
WORKDIR /app

# Set environment variables to prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy the installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code
COPY aiservice/ /app/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application using uvicorn
# Note: We use 0.0.0.0 to bind to all network interfaces, making it accessible from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 