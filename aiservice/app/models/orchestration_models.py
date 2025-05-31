from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from .pipeline_models import DocumentMetadata, EnrichedImageMetadata
import enum

class OrchestrationInput(BaseModel):
    source_identifier: str = Field(..., description="URL or filepath")
    source_type: Optional[str] = Field(default=None, examples=["url", "pdf", "docx", "txt", "md"])
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"])
    job_id: Optional[str] = Field(default=None, description="Unique job identifier")
    user_id: Optional[str] = Field(default=None, description="User identifier")
    output_format_options: Optional[Dict[str, Any]] = Field(default=None, description="Options for output formatting")

class ContentBlock(BaseModel):
    block_id: str = Field(..., description="Unique ID for this block, inherited from PreliminaryBlock.")
    tmp_id: Optional[str] = Field(None, description="Temporary ID used during processing, can be same as block_id or different.")
    user_id: Optional[str] = Field(None, description="Identifier of the user associated with this content block.")
    document_id: Optional[str] = Field(None, description="Identifier of the source document from DocumentMetadata.")
    type: str = Field(..., description="Type of content (e.g., 'text', 'heading', 'list', 'image', 'code_snippet', 'math_text', 'table').")
    order_index: Optional[int] = Field(None, description="Sequential order of the block in the reconstructed content.")
    
    # Common fields, often populated
    content: Optional[str] = Field(None, description="Primary text content for types like 'text', 'heading', 'code_snippet', 'math_text', 'table' (e.g., HTML table).")
    page_number: Optional[int] = Field(None, description="Page number in the original document.")
    bbox: Optional[List[float]] = Field(None, description="Bounding box [x0, y0, x1, y1] on the page, if applicable.")

    # Fields specific to type: 'heading'
    level: Optional[int] = Field(None, description="For 'heading' type, the heading level (1-6).")

    # Fields specific to type: 'code_snippet'
    language: Optional[str] = Field(None, description="For 'code_snippet' type, the programming language.")

    # Fields specific to type: 'list'
    items: Optional[List[Union[str, Dict[str, Any]]]] = Field(None, description="For 'list' type, holds list item contents. Items can be simple strings or nested structures for complex/nested lists.")
    ordered: Optional[bool] = Field(None, description="For 'list' type, true if the list is ordered, false if unordered.")
    list_start_number: Optional[int] = Field(None, description="For ordered 'list' type, the starting number if not 1.")

    # Fields specific to type: 'image'
    # These fields are populated by looking up EnrichedImageMetadata using image_id_ref
    image_id_ref: Optional[str] = Field(None, description="For 'image' type, reference to EnrichedImageMetadata.image_id.")
    gcs_url: Optional[str] = Field(None, description="For 'image' type, URL of the image in GCS.")
    alt_text: Optional[str] = Field(None, description="For 'image' type, original or LLM-refined alt text.")
    caption: Optional[str] = Field(None, description="For 'image' type, original or LLM-refined caption.")
    llm_description: Optional[str] = Field(None, description="For 'image' type, LLM-generated description of the image content.")
    width: Optional[int] = Field(None, description="For 'image' type, image width in pixels.")
    height: Optional[int] = Field(None, description="For 'image' type, image height in pixels.")
    
    # Ensure no old image fields like original_source_identifier are lingering if they are now part of EnrichedImageMetadata
    # The plan was to have ContentStructuringService create 'image' ContentBlock by finding matching EnrichedImageMetadata.
    # So, ContentBlock itself stores the resolved image details.

class OrchestrationStatusCodeEnum(str, enum.Enum):
    """Standardized status codes for orchestration and processing."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    
    ERROR_UNKNOWN = "error_unknown"
    ERROR_CREW_EXECUTION_FAILED = "error_crew_execution_failed"
    ERROR_UNEXPECTED_OUTPUT_TYPE = "error_unexpected_output_type"
    ERROR_CONTENT_BLOCK_VALIDATION = "error_content_block_validation"
    ERROR_NO_OUTPUT_FROM_CREW = "error_no_output_from_crew"
    
    FAILURE_ACQUISITION = "failure_acquisition"
    FAILURE_IMAGE_PROCESSING = "failure_image_processing"
    FAILURE_STRUCTURING = "failure_structuring"
    UNSUPPORTED_TYPE = "unsupported_type"

class OrchestrationOutput(BaseModel):
    status_code: str = Field(..., examples=["success", "partial_success", "failure_acquisition", "failure_image_processing", "failure_structuring", "unsupported_type"])
    source_identifier: str
    source_type: str
    user_id: Optional[str] = Field(None, description="Identifier of the user who initiated the request, mirrored from input or document_metadata.")
    document_id: Optional[str] = Field(None, description="Unique identifier for the processed document instance, mirrored from document_metadata.")
    processing_level_used: str
    extracted_title: Optional[str] = None
    is_long_article: bool = False
    original_content_blocks: List[ContentBlock] = []
    processed_images_data: Dict[str, EnrichedImageMetadata] = Field(default_factory=dict, description="Dictionary mapping image_id to EnrichedImageMetadata.")
    document_metadata: Optional[DocumentMetadata] = Field(None, description="Comprehensive metadata about the processed document.")
    error_message: Optional[str] = None 