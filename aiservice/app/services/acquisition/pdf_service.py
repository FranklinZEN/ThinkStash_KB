import asyncio
import fitz # PyMuPDF
import os
import uuid
import time
from typing import Optional, Any, List, Dict
from pydantic import BaseModel, Field

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.tools.llm_tools import ImageAnalysisLLMTool, ImageAnalysisInput, ImageAnalysisOutput # Assuming llm_tools.py is created

# --- Pydantic Models for PDFAcquisitionService ---

class PDFAcquisitionServiceInput(BaseModel):
    file_path: str = Field(..., description="Path to the PDF file to process.")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images and analyze them.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking.")
    # use_llm_for_image_analysis: bool = Field(default=False, description="Flag from settings to enable LLM for image analysis.") # This will come from global settings injected into service

class ProcessedPDFImage(BaseModel):
    image_id: str # e.g., "PDF_P1_IMG1"
    image_bytes: bytes
    original_file_name: Optional[str] = None # If extractable
    page_number: int
    bbox: Optional[List[float]] = None # Bounding box [x0, y0, x1, y1]
    # Fields from ImageAnalysisLLMTool if LLM analysis is run
    description: Optional[str] = None
    caption: Optional[str] = None
    keywords: Optional[List[str]] = None

class PDFAcquisitionServiceOutput(BaseModel):
    status: str = Field(..., examples=["success", "success_text_only", "error_file_not_found", "error_parsing_pdf", "error_image_extraction", "error_llm_image_analysis"])
    page_title: Optional[str] = None # Often filename or from PDF metadata
    extracted_text: Optional[str] = None
    images: List[ProcessedPDFImage] = Field(default_factory=list)
    error_message: Optional[str] = None
    processing_duration_seconds: float

class PDFAcquisitionService(BaseService):
    """
    Asynchronous service to extract text and images from PDF files.
    Uses PyMuPDF for direct parsing and optionally ImageAnalysisLLMTool for image descriptions.
    """
    def __init__(self, image_analysis_tool: Optional[ImageAnalysisLLMTool] = None, settings: Optional[Any] = None):
        super().__init__(settings)
        self.image_analysis_tool = image_analysis_tool
        # self.use_llm_for_image_analysis = getattr(settings, 'use_llm_for_image_analysis', False) if settings else False
        # A more robust way is to pass it directly or have settings as a typed object
        if settings and hasattr(settings, 'use_llm_for_image_analysis'):
             self.use_llm_for_image_analysis = settings.use_llm_for_image_analysis
        else:
             self.use_llm_for_image_analysis = False # Default if not in settings

    def _extract_text_from_pdf(self, doc: fitz.Document) -> str:
        full_text = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            full_text.append(page.get_text("text"))
        return "\n".join(full_text)

    async def _extract_images_from_pdf(self, doc: fitz.Document, job_id: str, pdf_filename: str) -> List[ProcessedPDFImage]:
        extracted_images: List[ProcessedPDFImage] = []
        loop = asyncio.get_event_loop()

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # PyMuPDF's get_images(full=True) gives more details about images
            image_list = await loop.run_in_executor(None, page.get_images, True)
            
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = await loop.run_in_executor(None, doc.extract_image, xref)
                image_bytes = base_image["image"]
                # image_ext = base_image["ext"]
                # width = base_image["width"]
                # height = base_image["height"]

                # Try to get bounding box of the image on the page
                # This is complex as get_images() doesn't directly give bbox on page.
                # We might need to iterate page display list or use other methods if exact bbox is crucial.
                # For now, keeping it simple. If PDF has vector graphics, bbox is more relevant.
                
                image_id = f"PDF_{job_id or uuid.uuid4().hex[:4]}P{page_num + 1}_IMG{img_index + 1}"
                
                # Placeholder for potential filename if available from PDF structure (rare)
                original_image_filename = f"image_{xref}.{base_image['ext']}"

                img_data = ProcessedPDFImage(
                    image_id=image_id,
                    image_bytes=image_bytes,
                    original_file_name=original_image_filename, # Or more meaningful if possible
                    page_number=page_num + 1,
                    # bbox= # Requires more complex logic to find bbox on page
                )

                if self.use_llm_for_image_analysis and self.image_analysis_tool:
                    print(f"PDFAcquisitionService: Analyzing image {image_id} with LLM.")
                    # Run LLM analysis (which is sync in BaseTool) in executor
                    analysis_input = ImageAnalysisInput(image_bytes=image_bytes, text_context=f"Image from PDF: {pdf_filename}, page {page_num+1}")
                    llm_result_dict = await loop.run_in_executor(None, self.image_analysis_tool._run, **analysis_input.model_dump())
                    llm_output = ImageAnalysisOutput(**llm_result_dict)

                    if llm_output.error_message:
                        print(f"PDFAcquisitionService: LLM analysis error for {image_id}: {llm_output.error_message}")
                        # Optionally log this error or attach to image_data
                    else:
                        img_data.description = llm_output.description
                        img_data.caption = llm_output.caption
                        img_data.keywords = llm_output.keywords
                
                extracted_images.append(img_data)
        return extracted_images

    async def execute(self, pdf_input: PDFAcquisitionServiceInput) -> ServiceResult[PDFAcquisitionServiceOutput]:
        start_time = time.time()
        job_id = pdf_input.job_id or uuid.uuid4().hex[:8]
        pdf_filename = os.path.basename(pdf_input.file_path)

        if not os.path.exists(pdf_input.file_path):
            duration = time.time() - start_time
            return ServiceResult.failure(
                error_message="File not found", 
                error_details=PDFAcquisitionServiceOutput(
                    status="error_file_not_found", page_title=pdf_filename, processing_duration_seconds=duration, error_message="File not found").model_dump()
            )

        extracted_text: Optional[str] = None
        processed_images: List[ProcessedPDFImage] = []
        page_title = pdf_filename # Default title
        error_msg: Optional[str] = None
        current_status = "pending"

        loop = asyncio.get_event_loop()

        try:
            doc = await loop.run_in_executor(None, fitz.open, pdf_input.file_path)
            
            # Extract metadata (e.g., title)
            meta = await loop.run_in_executor(None, getattr, doc, 'metadata')
            if meta and meta.get('title'):
                page_title = meta['title']
            if not page_title: page_title = pdf_filename # Fallback if no metadata title

            # Extract text content
            extracted_text = await loop.run_in_executor(None, self._extract_text_from_pdf, doc)
            current_status = "success_text_only"

            # Extract images if requested
            if pdf_input.processing_level == "full_content":
                try:
                    processed_images = await self._extract_images_from_pdf(doc, job_id, pdf_filename)
                    current_status = "success" if extracted_text else "success_images_only" # Adjust based on text success
                    if not extracted_text and not processed_images:
                        current_status = "error_parsing_pdf" # Neither text nor images found
                        error_msg = "Failed to extract meaningful content (text or images) from PDF."
                    elif not extracted_text and processed_images:
                         current_status = "success_images_only_text_failed"
                         error_msg = "Images extracted, but text extraction failed or yielded no content."

                except Exception as e_img:
                    error_msg = (error_msg or "") + f"; Image extraction/analysis failed: {str(e_img)}"
                    current_status = "error_image_extraction" if current_status not in ["error_parsing_pdf"] else current_status
                    # If text was extracted, it's a partial success despite image error
                    if extracted_text and current_status.startswith("error_image"):
                         current_status = "success_text_only_image_extraction_failed"
            
            await loop.run_in_executor(None, doc.close)

        except Exception as e:
            error_msg = f"Error parsing PDF '{pdf_filename}': {str(e)}"
            current_status = "error_parsing_pdf"
            # Ensure doc is closed if opened
            # This is tricky with async executor, doc might not be defined if fitz.open failed.
            # Consider adding a try/finally within the executor call for doc.close()
        
        duration = time.time() - start_time
        output = PDFAcquisitionServiceOutput(
            status=current_status,
            page_title=page_title,
            extracted_text=extracted_text,
            images=processed_images,
            error_message=error_msg,
            processing_duration_seconds=duration
        )

        if current_status.startswith("error"):
            return ServiceResult.failure(error_message=error_msg or "PDF processing failed.", error_details=output.model_dump())
        return ServiceResult.success(data=output) 