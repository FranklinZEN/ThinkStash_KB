import os
from dotenv import load_dotenv, find_dotenv

# Determine the path to the .env file in the `aiservice` directory.
# This assumes this config.py is in aiservice/app/config.py
# So, aiservice_dir is one level up from app, then find .env in aiservice_dir.
# More robustly, find_dotenv can search upwards from the current file or CWD.

# Load the .env file from the `aiservice` directory if it exists.
# usecwd=True makes find_dotenv look in the current working directory first, then search upwards.
# If your aiservice/.env is at the root of where you run the script, this should work.
# If the script is run from /e:/ThinkStash, and .env is in /e:/ThinkStash/aiservice/.env
# then find_dotenv(filename='aiservice/.env', usecwd=True) might be more direct or adjust path.

# Let's try to find it relative to this file, assuming standard project structure:
# aiservice/
#   app/
#     config.py
#   .env
# Current file: /e:/ThinkStash/aiservice/app/config.py
# Workspace root: /e:/ThinkStash
# .env location: /e:/ThinkStash/aiservice/.env

# Construct path to .env in aiservice directory relative to workspace root
aiservice_dotenv_path = os.path.join(os.getenv("WORKSPACE_FOLDER", "/e:/ThinkStash"), "aiservice", ".env")

# Check if the .env file specified by absolute path exists and load it
if os.path.exists(aiservice_dotenv_path):
    load_dotenv(dotenv_path=aiservice_dotenv_path, override=True)
    print(f"Loaded .env from: {aiservice_dotenv_path}")
elif os.path.exists(os.path.join(os.getcwd(), ".env")):
    # Fallback to .env in current working directory if the specific one is not found
    load_dotenv(override=True)
    print(f"Loaded .env from current working directory: {os.getcwd()}/.env")
elif find_dotenv(raise_error_if_not_found=False):
    # Fallback to dotenv's default upward search if specific paths fail
    load_dotenv(override=True)
    print(f"Loaded .env using find_dotenv(): {find_dotenv()}")
else:
    print("Warning: .env file not found. Environment variables should be set manually.")

# --- Accessor functions for configurations ---

def get_env_variable(var_name: str, default_value: str = None) -> str | None:
    """Fetches an environment variable.

    Args:
        var_name: The name of the environment variable.
        default_value: The default value to return if the variable is not found.

    Returns:
        The value of the environment variable, or the default value.
    """
    return os.environ.get(var_name, default_value)

def get_openai_api_key() -> str | None:
    """Retrieves the OpenAI API key from environment variables."""
    return get_env_variable("OPENAI_API_KEY")

def get_openai_default_model_name() -> str:
    """Retrieves the default OpenAI model name."""
    return get_env_variable("OPENAI_DEFAULT_MODEL_NAME", "gpt-4o-mini")

def get_openai_advanced_model_name() -> str:
    """Retrieves the advanced OpenAI model name for more complex tasks."""
    return get_env_variable("OPENAI_ADVANCED_MODEL_NAME", "gpt-4o")

def get_gemini_api_key() -> str | None:
    """Retrieves the Gemini API key from environment variables."""
    return get_env_variable("GEMINI_API_KEY")

def get_gcp_project_id() -> str | None:
    """Retrieves the Google Cloud Project ID from environment variables."""
    return get_env_variable("GCP_PROJECT_ID")

def get_gcs_bucket_name() -> str | None:
    """Retrieves the GCS Bucket Name from environment variables."""
    return get_env_variable("GCS_BUCKET_NAME")

def get_google_app_credentials() -> str | None:
    """Retrieves the path to Google Application Credentials JSON file from environment variables."""
    # This is usually set directly as an environment variable that Google libraries pick up.
    # However, if you store the *path* in .env, this function can retrieve that path.
    return get_env_variable("GOOGLE_APPLICATION_CREDENTIALS")

# Example of how these might be used (for testing this config file itself)
if __name__ == '__main__':
    print("--- Configuration Test ---")
    print(f"OpenAI API Key: {get_openai_api_key()}")
    print(f"OpenAI Default Model: {get_openai_default_model_name()}")
    print(f"OpenAI Advanced Model: {get_openai_advanced_model_name()}")
    print(f"Gemini API Key: {get_gemini_api_key()}")
    print(f"GCP Project ID: {get_gcp_project_id()}")
    print(f"GCS Bucket Name: {get_gcs_bucket_name()}")
    print(f"Google App Credentials Path: {get_google_app_credentials()}")
    # Note: The GCS client library typically uses GOOGLE_APPLICATION_CREDENTIALS directly from the environment.
    # This function get_google_app_credentials() would be useful if your app needs the *path string* itself for some reason. 