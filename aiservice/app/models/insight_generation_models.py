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
    # Add any other parameters the ContentRewriteCrew might need, e.g., target tone, length constraints.
    # For now, keeping it simple as per initial crew design.

class RewriteContentOutput(BaseModel):
    """Output model for the /rewrite-content endpoint."""
    ai_rewritten_content_blocks: List[ContentBlock] = Field(..., description="The list of AI-generated rewritten content blocks.")
    status_code: str = Field(default="success", description="Status of the rewrite operation (e.g., 'success', 'error_rewriting').")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Title Generation Models ---

class GenerateTitleInput(BaseModel):
    """Input model for the /generate-title endpoint."""
    content_blocks: List[ContentBlock] = Field(..., description="The list of content blocks for which to generate a title.")
    # Add any other parameters like existing_title (if model should avoid it) or context_hint.

class GenerateTitleOutput(BaseModel):
    """Output model for the /generate-title endpoint."""
    suggested_title: str = Field(..., description="The AI-generated suggested title.")
    status_code: str = Field(default="success", description="Status of the title generation operation.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Keyword Generation Models ---

class GenerateKeywordsInput(BaseModel):
    """Input model for the /generate-keywords endpoint."""
    content_blocks: List[ContentBlock] = Field(..., description="The list of content blocks for which to generate keywords.")
    # Add any other parameters like number_of_keywords_desired.

class GenerateKeywordsOutput(BaseModel):
    """Output model for the /generate-keywords endpoint."""
    suggested_keywords: List[str] = Field(..., description="A list of AI-generated suggested keywords.")
    status_code: str = Field(default="success", description="Status of the keyword generation operation.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.") 