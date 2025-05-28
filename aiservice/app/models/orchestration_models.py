from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class OrchestrationInput(BaseModel):
    source_type: str = Field(..., examples=["url", "pdf", "docx", "txt", "md"])
    source_identifier: str = Field(..., description="URL or filepath")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"])

class ContentBlock(BaseModel):
    # This is a generic content block, actual structure might vary slightly
    # depending on 'type' (e.g. text, math, code, image)
    # For V2.4, image blocks will have specific fields for the gallery
    type: str
    content: Optional[str] = None # For text, math, code
    original_source_identifier: Optional[str] = None # For image blocks, linking to processed_images_data
    gcs_url: Optional[str] = None # For image blocks
    alt_text: Optional[str] = None # For image blocks
    caption: Optional[str] = None # For image blocks
    llm_description: Optional[str] = None # For image blocks (e.g. from PDF multimodal)
    # Other image metadata like dimensions, mime_type can be added here or in processed_images_data

class ProcessedImageData(BaseModel):
    original_source_identifier: str
    gcs_url: str
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    llm_description: Optional[str] = None
    # Add other relevant fields: dimensions, mime_type, etc.

class OrchestrationOutput(BaseModel):
    status_code: str = Field(..., examples=["success", "partial_success", "failure_acquisition", "failure_image_processing", "failure_structuring", "unsupported_type"])
    source_identifier: str
    source_type: str
    processing_level_used: str
    extracted_title: Optional[str] = None
    is_long_article: bool = False
    original_content_blocks: List[ContentBlock] = []
    processed_images_data: Dict[str, ProcessedImageData] = Field(default_factory=dict, description="Dictionary mapping original_source_identifier to image metadata")
    error_message: Optional[str] = None 