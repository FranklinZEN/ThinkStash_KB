import asyncio
import os
import uuid
import time
import markdown # For Markdown processing
from bs4 import BeautifulSoup # For cleaning HTML from Markdown
import docx # For DOCX processing
from typing import Optional, Any, List, Dict, Union
from pydantic import BaseModel, Field, HttpUrl
import re
from urllib.parse import urlparse # Added import

from aiservice.app.services.base import BaseService, ServiceResult

# --- Pydantic Models for FileAcquisitionService ---

class FileAcquisitionServiceInput(BaseModel):
    file_path: str = Field(..., description="Path to the file to process.")
    source_content_type: str = Field(..., examples=["docx", "md", "txt"], description="The type of the file.")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking.")

class ProcessedFileImage(BaseModel):
    image_id: str # e.g., "DOCX_IMG_1", "MD_IMG_1"
    image_bytes: Optional[bytes] = None # Bytes of the image if local and extracted
    source_url: Optional[HttpUrl] = None # URL if it's a web-linked image (esp. from Markdown)
    original_file_name: Optional[str] = None # Filename of the image if available (e.g., from DOCX)
    alt_text: Optional[str] = None # Alt text from Markdown
    # content_type: Optional[str] = None # MIME type, if available

class FileAcquisitionServiceOutput(BaseModel):
    status: str = Field(..., examples=["success", "error_file_not_found", "error_parsing_file", "error_unsupported_type"])
    page_title: Optional[str] = None # Filename
    extracted_text: Optional[str] = None
    images: List[ProcessedFileImage] = Field(default_factory=list)
    error_message: Optional[str] = None
    processing_duration_seconds: float
    source_content_type_processed: str

class FileAcquisitionService(BaseService):
    """
    Asynchronous service to extract text and images from various file types (DOCX, MD, TXT).
    """

    def _generate_image_id(self, file_type_prefix: str, job_id: Optional[str], index: int) -> str:
        job_prefix = f"{job_id}_" if job_id else f"{uuid.uuid4().hex[:4]}_"
        return f"{file_type_prefix}_IMG_{job_prefix}{index + 1}"

    async def _process_docx(self, file_path: str, job_id: Optional[str], processing_level: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        text_content = ""
        images: List[ProcessedFileImage] = []

        try:
            document = await loop.run_in_executor(None, docx.Document, file_path)
            
            # Extract text
            for para in document.paragraphs:
                text_content += para.text + "\n"
            text_content = text_content.strip()

            # Extract images if requested
            if processing_level == "full_content":
                for i, rel_id in enumerate(document.part.rels):
                    rel = document.part.rels[rel_id]
                    if "image" in rel.target_ref:
                        image_part = rel.target_part
                        image_bytes = image_part.blob
                        original_filename = os.path.basename(image_part.partname)
                        image_id = self._generate_image_id("DOCX", job_id, i)
                        
                        images.append(ProcessedFileImage(
                            image_id=image_id,
                            image_bytes=image_bytes,
                            original_file_name=original_filename,
                            # content_type=image_part.content_type
                        ))
            return {"text": text_content, "images": images, "error": None}
        except Exception as e:
            return {"text": None, "images": [], "error": f"Error processing DOCX file {file_path}: {str(e)}"}

    async def _process_markdown(self, file_path: str, job_id: Optional[str], processing_level: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        images: List[ProcessedFileImage] = []
        error_msg: Optional[str] = None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = await loop.run_in_executor(None, f.read)
            
            html_content = await loop.run_in_executor(None, markdown.markdown, md_content, ['fenced_code', 'tables'])
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)

            if processing_level == "full_content":
                # Find images: ![alt](src) in raw markdown, or <img> in generated HTML
                # Using regex on raw markdown for simplicity for now, as bs4 on md-generated html can be tricky for src
                img_index = 0
                for match in re.finditer(r'!\[(.*?)\]\((.*?)\)', md_content):
                    alt_text = match.group(1)
                    src = match.group(2)
                    image_id = self._generate_image_id("MD", job_id, img_index)
                    img_index += 1

                    processed_image = ProcessedFileImage(image_id=image_id, alt_text=alt_text)
                    
                    if urlparse(src).scheme in ['http', 'https']:
                        processed_image.source_url = HttpUrl(src)
                        # ImageProcessingService will download this URL.
                    elif os.path.exists(src): # Check if it's an existing local file (absolute path)
                         with open(src, 'rb') as img_f:
                            processed_image.image_bytes = await loop.run_in_executor(None, img_f.read)
                         processed_image.original_file_name = os.path.basename(src)
                    else: # Check if relative path to MD file location
                        base_dir = os.path.dirname(file_path)
                        local_image_path = os.path.join(base_dir, src)
                        if os.path.exists(local_image_path):
                            with open(local_image_path, 'rb') as img_f:
                                processed_image.image_bytes = await loop.run_in_executor(None, img_f.read)
                            processed_image.original_file_name = os.path.basename(local_image_path)
                        else:
                            # Could not resolve src as URL or local file, store as potential URL/path
                            try:
                                processed_image.source_url = HttpUrl(src) # Attempt to cast, might fail
                            except Exception:
                                print(f"Markdown image source '{src}' is not a valid URL or local file, storing as original string.")
                                # processed_image.source_url = src # Cannot assign str to HttpUrl, handle appropriately
                                # For now, we might skip this image or log an issue
                                continue # Skip this image if src is unresolvable
                    images.append(processed_image)
            
            return {"text": text_content, "images": images, "error": None}
        except Exception as e:
            return {"text": None, "images": [], "error": f"Error processing Markdown file {file_path}: {str(e)}"}

    async def _process_txt(self, file_path: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        encodings_to_try = ['utf-8', 'latin-1', 'windows-1252']
        text_content = None
        error_msg = None
        try:
            for encoding in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        text_content = await loop.run_in_executor(None, f.read)
                    break # Success
                except UnicodeDecodeError:
                    continue
            if text_content is None:
                error_msg = f"Could not decode TXT file {file_path} with tried encodings."
        except Exception as e:
            error_msg = f"Error reading TXT file {file_path}: {str(e)}"
        return {"text": text_content, "images": [], "error": error_msg}

    async def execute(self, file_input: FileAcquisitionServiceInput) -> ServiceResult[FileAcquisitionServiceOutput]:
        start_time = time.time()
        job_id = file_input.job_id or uuid.uuid4().hex[:8]
        file_path = file_input.file_path
        file_type = file_input.source_content_type.lower()
        page_title = os.path.basename(file_path)

        if not os.path.exists(file_path):
            duration = time.time() - start_time
            return ServiceResult.failure(
                error_message="File not found",
                error_details=FileAcquisitionServiceOutput(
                    status="error_file_not_found", page_title=page_title, processing_duration_seconds=duration,
                    error_message="File not found", source_content_type_processed=file_type).model_dump()
            )

        result_data: Dict[str, Any] = {"text": None, "images": [], "error": "Unknown processing error"}
        if file_type == "docx":
            result_data = await self._process_docx(file_path, job_id, file_input.processing_level)
        elif file_type == "md":
            result_data = await self._process_markdown(file_path, job_id, file_input.processing_level)
        elif file_type == "txt":
            result_data = await self._process_txt(file_path)
        else:
            result_data["error"] = f"Unsupported file type: {file_type}"
            current_status = "error_unsupported_type"

        current_status = "success" if result_data["error"] is None else "error_parsing_file"
        if result_data["error"] and current_status != "error_unsupported_type": # Don't override unsupported type error
             current_status = "error_parsing_file"
        elif result_data["error"] is None and not result_data["text"] and not result_data["images"]:
            current_status = "error_parsing_file" # No content extracted successfully
            result_data["error"] = "No text or images extracted from file."
        
        duration = time.time() - start_time
        output = FileAcquisitionServiceOutput(
            status=current_status,
            page_title=page_title,
            extracted_text=result_data["text"],
            images=result_data["images"],
            error_message=result_data["error"],
            processing_duration_seconds=duration,
            source_content_type_processed=file_type
        )

        if current_status.startswith("error"):
            return ServiceResult.failure(error_message=output.error_message or "File processing failed.", error_details=output.model_dump())
        return ServiceResult.success(data=output) 