from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

# ContentBlock will be imported from orchestration_models for the output
# from app.models.orchestration_models import ContentBlock 

# Assuming pipeline_models.py is at aiservice.app.models.pipeline_models
# Adjust import path if necessary based on your project structure.
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, EnrichedImageMetadata

class ContentStructuringInput(BaseModel):
    extracted_text_content_ref: str = Field(..., description="Reference to the main text content in DataStore.")
    processed_image_data_list_ref: Optional[str] = Field(default=None, description="Reference to List[ProcessedImageData] in DataStore. Can be None if no images.")
    source_content_type_hint: str = Field(..., description="Hint of the original content type (e.g., pdf_content, html_content).")
    page_title_from_acquisition: Optional[str] = Field(default=None, description="Title extracted by the acquisition agent.")
    # Add job_id or other tracking IDs if needed

class ContentStructuringOutput(BaseModel):
    # This model directly returns the data needed by the OrchestrationAgent, not references.
    # The OrchestrationOutput model uses List[ContentBlock] for original_content_blocks.
    final_original_content_blocks: List[Dict[str, Any]] = Field(..., description="Final list of content blocks (text/math/code with placeholders, then image gallery blocks).")
    is_long_article_flag: bool = Field(default=False)
    status: str = Field(..., examples=["success", "error_retrieving_data", "error_llm_structuring", "error_gallery_append"], description="Status of the content structuring task.")
    error_message: Optional[str] = None 

class ContentStructuringServiceInput(BaseModel):
    preliminary_blocks: List[PreliminaryBlock] = Field(..., description="List of preliminary blocks from acquisition services.")
    enriched_images: List[EnrichedImageMetadata] = Field(..., description="List of enriched image metadata from ImageProcessingService.")
    document_metadata: DocumentMetadata = Field(..., description="Document metadata from acquisition services.")
    job_id: Optional[str] = Field(None, description="Optional job identifier.")

# Output model for ContentStructuringService is implicitly List[ContentBlock]
# from aiservice.app.models.orchestration_models.py, so no specific output model here. 