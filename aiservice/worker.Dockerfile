# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed by your packages
RUN apt-get update && apt-get install -y \
    libmagic1 \
    wget \
    gnupg \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY ./aiservice/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps

# Create directory for Playwright browsers
RUN mkdir -p /app/pw-browsers

# Copy the entire aiservice package
COPY ./aiservice/ /app/aiservice/

# Debug: Show the contents of the /app directory
RUN echo "=== Contents of /app ===" && \
    ls -la /app && \
    echo "=== Contents of /app/aiservice ===" && \
    ls -la /app/aiservice && \
    echo "=== Python path ===" && \
    python -c "import sys; print('\n'.join(sys.path))" && \
    echo "=== Playwright browsers ===" && \
    ls -la /app/pw-browsers

# Make port 8080 available
EXPOSE 8080

# Run worker.py when the container launches
CMD ["python", "-u", "/app/aiservice/worker.py"] 