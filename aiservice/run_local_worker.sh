#!/bin/bash
# In aiservice/run_local_worker.sh

# This script provides a convenient way to run the Python AI worker locally.
# It loads the required environment variables from the `.env.worker` file
# and then executes the main worker script.

# Set the script to exit immediately if a command exits with a non-zero status.
set -e

# Change to the directory where the script is located to ensure correct file paths.
cd "$(dirname "$0")"

# Load environment variables from .env.worker if it exists.
# This allows for easy configuration of secrets and settings without hardcoding them.
if [ -f .env.worker ]; then
  echo "Loading environment variables from .env.worker..."
  # Export the variables so they are available to the python script.
  # The grep command filters out comments and empty lines.
  export $(cat .env.worker | grep -v '^#' | grep -v '^$' | xargs)
  echo "Environment variables loaded."
else
  echo "Warning: .env.worker file not found. The worker might not have the necessary configuration."
fi

# Run the worker script directly using Python.
# It's assumed that 'worker.py' is in the same directory and contains
# the main execution block to start the service.
echo "Starting the AI worker..."
python worker.py 