from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from .pipeline_models import DocumentMetadata, EnrichedImageMetadata
import enum
import uuid

class OrchestrationInput(BaseModel):
    source_identifier: str = Field(..., description="URL or filepath")
    source_type: Optional[str] = Field(default=None, examples=["url", "pdf", "docx", "txt", "md"])
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"])
    job_id: Optional[str] = Field(default=None, description="Unique job identifier")
    user_id: Optional[str] = Field(default=None, description="User identifier")
    output_format_options: Optional[Dict[str, Any]] = Field(default=None, description="Options for output formatting")
    additional_context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context to pass through.")

# Represents the properties of a block, which vary by type.
class BlockProps(BaseModel):
    level: Optional[int] = None  # For headings
    language: Optional[str] = None  # For code blocks
    ordered: Optional[bool] = None  # For lists
    src: Optional[str] = None      # For images
    caption: Optional[str] = None  # For images
    
class InlineContent(BaseModel):
    type: str
    text: str
    styles: Dict[str, Any] = {}
    href: Optional[str] = None

class ContentBlock(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # E.g., 'paragraph', 'heading', 'list', 'image', 'code'
    props: BlockProps = Field(default_factory=BlockProps)
    content: Optional[Union[str, List['ContentBlock'], List[InlineContent]]] = None
    children: List['ContentBlock'] = []

    # The following are for compatibility/transformation and should not be directly used by the frontend.
    gcs_url: Optional[str] = Field(None, exclude=True)
    caption: Optional[str] = Field(None, exclude=True)
    level: Optional[int] = Field(None, exclude=True)
    language: Optional[str] = Field(None, exclude=True)

    @validator('props', pre=True, always=True)
    def assemble_props(cls, v, values):
        # If props is already a BlockProps instance, use it
        if isinstance(v, BlockProps):
            props = v
        # If it's a dictionary, create a BlockProps instance
        elif isinstance(v, dict):
            props = BlockProps(**v)
        # Otherwise, create a new one
        else:
            props = BlockProps()

        # For image blocks, transfer gcs_url and caption to props
        if values.get('type') == 'image':
            if 'gcs_url' in values and values['gcs_url']:
                props.src = values['gcs_url']
            if 'caption' in values and values['caption']:
                props.caption = values['caption']
        
        # For heading blocks, transfer level to props
        if values.get('type') == 'heading':
            if 'level' in values and values['level']:
                props.level = values['level']

        # For code blocks, transfer language to props
        if values.get('type') == 'code':
             if 'language' in values and values['language']:
                props.language = values['language']
                
        return props

# Ensure forward references are resolved after all models are defined
ContentBlock.model_rebuild()

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
    REWRITE_PENDING = "rewrite_pending"
    REWRITE_STARTED = "rewrite_started"
    REWRITE_SUMMARIZATION_AGENT_STARTED = "rewrite_summarization_agent_started"
    REWRITE_SUMMARIZATION_AGENT_PROCESSING = "rewrite_summarization_agent_processing"
    REWRITE_SUMMARIZATION_AGENT_COMPLETED = "rewrite_summarization_agent_completed"
    REWRITE_RECONSTRUCTION_STARTED = "rewrite_reconstruction_started"
    REWRITE_RECONSTRUCTION_COMPLETED = "rewrite_reconstruction_completed"
    REWRITE_SUCCESS = "rewrite_success"

    # AI Rewrite Process Specific Failure Statuses
    REWRITE_FAILED_EMPTY_INPUT = "rewrite_failed_empty_input"
    REWRITE_FAILED_SUMMARIZATION_AGENT_ERROR = "rewrite_failed_summarization_agent_error"
    REWRITE_FAILED_SUMMARIZATION_OUTPUT_PARSING = "rewrite_failed_summarization_output_parsing"
    REWRITE_FAILED_RECONSTRUCTION = "rewrite_failed_reconstruction"
    REWRITE_FAILED_UNHANDLED_EXCEPTION = "rewrite_failed_unhandled_exception"
    REWRITE_FAILED_DB_UPDATE = "rewrite_failed_db_update"

class OrchestrationOutput(BaseModel):
    status_code: str = Field(..., examples=["success", "partial_success", "failure_acquisition", "failure_image_processing", "failure_structuring", "unsupported_type"])
    user_id: Optional[str] = Field(default=None, description="User identifier for the entire orchestration, if available.")
    request_id: Optional[str] = Field(None, description="Request identifier (job_id) for the entire orchestration.")
    source_identifier: str
    final_url: Optional[str] = None
    source_type: Optional[str] = None
    title: Optional[str] = Field(None, description="The final title for the document.")
    content_blocks: List[ContentBlock] = Field(default_factory=list, description="The final, structured content blocks.")
    images_metadata: List[EnrichedImageMetadata] = Field(default_factory=list)
    document_metadata: Optional[DocumentMetadata] = Field(None, description="Comprehensive metadata about the processed document.")
    error_message: Optional[str] = None
    is_long_form_content: bool = False
    processing_level: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None