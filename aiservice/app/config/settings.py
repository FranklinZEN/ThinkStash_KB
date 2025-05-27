# In aiservice/app/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str
    openai_default_model_name: str = "gpt-4o-mini"
    openai_advanced_model_name: str = "gpt-4o" # Or your preferred advanced model
    gemini_api_key: str | None = None

    gcp_project_id: str | None = None
    gcs_bucket_name: str | None = None
    google_application_credentials: str | None = None # Path to JSON key file

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

settings = Settings()