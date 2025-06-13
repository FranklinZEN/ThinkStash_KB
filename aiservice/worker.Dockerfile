# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/bin/ms-playwright

# Set the working directory in the container
WORKDIR /app

# --- INSTALLATION & DEBUGGING STEPS ---
# By separating these RUN commands, we can pinpoint failures in Cloud Build.

# STEP 1: Update package lists
RUN apt-get update

# STEP 2: Install system dependencies.
# A comprehensive list is used to ensure Playwright's headless browser can run reliably.
RUN apt-get install -y --no-install-recommends \
    libmagic1 \
    wget \
    ca-certificates \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
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

# STEP 3: Copy and install Python requirements
COPY ./aiservice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# STEP 4: Install only the chromium browser binaries.
RUN playwright install chromium

# --- FINAL APPLICATION SETUP ---

# Copy the entire aiservice application code into a subdirectory named 'aiservice'
COPY ./aiservice /app/aiservice

# Add the root /app directory to the PYTHONPATH.
# This allows Python to find the 'aiservice' module.
ENV PYTHONPATH=/app

# Make port 8080 available for the health check server
EXPOSE 8080

# Run the 'worker' module from within the 'aiservice' package.
# Using -m ensures the Python path is handled correctly for a package.
CMD ["python", "-u", "-m", "aiservice.worker"] 