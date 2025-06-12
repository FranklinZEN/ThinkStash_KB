from pydantic import BaseModel, Field
from typing import List, Optional, Any

class WebAcquisitionInput(BaseModel):
    url: str = Field(..., description="The URL to fetch and process.")
    processing_level: str = Field(..., examples=["full_content", "text_only"], description="Controls whether to extract images.")
    # Potentially add job_id or other tracking identifiers if needed later

class ExtractedImageURLWithID(BaseModel):
    image_id: str # e.g., WEB_IMG_1, WEB_IMG_2
    image_url: str # The direct URL of the image
    alt_text: Optional[str] = None # If an alt text was associated with the image
    # Context or original DOM path could be added if WebContentFetcherTool provides it

class WebAcquisitionOutput(BaseModel):
    status: str = Field(..., examples=["success", "success_pdf_redirect", "error_fetch", "error_parsing", "error_paywall", "error_unsupported_content_type"], description="Overall status of the web acquisition task.")
    page_title_from_web: Optional[str] = None
    final_url_after_redirects: Optional[str] = None # The final URL if redirects occurred
    
    # References to data stored, likely via DataStoreAccessTool
    extracted_text_content_ref: Optional[str] = None
    extracted_image_url_list_with_ids_ref: Optional[str] = None # Ref to List[ExtractedImageURLWithID]
    
    # If PDF was downloaded directly (e.g. from a redirect), its path might be stored
    downloaded_pdf_path_ref: Optional[str] = None 
    
    error_message: Optional[str] = None
    is_paywalled: Optional[bool] = None 