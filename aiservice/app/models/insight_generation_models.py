#!/usr/bin/env python
# coding: utf-8
"""
Defines Pydantic models for AI insight generation API requests and responses,
covering content rewrite, title generation, and keyword extraction.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Assuming ContentBlock and DocumentMetadata are imported from where they are now defined
# (likely orchestration_models.py or pipeline_models.py as per previous discussions)
# If they were moved or consolidated, adjust the import path.
# For now, let's assume they are in orchestration_models.py based on the previous context.
from .orchestration_models import ContentBlock
from .pipeline_models import DocumentMetadata

# --- Content Rewrite Models ---

class RewriteContentInput(BaseModel):
    """Input model for the /rewrite-content endpoint."""
    content_blocks_to_rewrite: List[ContentBlock] = Field(..., description="The list of content blocks to be rewritten/summarized.")
    document_metadata: Optional[DocumentMetadata] = Field(None, description="Optional document metadata for context during rewriting.")
    original_content_blocks_json_string: Optional[str] = Field(None, description="A JSON string representation of the original content blocks, primarily for the reconstruction agent if needed.")
    user_id: Optional[str] = Field(None, description="Identifier for the user associated with this request, if not in document_metadata.")
    # Add any other parameters the ContentRewriteCrew might need, e.g., target tone, length constraints.
    # For now, keeping it simple as per initial crew design.

class RewriteContentOutput(BaseModel):
    """Output model for the /rewrite-content endpoint."""
    ai_rewritten_content_blocks: List[ContentBlock] = Field(..., description="The list of AI-generated rewritten content blocks.")
    status_code: str = Field(default="success", description="Status of the rewrite operation (e.g., 'success', 'error_rewriting').")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")
    usage_metrics: Optional[Dict[str, Any]] = Field(None, description="Token usage metrics from the AI model provider.")
    processing_time_ms: Optional[float] = Field(None, description="Total processing time for the rewrite operation in milliseconds.")
    trace_id: Optional[str] = Field(None, description="A unique identifier for tracing the request through the system.")

# --- Title Generation Models ---

class TitleGenerationRequest(BaseModel):
    content_blocks: List[ContentBlock]

class TitleGenerationResponse(BaseModel):
    suggested_title: str

# --- Keyword Generation Models ---

class KeywordExtractionRequest(BaseModel):
    content_blocks: List[ContentBlock] = Field(..., description="The list of content blocks from which to extract keywords.")

class KeywordExtractionResponse(BaseModel):
    suggested_keywords: List[str] = Field(..., description="A list of suggested keywords.")
    # Potentially add fields for confidence scores or alternative keyword sets in the future 