from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class FileAcquisitionInput(BaseModel):
    file_path: str = Field(..., description="Path to the file (DOCX, TXT, or MD)")
    processing_level: str = Field(..., examples=["full_content", "text_only"])
    source_content_type: str = Field(..., examples=["docx", "txt", "md"], description="Hint of the content type from orchestrator")

class RawOrLinkedImage(BaseModel):
    image_id: str # e.g., DOCX_IMG_1, MD_IMG_1
    source_path_or_url: Optional[str] = None # URL for linked MD images, or temp path for extracted DOCX images
    raw_data_ref: Optional[str] = None # Reference if raw image data is stored (e.g., via DataStoreAccessTool)
    alt_text: Optional[str] = None # e.g., from MD image syntax
    # Potentially add original filename if extracted from DOCX

class FileAcquisitionOutput(BaseModel):
    status: str = Field(..., examples=["success_docx", "success_txt", "success_md", "error_file_not_found", "error_parsing_docx", "error_parsing_txt", "error_parsing_md", "unsupported_type_for_agent"])
    extracted_title: Optional[str] = None
    # References to data stored, likely via DataStoreAccessTool
    extracted_text_content_ref: Optional[str] = None 
    raw_or_linked_image_list_with_ids_ref: Optional[str] = None # Ref to List[RawOrLinkedImage]
    error_message: Optional[str] = None 