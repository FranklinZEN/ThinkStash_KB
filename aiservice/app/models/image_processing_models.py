from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any

# Re-using ProcessedImageData from orchestration_models if it fits,
# or define a more specific one here if needed. For now, assume it can be reused.
# from app.models.orchestration_models import ProcessedImageData 

class ImageProcessingInput(BaseModel):
    # Exactly one of these should be provided, based on the source acquisition agent
    pdf_image_list_ref: Optional[str] = Field(default=None, description="Reference to List[RawPDFImageWithID] from PDF agent.")
    generic_file_image_list_ref: Optional[str] = Field(default=None, description="Reference to List[RawOrLinkedImage] from Generic File agent.")
    web_image_list_ref: Optional[str] = Field(default=None, description="Reference to List[ExtractedImageURLWithID] from Web URL agent.")
    
    original_source_identifier: str = Field(..., description="Original source URL or filepath, for context or GCS path.")
    source_type: str = Field(..., description="Original source type (url, pdf, docx, etc.).")
    job_id: Optional[str] = Field(default=None, description="Optional job ID for unique GCS paths or logging.")

class ImageProcessingOutput(BaseModel):
    status: str = Field(..., examples=["success_no_images", "success_images_processed", "error_fetching_refs", "error_downloading", "error_uploading", "error_metadata_consolidation"], description="Overall status of image processing.")
    processed_image_data_list_ref: Optional[str] = Field(default=None, description="Reference to List[ProcessedImageData] in DataStore.")
    # This list itself will contain ProcessedImageData objects, each with original_source_identifier, gcs_url, alt_text, caption, etc.
    error_message: Optional[str] = None
    images_processed_count: int = 0
    images_failed_count: int = 0 