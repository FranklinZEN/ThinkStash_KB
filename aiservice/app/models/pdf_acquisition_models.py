from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class PDFAcquisitionInput(BaseModel):
    file_path: str = Field(..., description="Path to the PDF file.")
    processing_level: str = Field(..., examples=["full_content", "text_only"], description="Controls whether to extract and mark images.")
    # job_id or other tracking identifiers could be added here

class RawPDFImageWithID(BaseModel):
    image_id: str # e.g., PDF_P1_figure_1 (page_number + id_from_llm)
    raw_image_data_ref: str # Reference to the full page image path in DataStore
    page_number: int
    image_type_from_llm: Optional[str] = Field(default=None, description="Type of image (e.g., chart, diagram) from LLM.")
    description: Optional[str] = Field(default=None, description="LLM-generated description of the specific figure on the page.")
    caption: Optional[str] = Field(default=None, description="LLM-generated/extracted caption for the specific figure.")
    # Bounding box (bounding_box_normalized) could be added if the LLM tool provides it reliably

class PDFAcquisitionOutput(BaseModel):
    status: str = Field(..., examples=["success", "error_parsing_pdf", "error_page_to_image_conversion", "error_llm_image_marking"])
    extracted_title: Optional[str] = None
    parsing_tier_used: Optional[str] = Field(default=None, description="Which parser was ultimately successful (e.g. pymupdf, nougat, pdfminer).")
    extracted_text_content_ref: Optional[str] = Field(default=None, description="DataStore key for the extracted text.")
    # This list will contain RawPDFImageWithID objects, one for each *identified figure* within page images.
    # The raw_image_data_ref within each item still points to the full page image.
    raw_image_list_with_ids_ref: Optional[str] = Field(default=None, description="DataStore key for List[RawPDFImageWithID objects].") 
    error_message: Optional[str] = None 