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

# --- BlockNote Compliant Models ---

class InlineContent(BaseModel):
    type: str = Field(..., description="e.g., 'text', 'link'")
    text: str
    styles: Dict[str, Any] = Field(default_factory=dict)
    href: Optional[str] = Field(None, description="URL for 'link' type content")

class BlockProps(BaseModel):
    level: Optional[int] = Field(None, description="Heading level (1-6)")
    language: Optional[str] = Field(None, description="Language for code blocks")
    ordered: Optional[bool] = Field(None, description="For list blocks")
    url: Optional[str] = Field(None, description="URL for image blocks")
    caption: Optional[str] = Field(None, description="Caption for image blocks")
    # Add other props as needed, e.g., backgroundColor, textColor

class ContentBlock(BaseModel):
    id: str = Field(..., description="Unique ID for this block.")
    type: str = Field(..., description="BlockNote-compatible type (e.g., 'paragraph', 'heading', 'bulletListItem', 'image').")
    props: BlockProps = Field(default_factory=BlockProps)
    content: Union[List[InlineContent], str] = Field(default_factory=list, description="For text-based blocks, a list of InlineContent. For other blocks like 'image', this can be empty or hold simple content.")
    children: List['ContentBlock'] = Field(default_factory=list)
    
    # --- Deprecated/Legacy Fields for ThinkStash Backend ---
    # These are kept for reference during transition but are not part of the core BlockNote structure.
    # The data they hold should be mapped to the new structure.
    block_id: Optional[str] = Field(None, description="[DEPRECATED] Use id.")
    user_id: Optional[str] = Field(None, description="[DEPRECATED] Data is now scoped to the document/card.")
    document_id: Optional[str] = Field(None, description="[DEPRECATED] Data is now scoped to the document/card.")
    order_index: Optional[int] = Field(None, description="[DEPRECATED] Order is implicit in the list.")

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

    # AI Rewrite Process Specific Statuses (Task Progress Stages)
    REWRITE_PENDING = "rewrite_pending" # Initial state in DB before processing starts
    REWRITE_STARTED = "rewrite_started"
    REWRITE_SUMMARIZATION_AGENT_STARTED = "rewrite_summarization_agent_started"
    REWRITE_SUMMARIZATION_AGENT_PROCESSING = "rewrite_summarization_agent_processing"
    REWRITE_SUMMARIZATION_AGENT_COMPLETED = "rewrite_summarization_agent_completed"
    REWRITE_RECONSTRUCTION_STARTED = "rewrite_reconstruction_started"
    REWRITE_RECONSTRUCTION_COMPLETED = "rewrite_reconstruction_completed"
    REWRITE_SUCCESS = "rewrite_success" # Final success state for the rewrite task

    # AI Rewrite Process Specific Failure Statuses
    REWRITE_FAILED_EMPTY_INPUT = "rewrite_failed_empty_input"
    REWRITE_FAILED_SUMMARIZATION_AGENT_ERROR = "rewrite_failed_summarization_agent_error"
    REWRITE_FAILED_SUMMARIZATION_OUTPUT_PARSING = "rewrite_failed_summarization_output_parsing"
    REWRITE_FAILED_RECONSTRUCTION = "rewrite_failed_reconstruction"
    REWRITE_FAILED_UNHANDLED_EXCEPTION = "rewrite_failed_unhandled_exception"
    REWRITE_FAILED_DB_UPDATE = "rewrite_failed_db_update" # For when DB updates fail within the crew manager

class OrchestrationOutput(BaseModel):
    status_code: str = Field(..., examples=["success", "partial_success", "failure_acquisition", "failure_image_processing", "failure_structuring", "unsupported_type"])
    user_id: Optional[str] = Field(default=None, description="User identifier for the entire orchestration, if available.")
    document_id: Optional[str] = Field(default=None, description="Document identifier (job_id) for the entire orchestration, if available.")
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
    card_id: Optional[str] = Field(None, description="The ID of the newly created KnowledgeCard on success.") 