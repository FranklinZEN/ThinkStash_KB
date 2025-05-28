# In aiservice/app/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from pydantic import Field

class Settings(BaseSettings):
    # Application settings
    app_name: str = "ThinkStash AI Service"
    debug_mode: bool = Field(default=False, description="Enable debug mode for more verbose logging.")

    # LLM Configuration
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    # anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    # vertex_ai_project: Optional[str] = Field(None, env="VERTEX_AI_PROJECT")
    # vertex_ai_location: Optional[str] = Field(None, env="VERTEX_AI_LOCATION")
    default_llm_model: str = Field(default="gpt-4o-mini", description="Default LLM model for text generation/analysis.")
    default_multimodal_llm_model: str = Field(default="gpt-4o", description="Default LLM for multimodal tasks (e.g., vision).")

    # Service Behavior Flags
    use_llm_for_routing: bool = Field(default=False, description="Use LLM for routing (V2.4 style, should be False for V2.5 deterministic). Set to False for V2.5.")
    use_llm_for_image_analysis: bool = Field(default=False, description="Enable LLM-based analysis (description, caption) for images in ImageProcessingService.")
    # use_nougat_for_pdf: bool = Field(default=False, description="Enable Nougat for PDF parsing (if available and configured).")

    # GCS Configuration
    gcs_bucket_name: Optional[str] = Field(None, env="GCS_BUCKET_NAME", description="Google Cloud Storage bucket for storing images.")
    # gcs_project_id: Optional[str] = Field(None, env="GCS_PROJECT_ID") # If needed explicitly by GCS client

    # Caching Configuration (e.g., Redis)
    redis_host: Optional[str] = Field(default="localhost", env="REDIS_HOST")
    redis_port: Optional[int] = Field(default=6379, env="REDIS_PORT")
    redis_db: Optional[int] = Field(default=0, env="REDIS_DB")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    cache_ttl_seconds: int = Field(default=3600, description="Default TTL for cached items in seconds.")

    # Performance & Timeouts
    default_request_timeout_seconds: int = Field(default=30, description="Default timeout for external HTTP requests.")
    max_concurrent_tasks: int = Field(default=10, description="Max concurrent tasks for parallel operations.")

    # For pydantic-settings to load from .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

# Global way to access settings
# This instance will be created once and can be imported by other modules.
settings = Settings()

# Example of how to use:
# from aiservice.app.config.settings import settings
# if settings.debug_mode:
#     print("Running in debug mode")