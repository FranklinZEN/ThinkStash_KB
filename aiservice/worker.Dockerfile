# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed by your packages
RUN apt-get update && apt-get install -y libmagic1 && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file to leverage Docker cache
COPY ./aiservice/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY ./aiservice/ .

# List the contents of the /app directory to help with debugging
RUN ls -la /app
RUN ls -la /app/aiservice

# Command to run the application
CMD ["python", "-u", "worker.py"] 