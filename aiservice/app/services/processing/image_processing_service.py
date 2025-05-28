import asyncio
import io
import os
import uuid
import time
import re
import functools # Added for functools.partial
from typing import Optional, Any, List, Dict, Union

import aiohttp
from PIL import Image # Pillow
from pydantic import BaseModel, Field, HttpUrl
from google.cloud import storage # For GCS

from aiservice.app.config.settings import Settings # For typed settings
from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.tools.llm_tools import ImageAnalysisLLMTool, ImageAnalysisInput, ImageAnalysisOutput
from aiservice.app.models.orchestration_models import ProcessedImageData # Final output model for each image

# --- Input Model for ImageProcessingService --- 
class RawImageInput(BaseModel):
    image_id: str # Original ID from acquisition service (e.g., WEB_IMG_1, PDF_P1_IMG1)
    image_bytes: Optional[bytes] = None
    source_url: Optional[HttpUrl] = None # If image needs to be downloaded
    alt_text: Optional[str] = None      # Existing alt text from source
    caption: Optional[str] = None       # Existing caption from source (e.g. from PDF multimodal analysis)
    
    # For GCS path construction
    original_source_identifier_for_gcs_path: str 
    source_type_for_gcs_path: str # e.g. web, pdf, docx
    job_id_for_gcs_path: str

class ImageProcessingServiceInput(BaseModel):
    images_to_process: List[RawImageInput]
    # use_llm_for_image_analysis: bool = Field(default=False) # This will come from global settings
    # gcs_bucket_name: Optional[str] = None # This will come from global settings

# Service output is a list of ProcessedImageData, returned via ServiceResult.data
# So, no specific Output Pydantic model here, List[ProcessedImageData] is the data type.

class ImageProcessingService(BaseService):
    """
    Asynchronous service to download, process (metadata, LLM analysis), and upload images to GCS.
    """
    def __init__(self, image_analysis_tool: Optional[ImageAnalysisLLMTool] = None, settings: Optional[Settings] = None):
        super().__init__(settings)
        self.image_analysis_tool = image_analysis_tool
        self.settings = settings # Store typed settings
        self.use_llm_for_image_analysis = self.settings.use_llm_for_image_analysis if self.settings else False
        self.gcs_bucket_name = self.settings.gcs_bucket_name if self.settings else None
        
        self.gcs_client: Optional[storage.Client] = None
        if self.gcs_bucket_name:
            try:
                self.gcs_client = storage.Client() # Initialize GCS client
                print(f"ImageProcessingService: GCS Client initialized for bucket: {self.gcs_bucket_name}")
            except Exception as e:
                print(f"ImageProcessingService: WARNING - Failed to initialize GCS client: {str(e)}. GCS uploads will fail.")
                self.gcs_client = None # Ensure it's None if init fails
                self.gcs_bucket_name = None # Can't use bucket if client failed

    def _sanitize_for_gcs_path(self, text: Optional[str], max_length: int = 100) -> str:
        if not text: return f"untitled_{uuid.uuid4().hex[:6]}"
        text = str(text)
        text = re.sub(r'^https?://', '', text) 
        text = re.sub(r'[^a-zA-Z0-9._/\-]', '_', text) # Hyphen escaped
        text = re.sub(r'_+', '_', text)
        text = text.strip('_').strip('/')
        return text[:max_length]

    async def _get_image_metadata(self, image_bytes: bytes) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        try:
            img = await loop.run_in_executor(None, Image.open, io.BytesIO(image_bytes))
            width, height = img.size
            img_format = img.format
            mime_type = Image.MIME.get(img_format.upper() if img_format else None)
            return {"width": width, "height": height, "format": img_format, "mime_type": mime_type, "error": None}
        except Exception as e:
            return {"error": f"Pillow metadata extraction failed: {str(e)}"}

    async def _upload_to_gcs(self, image_bytes: bytes, gcs_blob_name: str, mime_type: Optional[str]) -> Dict[str, Any]:
        if not self.gcs_client or not self.gcs_bucket_name:
            return {"gcs_url": None, "error": "GCS client or bucket not configured."}
        
        loop = asyncio.get_event_loop()
        try:
            bucket = self.gcs_client.bucket(self.gcs_bucket_name)
            blob = bucket.blob(gcs_blob_name)
            
            # Use a file-like object for upload_from_file method
            image_file_obj = io.BytesIO(image_bytes)
            
            # Use functools.partial to include the keyword argument for the executor
            upload_func = functools.partial(blob.upload_from_file, content_type=(mime_type or 'application/octet-stream'))
            await loop.run_in_executor(None, upload_func, image_file_obj)
            gs_url = f"gs://{self.gcs_bucket_name}/{gcs_blob_name}"
            print(f"ImageProcessingService: Successfully uploaded to {gs_url}")
            return {"gcs_url": gs_url, "error": None}
        except Exception as e:
            print(f"ImageProcessingService: ERROR - GCS Upload failed for {gcs_blob_name}: {str(e)}")
            return {"gcs_url": None, "error": f"GCS upload failed: {str(e)}"}

    async def _process_single_image(self, raw_image: RawImageInput) -> Optional[ProcessedImageData]:
        current_image_bytes: Optional[bytes] = raw_image.image_bytes
        error_messages: List[str] = []

        # 1. Download if source_url is provided and no bytes
        if raw_image.source_url and not current_image_bytes:
            try:
                timeout_seconds = self.settings.default_request_timeout_seconds if self.settings else 30
                timeout = aiohttp.ClientTimeout(total=timeout_seconds)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(str(raw_image.source_url)) as response:
                        response.raise_for_status()
                        current_image_bytes = await response.read()
            except Exception as e:
                error_messages.append(f"Download failed for {raw_image.source_url}: {str(e)}")
                print(f"ImageProcessingService: {error_messages[-1]}")
                return None 

        if not current_image_bytes:
            if not error_messages: error_messages.append("No image bytes or downloadable URL provided.")
            print(f"ImageProcessingService: No bytes for image {raw_image.image_id}. Errors: {'; '.join(error_messages)}")
            return None

        metadata = await self._get_image_metadata(current_image_bytes)
        if metadata.get("error"):
            error_messages.append(metadata["error"])

        gcs_url: Optional[str] = None
        if self.gcs_client and self.gcs_bucket_name:
            file_ext = os.path.splitext(raw_image.image_id)[1] or (f".{metadata.get('format', 'img').lower()}" if metadata.get('format') else ".img")
            sanitized_source_id = self._sanitize_for_gcs_path(raw_image.original_source_identifier_for_gcs_path.split("/")[-1].split(".")[0])
            gcs_blob_name = f"{raw_image.source_type_for_gcs_path}/{sanitized_source_id}/{raw_image.job_id_for_gcs_path}/{raw_image.image_id}{file_ext}"
            
            gcs_result = await self._upload_to_gcs(current_image_bytes, gcs_blob_name, metadata.get("mime_type"))
            gcs_url = gcs_result.get("gcs_url")
            if gcs_result.get("error"):
                error_messages.append(gcs_result["error"])
                print(f"ImageProcessingService: GCS upload failed for {raw_image.image_id}: {gcs_result.get('error')}")
                # If GCS is configured but upload fails, consider the image processing failed.
                return None 
        elif not self.gcs_bucket_name: # GCS not configured
            error_messages.append("GCS bucket not configured; cannot upload.")
            gcs_url = f"local_mock_path/{raw_image.image_id}.{metadata.get('format', 'img').lower()}" # Mock path if no GCS
            print(f"ImageProcessingService: GCS not configured. Image {raw_image.image_id} not uploaded.")
        
        llm_description: Optional[str] = None
        llm_caption_override: Optional[str] = raw_image.caption

        if self.use_llm_for_image_analysis and self.image_analysis_tool:
            print(f"ImageProcessingService: LLM analyzing image {raw_image.image_id}")
            loop = asyncio.get_event_loop()
            analysis_input = ImageAnalysisInput(
                image_bytes=current_image_bytes,
                text_context=raw_image.alt_text or raw_image.caption 
            )
            # Use functools.partial to correctly pass kwargs to the tool's _run method
            tool_call_with_args = functools.partial(self.image_analysis_tool._run, **analysis_input.model_dump())
            llm_analysis_result_dict = await loop.run_in_executor(None, tool_call_with_args)
            
            llm_analysis_output = ImageAnalysisOutput(**llm_analysis_result_dict)
            if llm_analysis_output.error_message:
                error_messages.append(f"LLM analysis error: {llm_analysis_output.error_message}")
            else:
                llm_description = llm_analysis_output.description
                if llm_analysis_output.caption: 
                    llm_caption_override = llm_analysis_output.caption
        
        final_image_data = ProcessedImageData(
            original_source_identifier=raw_image.image_id, 
            gcs_url=gcs_url or "gcs_not_configured_or_failed",
            alt_text=raw_image.alt_text,
            caption=llm_caption_override,
            llm_description=llm_description,
            width=metadata.get("width"),
            height=metadata.get("height"),
            mime_type=metadata.get("mime_type")
        )
        if error_messages:
            print(f"ImageProcessingService: Note - Errors for {raw_image.image_id}: {'; '.join(error_messages)}")
        return final_image_data

    async def execute(self, service_input: ImageProcessingServiceInput) -> ServiceResult[List[ProcessedImageData]]:
        start_time = time.time()
        processed_images_list: List[ProcessedImageData] = []
        failed_image_ids: List[str] = []

        tasks = [self._process_single_image(raw_image) for raw_image in service_input.images_to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            raw_image_input = service_input.images_to_process[i]
            if isinstance(result, ProcessedImageData):
                processed_images_list.append(result)
            elif isinstance(result, Exception):
                print(f"ImageProcessingService: Exception processing image {raw_image_input.image_id}: {result}")
                failed_image_ids.append(raw_image_input.image_id)
            elif result is None: 
                print(f"ImageProcessingService: Image {raw_image_input.image_id} was not processed successfully.")
                failed_image_ids.append(raw_image_input.image_id)
        
        duration = time.time() - start_time
        status_message = f"Processed {len(processed_images_list)} out of {len(service_input.images_to_process)} images, {len(failed_image_ids)} failed."
        print(f"ImageProcessingService: Completed in {duration:.2f}s. {status_message}")

        if failed_image_ids and not processed_images_list: # All images failed
            # Construct a more informative error message for the failure case
            failure_summary = f"All {len(failed_image_ids)} images failed processing. First failure on: {failed_image_ids[0] if failed_image_ids else 'N/A'}."
            return ServiceResult.failure(error_message=failure_summary, error_details={"failed_ids": failed_image_ids, "summary": status_message})
        
        # If some images failed but others succeeded, or if all succeeded, or if no images were provided:
        # The orchestrator can inspect the length of processed_images_list against the input 
        # to determine if it was a partial success and log/handle accordingly.
        # The ServiceResult itself is a success if at least some images were processed or no images were there to begin with.
        return ServiceResult.success(data=processed_images_list)

# Required for _sanitize_for_gcs_path
# import re # Removed redundant import 