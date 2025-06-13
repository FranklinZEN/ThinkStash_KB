# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/bin/ms-playwright # Standard path for playwright install

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for Playwright and other libraries
RUN apt-get update && apt-get install -y \
    libmagic1 \
    wget \
    # Playwright-specific dependencies
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY ./aiservice/requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and their OS dependencies
RUN playwright install --with-deps chromium

# Copy the entire aiservice application code into the /app directory
COPY ./aiservice/ /app/

# Make port 8080 available for the health check server
EXPOSE 8080

# Run worker.py when the container launches.
# It's now in the root of WORKDIR (/app)
CMD ["python", "-u", "worker.py"] 