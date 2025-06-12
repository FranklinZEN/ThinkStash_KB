from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import datetime

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

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
    ai_rewritten_content_blocks: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    usage_metrics: Optional[Dict[str, Any]] = None # To store usage_metrics from RewriteContentOutput
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    class Config:
        use_enum_values = True 