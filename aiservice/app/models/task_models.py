from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
import datetime
import uuid
from .orchestration_models import ContentBlock

class TaskType(str, Enum):
    """Enum for the different types of tasks that can be dispatched."""
    RECONSTRUCT_FROM_URL = "reconstruct_from_url"
    REWRITE_CONTENT = "rewrite_content"
    GENERATE_TITLE = "generate_title"
    GENERATE_KEYWORDS = "generate_keywords"

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TaskResult(BaseModel):
    """Data model for the result of a task."""
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class TaskPayload(BaseModel):
    id: str
    userId: str
    type: str
    status: str
    payload: Dict[str, Any]

class TaskRequest(BaseModel):
    task_type: str
    payload: Dict[str, Any]
    user_id: str

class RewriteTaskPayload(BaseModel):
    task_id: str
    user_id: str # Assuming user_id is a string, adjust if necessary
    original_content_blocks: List[Dict[str, Any]] # Assuming content blocks are dicts
    # Any other data needed by the worker that comes directly from the initial request

class TaskStatusUpdate(BaseModel):
    task_id: str
    status: TaskStatus
    user_id: Optional[str] = None
    input_data_ref: Optional[str] = None # e.g., a path or URI to where input is stored if not in payload
    result_data_ref: Optional[str] = None # e.g., a path or URI to where result is stored
    ai_rewritten_content_blocks: Optional[List[ContentBlock]] = None
    error_message: Optional[str] = None
    usage_metrics: Optional[Dict[str, Any]] = None # To store usage_metrics from RewriteContentOutput
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    class Config:
        use_enum_values = True 

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

class DocumentMetadata(BaseModel):
    document_id: str
    user_id: str
    source_identifier: str
    source_type: str
    title: Optional[str] = None 