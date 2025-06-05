# In aiservice/app/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Set, Any
from pydantic import Field
import os

# --- Determine the path to the .env file relative to this settings.py file ---
# Directory where settings.py is located (aiservice/app/config)
_SETTINGS_DIR = os.path.dirname(os.path.abspath(__file__))
# Path to .env file (should be in the project root, one level above the 'aiservice' directory)
# aiservice/app/config -> aiservice/app -> aiservice -> project_root
_ENV_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_SETTINGS_DIR))), ".env")

class WebServiceSpecificSettings(BaseSettings):
    # Copied from MockWebServiceSettings in web_service.py and defaults from WebService constructor
    default_user_agent: str = Field(default="ThinkStashAI/1.0", env="WEB_DEFAULT_USER_AGENT")
    trafilatura_include_comments: bool = Field(default=False, env="WEB_TRAFILATURA_INCLUDE_COMMENTS")
    trafilatura_include_tables: bool = Field(default=True, env="WEB_TRAFILATURA_INCLUDE_TABLES")
    trafilatura_favor_recall: bool = Field(default=True, env="WEB_TRAFILATURA_FAVOR_RECALL")
    trafilatura_deduplicate: bool = Field(default=True, env="WEB_TRAFILATURA_DEDUPLICATE")
    
    # Playwright specific settings
    use_playwright_for_image_filtering: bool = Field(default=True, env="WEB_USE_PLAYWRIGHT_FOR_IMAGE_FILTERING", description="Enable Playwright for advanced image filtering by rendered dimensions.")
    min_image_width: int = Field(default=300, env="WEB_MIN_IMAGE_WIDTH", description="Minimum rendered width for an image to be included (if Playwright is enabled).")
    min_image_height: int = Field(default=75, env="WEB_MIN_IMAGE_HEIGHT", description="Minimum rendered height for an image to be included (if Playwright is enabled).")
    min_image_area: int = Field(default=22500, env="WEB_MIN_IMAGE_AREA", description="Minimum rendered area (width*height) for an image to be included (if Playwright is enabled).")
    playwright_page_load_timeout_ms: int = Field(default=30000, env="WEB_PLAYWRIGHT_PAGE_LOAD_TIMEOUT_MS", description="Timeout for Playwright page.goto() in milliseconds.")
    playwright_network_idle_timeout_ms: int = Field(default=10000, env="WEB_PLAYWRIGHT_NETWORK_IDLE_TIMEOUT_MS", description="Timeout for Playwright page.wait_for_load_state('networkidle') in milliseconds.")
    minimal_content_length_threshold: int = Field(default=500, env="WEB_MINIMAL_CONTENT_LENGTH_THRESHOLD", description="Minimum length of extracted content to be considered non-minimal for paywall detection.")

    stop_processing_heading_texts: Set[str] = Field(
        default_factory=lambda: {
            "related articles", "most popular", "comments", "further reading", 
            "posted on", "share this article", "leave a comment", "you might also like", 
            "related posts", "keep reading", "next article", "previous article", 
            "also on", "more from", "recommended for you", "explore more", "sign up",
            "acknowledgements", "about the author", "about the authors"
        },
        env="WEB_STOP_PROCESSING_HEADING_TEXTS",
        description="Set of lowercase heading texts that signal the end of main content."
    )

    model_config = SettingsConfigDict(
        env_prefix='AISERVICE_', # Optional: prefix for environment variables to avoid collisions
        env_file=_ENV_FILE_PATH,
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False
    )

class Settings(BaseSettings):
    # Application settings
    app_name: str = "ThinkStash AI Service"
    debug_mode: bool = Field(default=False, description="Enable debug mode for more verbose logging.")

    # Database URL (for PostgreSQL)
    database_url: Optional[str] = Field(None, env="DATABASE_URL", description="PostgreSQL database connection URL.")

    # LLM Configuration - Focused on Gemini via OpenAI Compatibility Layer
    # This will load GEMINI_API_KEY from the .env file
    gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY", description="API key for Gemini models (used by OpenAI compatibility layer).")
    
    # Flag to explicitly use the Gemini via OpenAI compatibility layer
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
    gcs_concurrent_upload_limit: int = Field(default=5, env="GCS_CONCURRENT_UPLOAD_LIMIT", description="Limit for concurrent GCS uploads in ImageProcessingService.")
    img_filter_min_dimension: int = Field(default=50, env="IMG_FILTER_MIN_DIMENSION", description="Min width/height for images to be kept (legacy, prefer specific width/height).")
    img_filter_min_width_px: int = Field(default=75, env="IMG_FILTER_MIN_WIDTH_PX", description="Minimum width in pixels for an image to be processed.")
    img_filter_min_height_px: int = Field(default=75, env="IMG_FILTER_MIN_HEIGHT_PX", description="Minimum height in pixels for an image to be processed.")
    img_filter_min_area: int = Field(default=5000, env="IMG_FILTER_MIN_AREA", description="Min area (width*height) for images.")
    img_filter_max_aspect_ratio_deviation: float = Field(default=999.0, env="IMG_FILTER_MAX_ASPECT_RATIO_DEVIATION", description="Max aspect ratio deviation for images.")
    
    img_filter_irrelevant_alt_text_exact: Set[str] = Field(default={
        "icon", "logo", "avatar", "profile", "button", "spinner", "loading", "pixel", "spacer", "ad", "advertisement"
    }, description="Exact alt text matches for filtering images.")
    
    img_filter_irrelevant_alt_text_substrings: Set[str] = Field(default={
        "icon", "logo", "avatar", "profile", "button", "advert", "social", "badge", "promo", "rating", "user photo", "profile picture", "thumbnail"
    }, description="Substrings in alt text for filtering images.")

    img_filter_irrelevant_filename_url_segments: Set[str] = Field(default={
        "/icon", "/logo", "/avatar", "/profile", "/button", "/badge", "/sprite", 
        "/spinner", "/loader", "/ads/", "/ad/", "pixel.gif", "spacer.gif", 
        "/social_", "_social.", "gravatar.com", "default-avatar", "profile-pic", 
        "-icon.", "-logo.", "/thumb/", "_thumb.", "avatar-", "/avatars/", "/users/",
        "thumbnail"
    }, description="URL/filename segments for filtering images.")

    # Performance & Timeouts
    default_request_timeout_seconds: int = Field(default=30, env="DEFAULT_REQUEST_TIMEOUT_SECONDS", description="Default timeout for external HTTP requests.")
    max_concurrent_tasks: int = Field(default=10, env="MAX_CONCURRENT_TASKS", description="Max concurrent tasks for parallel operations.")

    # Nested WebServiceSpecificSettings
    web_service: WebServiceSpecificSettings = Field(default_factory=WebServiceSpecificSettings)

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE_PATH, # Use the explicitly determined path
        env_file_encoding='utf-8', 
        extra='ignore', 
        case_sensitive=False # Important for .env variable names like GEMINI_API_KEY
    )

settings = Settings()

# --- Add get_crew_llm method to Settings class ---
def get_crew_llm(self: Settings) -> Any: # Using Any for now, will be ChatOpenAI or similar
    """Returns a CrewAI/Langchain compatible LLM client based on settings."""
    if self.use_gemini_via_openai_compatibility:
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY must be set in .env when using Gemini via OpenAI compatibility.")
        
        # Ensure the langchain-openai package is installed and import ChatOpenAI
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai package not found. "
                "Please install it with `pip install langchain-openai` to use Gemini via OpenAI compatibility."
            )
        
        print(f"[Settings] Initializing LLM for CrewAI: Gemini via OpenAI compatibility.")
        print(f"[Settings]   API Key: {'*' * (len(self.gemini_api_key) - 4) + self.gemini_api_key[-4:] if self.gemini_api_key else 'Not Set'}")
        print(f"[Settings]   Model: {self.gemini_text_model_compat}")
        print(f"[Settings]   Base URL: {self.gemini_compatibility_base_url}")

        # For CrewAI, it's common to pass the model instance directly.
        # The ChatOpenAI client handles the API key via environment variable OPENAI_API_KEY by default,
        # but when using a custom base_url for Gemini, we might need to pass it explicitly or ensure
        # the environment is set up in a way it expects for custom providers.
        # CrewAI/Langchain typically expect OPENAI_API_KEY, so we set it temporarily if needed.
        # However, for Google's OpenAI-compatible endpoint, the key is passed in the Authorization header.
        # langchain-openai ChatOpenAI should handle this if base_url is set correctly and api_key is provided.
        
        llm_params = {
            "model_name": self.gemini_text_model_compat,
            "openai_api_base": self.gemini_compatibility_base_url,
            "openai_api_key": self.gemini_api_key,
            "temperature": 0.2, # Default temperature, can be made configurable
             # "max_tokens": 2048, # Optional: set a default max_tokens
        }
        
        # Remove None-valued keys to avoid issues with ChatOpenAI constructor
        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        try:
            llm = ChatOpenAI(**llm_params)
            print("[Settings] ChatOpenAI client for Gemini compatibility initialized successfully.")
            return llm
        except Exception as e:
            print(f"[Settings] Error initializing ChatOpenAI for Gemini: {e}")
            raise ValueError(f"Failed to initialize ChatOpenAI for Gemini compatibility: {e}")

    else:
        # Placeholder for other LLM configurations if needed in the future
        # For now, this path means direct OpenAI or another LLM, which needs specific setup.
        print(f"[Settings] WARN: Gemini via OpenAI compatibility is disabled. Attempting fallback or other LLM config.")
        if self.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                raise ImportError(
                    "langchain-openai package not found. Please install it with `pip install langchain-openai`."
                )
            print(f"[Settings] Initializing direct OpenAI LLM: {self.default_llm_model}")
            # This would be a direct OpenAI call if openai_api_key is set and use_gemini_via_openai_compatibility is False
            return ChatOpenAI(model_name=self.default_llm_model, openai_api_key=self.openai_api_key, temperature=0.2)
        else:
            raise ValueError(
                "LLM configuration error: use_gemini_via_openai_compatibility is False, "
                "and no other LLM provider (e.g., direct OpenAI API key) is configured."
            )

# Bind the method to the class
Settings.get_crew_llm = get_crew_llm

# Remove all debug prints

# Example of how to use:
# from aiservice.app.config.settings import settings
# if settings.debug_mode:
#     print("Running in debug mode")