# In aiservice/app/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Set
from pydantic import Field
import os

# --- Determine the path to the .env file relative to this settings.py file ---
# Directory where settings.py is located (aiservice/app/config)
_SETTINGS_DIR = os.path.dirname(os.path.abspath(__file__))
# Path to .env file (should be in aiservice/.env)
# So, go up two directories (config -> app -> aiservice) then find .env
_ENV_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(_SETTINGS_DIR)), ".env")

class Settings(BaseSettings):
    # Application settings
    app_name: str = "ThinkStash AI Service"
    debug_mode: bool = Field(default=False, description="Enable debug mode for more verbose logging.")

    # LLM Configuration - Focused on Gemini via OpenAI Compatibility Layer
    # This will load GEMINI_API_KEY from the .env file
    gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY", description="API key for Gemini models (used by OpenAI compatibility layer).")
    
    # Flag to explicitly use the Gemini via OpenAI compatibility layer strategy
    use_gemini_via_openai_compatibility: bool = Field(default=True, env="USE_GEMINI_VIA_OPENAI_COMPATIBILITY", description="Flag to enable Gemini via OpenAI compatibility layer.")
    
    # Model name for the text generation, as used by the OpenAI compatibility layer
    # This will load GEMINI_TEXT_MODEL_COMPAT from the .env file
    gemini_text_model_compat: str = Field(default="models/gemini-2.5-flash", env="GEMINI_TEXT_MODEL_COMPAT", description="Gemini text model for OpenAI compatibility layer.")
    
    # Base URL for the Gemini OpenAI compatibility endpoint
    # This will load GEMINI_COMPATIBILITY_BASE_URL from the .env file
    gemini_compatibility_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta/openai/", env="GEMINI_COMPATIBILITY_BASE_URL", description="Base URL for Gemini OpenAI compatibility.")

    # Fallback/general default LLM model (can be the same as gemini_text_model_compat if only using that)
    default_llm_model: str = Field(default="models/gemini-2.5-flash", env="DEFAULT_LLM_MODEL", description="Default LLM model name if not using compatibility layer or for other purposes. Ensure .env defines this if used differently.")
    
    # Multimodal model - align with your .env or set a sensible default
    default_multimodal_llm_model: str = Field(default="models/gemini-2.5-flash", env="DEFAULT_MULTIMODAL_MODEL_NAME", description="Default LLM for multimodal tasks.")

    # Optional: Keep OpenAI API key if you plan to use OpenAI models directly for some tasks
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY", description="Direct OpenAI API Key, if needed for other models.")

    # --- Commented out fields related to direct Google GenAI integration to avoid confusion ---
    # google_api_key: Optional[str] = Field(None, env="GOOGLE_API_KEY", description="API key for Google AI services (Gemini).")
    # default_llm_model: str = Field(default="gemini-1.5-flash-latest", env="DEFAULT_LLM_MODEL", description="Default LLM model for text generation/analysis. Ensure .env matches desired model.") 
    # default_multimodal_llm_model: str = Field(default="gemini-1.5-pro-latest", env="DEFAULT_MULTIMODAL_LLM_MODEL", description="Default LLM for multimodal tasks (e.g., vision).")

    # Service Behavior Flags
    use_llm_for_routing: bool = Field(default=False, description="Use LLM for routing (V2.4 style, should be False for V2.5 deterministic). Set to False for V2.5.")
    use_llm_for_image_analysis: bool = Field(default=False, env="USE_LLM_FOR_IMAGE_ANALYSIS", description="Enable LLM-based analysis (description, caption) for images in ImageProcessingService.")
    
    # GCS Configuration
    gcs_bucket_name: Optional[str] = Field(None, env="GCS_BUCKET_NAME", description="Google Cloud Storage bucket for storing images.")
    
    # Caching Configuration
    redis_host: Optional[str] = Field(default="localhost", env="REDIS_HOST")
    redis_port: Optional[int] = Field(default=6379, env="REDIS_PORT")
    redis_db: Optional[int] = Field(default=0, env="REDIS_DB")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    default_cache_ttl_seconds: int = Field(default=3600, env="DEFAULT_CACHE_TTL_SECONDS", description="Default TTL for general cached items in seconds (e.g., Redis).")
    
    # Web Acquisition Service Specific Caching
    web_html_cache_ttl_seconds: int = Field(default=3600, env="WEB_HTML_CACHE_TTL_SECONDS", description="TTL for in-memory HTML cache in WebAcquisitionService.")

    # Image Processing Service Specific Caching & Filters
    image_processing_cache_size: int = Field(default=256, env="IMAGE_PROCESSING_CACHE_SIZE", description="Max size for LRU cache in ImageProcessingService.")
    img_filter_min_dimension: int = Field(default=50, env="IMG_FILTER_MIN_DIMENSION", description="Min width/height for images to be kept.")
    img_filter_min_area: int = Field(default=5000, env="IMG_FILTER_MIN_AREA", description="Min area (width*height) for images.")
    img_filter_max_aspect_ratio_deviation: float = Field(default=4.0, env="IMG_FILTER_MAX_ASPECT_RATIO_DEVIATION", description="Max aspect ratio deviation for images.")
    
    img_filter_irrelevant_alt_text_exact: Set[str] = Field(default={
        "logo", "avatar", "icon", "profile", "banner", "ad", "advertisement", 
        "user", "default", "placeholder", "loading", "spinner", "spacer", "pixel",
        "figure", "image", "photo", "illustration", "diagram"
    }, description="Exact alt text matches for filtering images.")
    
    img_filter_irrelevant_alt_text_substrings: Set[str] = Field(default={
        "logo", "avatar", "icon", "profile", "banner", "advert", "promo", "social", "button", "rating", 
        "star", "user photo", "profile picture", "author bio", "site badge", "user badge", "blog logo",
        "decorative image", "background image"
    }, description="Substrings in alt text for filtering images.")

    img_filter_irrelevant_filename_url_segments: Set[str] = Field(default={
        "/logo", "/avatar", "/icon", "/banner", "/profile", "/badge", "/sprite", 
        "/spinner", "/loader", "/ads/", "/ad/", "/advert/", "pixel.gif", "spacer.gif",
        "/track", "/beacon", "gravatar.com", "/share_", "_share.", "/social_", "_social.",
        "feedburner.com", "doubleclick.net", "googlesyndication.com", "adservice.google.com",
        "feeds.feedburner.com", "ad.doubleclick.net", "stats.wordpress.com",
        "default-avatar", "default_avatar", "profile-pic", "profile_pic",
        "icon-", "logo-", "banner-", "-icon.", "-logo.", "-banner."
    }, description="URL/filename segments for filtering images.")

    # Performance & Timeouts
    default_request_timeout_seconds: int = Field(default=30, env="DEFAULT_REQUEST_TIMEOUT_SECONDS", description="Default timeout for external HTTP requests.")
    max_concurrent_tasks: int = Field(default=10, env="MAX_CONCURRENT_TASKS", description="Max concurrent tasks for parallel operations.")

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE_PATH, # Use the explicitly determined path
        env_file_encoding='utf-8', 
        extra='ignore', 
        case_sensitive=False # Important for .env variable names like GEMINI_API_KEY
    )

settings = Settings()

# Remove all debug prints

# Example of how to use:
# from aiservice.app.config.settings import settings
# if settings.debug_mode:
#     print("Running in debug mode")