# ----------------- Builder Stage -----------------
# This stage installs dependencies and builds wheels.
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN pip install --upgrade pip

# Copy only the requirements file to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip wheel --no-cache-dir --wheel-dir=/app/wheels -r requirements.txt


# ----------------- Runner Stage -----------------
# This stage creates the final, lean production image.
FROM python:3.11-slim

# Create a non-root user and group
RUN addgroup --system app && adduser --system --group app

# Set the working directory
WORKDIR /app

# Copy the wheels from the builder stage
COPY --from=builder /app/wheels /wheels

# Install the wheels
RUN pip install --no-cache /wheels/*
RUN pip install pytest pytest-asyncio pytest-cov requests-mock

# Copy the application code
COPY . .

# Run tests
RUN pytest

# Switch to the non-root user
USER app

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 