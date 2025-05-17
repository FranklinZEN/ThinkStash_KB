# AI Service for Thinkstash

This directory contains the Python-based AI microservice for Thinkstash, built using FastAPI and CrewAI.

## Project Structure

- `app/`: Main application code
  - `agents/`: CrewAI agents
  - `tools/`: CrewAI tools
  - `tasks/`: CrewAI tasks
  - `crews/`: CrewAI crew definitions
  - `api/`: FastAPI endpoints, routers, and schemas
    - `routers/`: API routers
    - `schemas/`: Pydantic schemas for API requests/responses
  - `core/`: Configuration, shared utilities, GCS client wrappers, etc.
  - `config/`: (Existing) Pydantic settings for environment variables.
  - `services/`: Business logic not directly part of agents/crews.
  - `utils/`: (Existing) General utility functions.
  - `main.py`: FastAPI application entry point.
- `tests/`: Unit and integration tests for the AI service.
- `scripts/`: Utility scripts for development or deployment tasks.
- `.venv/`: Python virtual environment (gitignored).
- `requirements.txt`: Python dependencies.
- `.env`: Environment variables (gitignored) - loaded by `app/config/settings.py`.
- `.gitignore`: Specifies files to be ignored by Git within the aiservice directory.
- `README.md`: This file.

## Setup

1.  Navigate to the `aiservice` directory.
2.  Create a Python virtual environment: `python -m venv .venv`
3.  Activate the virtual environment: `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows).
4.  Install dependencies: `pip install -r requirements.txt`
5.  Create a `.env` file in the `aiservice` directory and populate it with necessary API keys (e.g., `OPENAI_API_KEY`). Refer to `app/config/settings.py` for required variables.

## Running Locally

From the `aiservice` directory (with virtual environment activated):

`uvicorn app.main:app --reload --host 0.0.0.0 --port 8001`

(Adjust port if 8001 is in use or if `app/main.py` specifies a different one via config). 