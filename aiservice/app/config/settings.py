from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str
    openai_model_name: str = "gpt-4o-mini" # Default value, will be overridden by .env
    gemini_api_key: str | None = None # Optional Gemini API key

    # For FastAPI/Uvicorn if needed later
    # host: str = "0.0.0.0"
    # port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

settings = Settings() 