# In aiservice/app/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from pydantic import Field
import os

class Settings(BaseSettings):
    # Application settings
    app_name: str = "ThinkStash AI Service"
    debug_mode: bool = Field(default=False, description="Enable debug mode for more verbose logging.")

    # LLM Configuration
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    default_llm_model: str = Field(default="gpt-4o-mini", description="Default LLM model for text generation/analysis.") # Loads from DEFAULT_LLM_MODEL in .env
    default_multimodal_llm_model: str = Field(default="gpt-4o", description="Default LLM for multimodal tasks (e.g., vision).") # Loads from DEFAULT_MULTIMODAL_MODEL_NAME in .env

    # Gemini Configuration (REMOVED/COMMENTED)
    # gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY")
    # gemini_text_model: str = Field(default="models/gemini-1.5-flash-lite", env="GEMINI_TEXT_MODEL", description="Gemini model for text generation/analysis.")
    # gemini_multimodal_model: str = Field(default="models/gemini-1.5-flash", env="GEMINI_MULTIMODAL_MODEL", description="Gemini model for multimodal tasks.")

    # Service Behavior Flags
    use_llm_for_routing: bool = Field(default=False, description="Use LLM for routing (V2.4 style, should be False for V2.5 deterministic). Set to False for V2.5.")
    use_llm_for_image_analysis: bool = Field(default=False, description="Enable LLM-based analysis (description, caption) for images in ImageProcessingService.")
    
    # GCS Configuration
    gcs_bucket_name: Optional[str] = Field(None, env="GCS_BUCKET_NAME", description="Google Cloud Storage bucket for storing images.")
    
    # Caching Configuration (e.g., Redis)
    redis_host: Optional[str] = Field(default="localhost", env="REDIS_HOST")
    redis_port: Optional[int] = Field(default=6379, env="REDIS_PORT")
    redis_db: Optional[int] = Field(default=0, env="REDIS_DB")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    cache_ttl_seconds: int = Field(default=3600, description="Default TTL for cached items in seconds.")

    # Performance & Timeouts
    default_request_timeout_seconds: int = Field(default=30, description="Default timeout for external HTTP requests.")
    max_concurrent_tasks: int = Field(default=10, description="Max concurrent tasks for parallel operations.")

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8', 
        extra='ignore', 
        case_sensitive=False
    )

settings = Settings()

# Remove all debug prints

# Example of how to use:
# from aiservice.app.config.settings import settings
# if settings.debug_mode:
#     print("Running in debug mode")