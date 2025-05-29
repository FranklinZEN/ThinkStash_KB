from pydantic import BaseModel, Field
from typing import List

from .pipeline_models import RawImageInput # Import RawImageInput

# Re-using ProcessedImageData from orchestration_models if it fits,
# or define a more specific one here if needed. For now, assume it can be reused.
# from app.models.orchestration_models import ProcessedImageData 

# The old ImageProcessingInput and ImageProcessingOutput are replaced by
# direct usage of List[RawImageInput] as input to the service's execute method,
# and List[EnrichedImageMetadata] as the data within the ServiceResult output.

class ImageProcessingServiceInput(BaseModel):
    images_to_process: List[RawImageInput] = Field(..., description="List of raw image data objects to be processed.")
    # Contextual fields like job_id, source_type, etc., are now expected to be part of each RawImageInput object.

# ImageProcessingOutput class removed as it is obsolete. 