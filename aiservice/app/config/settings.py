from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    gemini_api_key: str 
    openai_api_key: str | None = None # Optional, for fallback or other agents
    openai_model_name: str = "gpt-4o-mini" # Default value, will be overridden by .env
    DATABASE_URL: str

    # For FastAPI/Uvicorn if needed later
    # host: str = "0.0.0.0"
    # port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

settings = Settings() 