#!/usr/bin/env python
# coding: utf-8
"""
Defines Pydantic models for specific task outputs within crews.
These models are typically used with the `output_pydantic` parameter in CrewAI Tasks.
"""

from pydantic import BaseModel, Field
from typing import Optional, List

class Segment(BaseModel):
    type: str = Field(..., description="Type of segment, e.g., 'text' or 'image_reference'.")
    content: Optional[str] = Field(None, description="Text content if type is 'text'.")
    image_id_ref: Optional[str] = Field(None, description="Image ID reference if type is 'image_reference'.")

class StructuredSummary(BaseModel):
    segments: List[Segment] = Field(..., description="A list of text and image reference segments.")

class SummarizerTaskOutput(BaseModel):
    """Pydantic model for the output of the summarization task."""
    structured_summary: StructuredSummary = Field(..., description="The structured summary containing text and image references.")
    raw_llm_output_json: Optional[str] = Field(None, description="The raw JSON string output from the LLM, for debugging or if parsing fails.")
    # Potentially add other fields if the LLM tool or agent might return them structured,
    # e.g., image_references_made: Optional[List[str]] = None
    # For now, keeping it simple to just the summary string as per the plan.

# Add other task-specific output models here as needed.

class TitleGenerationOutput(BaseModel):
    """Pydantic model for the output of the title generation task."""
    suggested_title: str = Field(..., description="The AI-generated title for the content, or an error message.") 