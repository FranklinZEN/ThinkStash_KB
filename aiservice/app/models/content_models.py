# File: aiservice/app/models/content_models.py
"""Pydantic models for standardized content representation across the AI service."""

from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Union, Any # Any for bytes in older Pydantic, or use bytes directly.

# --- Standardized Image Reference Models (Input to TS-AI-4.5) ---
# As per TS-AI-4 & TS-AI-4.5 Development Plan - V1.2, "Standardized Agent Output Format for TS-AI-4"

class ImageRefUrl(BaseModel):
    """Reference to an image by its web URL."""
    type: str = Field(default="url", Literal="url") # Literal might need Pydantic v1.9+ or Pydantic v2
    url: HttpUrl
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    source_scope: Optional[str] = None # New: e.g., "main_content", "full_page_heuristic" (from WebContentFetcherTool)
    context_before: Optional[str] = None # New: Text snippet before the image
    context_after: Optional[str] = None  # New: Text snippet after the image

class ImageRefData(BaseModel):
    """Reference to an image, with data stored as a Base64 encoded string."""
    type: str = Field(default="data", Literal="data") 
    data_base64_string: str # Changed from data_bytes: bytes
    filename_hint: Optional[str] = None
    mime_type_hint: Optional[str] = None
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    source_scope: Optional[str] = Field(default="file_embedded")

# --- Standardized Agent Output Model for Content Acquisition (TS-AI-4) ---
# Output of TS-AI-4, Input for image_references to TS-AI-4.5
class AcquiredContent(BaseModel):
    """ 
    Standardized output from the ContentAcquisitionAgent (TS-AI-4).
    This structure is passed to subsequent agents in the processing crew (e.g., ImageProcessingAgent).
    """
    # Status values based on V1.2 plan for the ContentAcquisitionAgent output
    status: str  # Expected: "success", "strict_paywall_domain", "suspected_paywall_patterns", 
                 # "unsupported_url_type", "unsupported_file_type", 
                 # "fetch_error", "parse_error", "agent_error", 
                 # "pdf_requires_manual_review_for_layout"
    input_type: str # "url" or "file"
    source_identifier: str # The original URL or filename
    
    final_url_if_redirected: Optional[HttpUrl] = None # Specific to URL fetching
    page_title: Optional[str] = None # Title extracted from web page or document metadata
    extracted_text: Optional[str] = None
    
    # image_references is a key input for the ImageProcessingAgent (TS-AI-4.5)
    image_references: Optional[List[Union[ImageRefUrl, ImageRefData]]] = None
    
    error_message: Optional[str] = None

    # Consider adding a field for raw PDF bytes if status is "pdf_requires_manual_review_for_layout"
    # to allow a potential future manual review or different processing path.
    # For now, this is not explicitly in the V1.2 AcquiredContent model, but a thought.
    # pdf_bytes_for_review: Optional[bytes] = None 

# --- Standardized Output Model for Image Processing (TS-AI-4.5) ---
# As per TS-AI-4 & TS-AI-4.5 Development Plan - V1.2, for ImageProcessingAgent output
# This will be the primary image input for ContentStructuringAgent (TS-AI-X)
class ProcessedImageData(BaseModel):
    """
    Standardized data for an image after it has been processed by TS-AI-4.5 
    (e.g., downloaded if from URL, and GCS URL obtained).
    This is a key input for the ContentStructuringAgent (TS-AI-X).
    """
    type: str = Field(description="Indicates if the original source was 'url' or 'data'. Helps trace origin (e.g., 'url_processed', 'data_processed').")
    gcs_url: str = Field(description="The GCS URL where the image is (or will be) stored.")
    
    # Original source details, carried over for reference and context
    original_source_identifier: Union[HttpUrl, str] = Field(description="Original URL if from web, or original filename if from file.")
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    
    # Contextual information carried over from ContentAcquisitionAgent
    source_scope: Optional[str] = Field(default=None, description="Scope where image was found (e.g., 'main_content', 'full_page_heuristic', 'file_embedded', 'markdown_link').")
    context_before: Optional[str] = Field(default=None, description="Text snippet found immediately before the image in its original context.")
    context_after: Optional[str] = Field(default=None, description="Text snippet found immediately after the image in its original context.")

    # Properties determined during processing by TS-AI-4.5 or its uploader tool
    detected_mime_type: Optional[str] = Field(default=None, description="MIME type detected/confirmed during download/processing.")
    width: Optional[int] = Field(default=None, description="Image width in pixels, if determined.")
    height: Optional[int] = Field(default=None, description="Image height in pixels, if determined.")
    
    # Status of processing this specific image by TS-AI-4.5
    processing_status: str # e.g., "success", "download_failed", "upload_failed", "unsupported_format_for_upload", "api_error"
    error_message: Optional[str] = None

# ... (Potentially other shared models for the application if needed) ...