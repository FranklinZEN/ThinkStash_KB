import asyncio
import io
import os
import uuid
import time
import re
import functools
from typing import Optional, Any, List, Dict, Set
import hashlib
import logging # Added logging

import aiohttp
from PIL import Image # Pillow
from google.cloud import storage # For GCS
from cachetools import LRUCache # Import LRUCache

from aiservice.app.config.settings import Settings # For typed settings
from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.tools.llm_tools import ImageAnalysisLLMTool, ImageAnalysisInput, ImageAnalysisOutput

# Import the new standard models
from aiservice.app.models.pipeline_models import RawImageInput, EnrichedImageMetadata # Added EnrichedImageMetadata
from aiservice.app.models.image_processing_models import ImageProcessingServiceInput

# --- Input Model for ImageProcessingService --- 
# Removed internally defined RawImageInput and ImageProcessingServiceInput as they are now imported

# Service output is List[EnrichedImageMetadata], returned via ServiceResult.data

class ImageProcessingService(BaseService):
    """
    Asynchronous service to download, process (metadata, LLM analysis), and upload images to GCS.
    """
    # --- Image Filter Constants are now loaded from settings in __init__ ---
    # MIN_IMG_DIMENSION = 50  # Removed
    # MIN_IMG_AREA = 5000     # Removed
    # MAX_IMG_ASPECT_RATIO_DEVIATION = 4.0 # Removed
    # IRRELEVANT_ALT_TEXT_EXACT: Set[str] = { ... } # Removed
    # IRRELEVANT_ALT_TEXT_SUBSTRINGS: Set[str] = { ... } # Removed
    # IRRELEVANT_FILENAME_URL_SEGMENTS: Set[str] = { ... } # Removed

    def __init__(self, image_analysis_tool: Optional[ImageAnalysisLLMTool] = None, settings: Optional[Settings] = None):
        super().__init__(settings)
        self.image_analysis_tool = image_analysis_tool
        self.settings = settings # Store typed settings
        self.logger = logging.getLogger(__name__) # Initialize logger
        
        if self.settings:
            if hasattr(self.settings, 'debug_mode') and self.settings.debug_mode:
                self.logger.setLevel(logging.DEBUG)
            else:
                self.logger.setLevel(logging.INFO)
            self.use_llm_for_image_analysis = self.settings.use_llm_for_image_analysis
            self.gcs_bucket_name = self.settings.gcs_bucket_name
            # Load image filter constants from settings
            self.MIN_IMG_DIMENSION = self.settings.img_filter_min_dimension
            self.MIN_IMG_WIDTH_PX = self.settings.img_filter_min_width_px
            self.MIN_IMG_HEIGHT_PX = self.settings.img_filter_min_height_px
            self.MIN_IMG_AREA = self.settings.img_filter_min_area
            self.MAX_IMG_ASPECT_RATIO_DEVIATION = self.settings.img_filter_max_aspect_ratio_deviation
            self.IRRELEVANT_ALT_TEXT_EXACT = self.settings.img_filter_irrelevant_alt_text_exact
            self.IRRELEVANT_ALT_TEXT_SUBSTRINGS = self.settings.img_filter_irrelevant_alt_text_substrings
            self.IRRELEVANT_FILENAME_URL_SEGMENTS = self.settings.img_filter_irrelevant_filename_url_segments
            processing_cache_maxsize = self.settings.image_processing_cache_size
            self.default_request_timeout_seconds = self.settings.default_request_timeout_seconds
        else:
            # Fallbacks if settings object is not provided (should ideally not happen in production)
            self.logger.setLevel(logging.INFO) # Default if no settings
            self.use_llm_for_image_analysis = False
            self.gcs_bucket_name = None
            self.MIN_IMG_DIMENSION = 50
            self.MIN_IMG_WIDTH_PX = 150
            self.MIN_IMG_HEIGHT_PX = 150
            self.MIN_IMG_AREA = 5000
            self.MAX_IMG_ASPECT_RATIO_DEVIATION = 4.0
            self.IRRELEVANT_ALT_TEXT_EXACT = {"logo", "avatar", "icon"} # Minimal fallback
            self.IRRELEVANT_ALT_TEXT_SUBSTRINGS = {"logo", "avatar", "icon"} # Minimal fallback
            self.IRRELEVANT_FILENAME_URL_SEGMENTS = {"/logo", "/avatar", "/icon"} # Minimal fallback
            processing_cache_maxsize = 128 # Fallback cache size
            self.default_request_timeout_seconds = 30

        self.gcs_client: Optional[storage.Client] = None
        if self.gcs_bucket_name:
            try:
                self.gcs_client = storage.Client() # Initialize GCS client
                self.logger.info(f"ImageProcessingService: GCS Client initialized for bucket: {self.gcs_bucket_name}")
            except Exception as e:
                self.logger.warning(f"ImageProcessingService: WARNING - Failed to initialize GCS client: {str(e)}. GCS uploads will fail.")
                self.gcs_client = None # Ensure it's None if init fails
                self.gcs_bucket_name = None # Can't use bucket if client failed
        
        # Initialize LRU Cache
        self.processing_cache = LRUCache(maxsize=processing_cache_maxsize)

    def _sanitize_for_gcs_path(self, text: Optional[str], max_length: int = 100) -> str:
        if not text: return f"untitled_{uuid.uuid4().hex[:6]}"
        text = str(text)
        text = re.sub(r'^https?://', '', text) 
        text = re.sub(r'[^a-zA-Z0-9._/\\-]', '_', text) # Hyphen escaped
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
            
            image_file_obj = io.BytesIO(image_bytes)
            
            upload_func = functools.partial(blob.upload_from_file, content_type=(mime_type or 'application/octet-stream'))
            await loop.run_in_executor(None, upload_func, image_file_obj)
            gs_url = f"gs://{self.gcs_bucket_name}/{gcs_blob_name}"
            self.logger.info(f"ImageProcessingService: Successfully uploaded to {gs_url}")
            return {"gcs_url": gs_url, "error": None}
        except Exception as e:
            self.logger.error(f"ImageProcessingService: ERROR - GCS Upload failed for {gcs_blob_name}: {str(e)}", exc_info=True)
            return {"gcs_url": None, "error": f"GCS upload failed: {str(e)}"}

    async def _process_single_image(self, raw_image: RawImageInput) -> Optional[EnrichedImageMetadata]:
        current_image_bytes: Optional[bytes] = raw_image.image_bytes # Moved higher to be available for initial cache key logic if needed, though hash is after download
        error_messages: List[str] = []

        # --- TEMP DEBUG LOG ---
        self.logger.debug(f"ImageProcessingService._process_single_image: Processing ID: {raw_image.image_id}, Source URL: {raw_image.source_url}, Alt Text: '{raw_image.alt_text}'")
        # --- END TEMP DEBUG LOG ---

        # 1. Download if source_url is provided and no bytes (current_image_bytes will be updated)
        if raw_image.source_url and not current_image_bytes:
            try:
                timeout_seconds = self.default_request_timeout_seconds # Use instance attribute
                timeout = aiohttp.ClientTimeout(total=timeout_seconds)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(str(raw_image.source_url)) as response:
                        response.raise_for_status()
                        current_image_bytes = await response.read()
            except Exception as e:
                error_messages.append(f"Download failed for {raw_image.source_url}: {str(e)}")
                self.logger.error(f"Download failed for {raw_image.source_url}: {str(e)}", exc_info=True)
                return None 

        if not current_image_bytes:
            if not error_messages: error_messages.append("No image bytes or downloadable URL provided for cache key generation or processing.")
            self.logger.warning(f"ImageProcessingService: No bytes for image {raw_image.image_id}. Errors: {'; '.join(error_messages)}")
            return None
        
        # Generate cache key using a hash of image_bytes
        image_bytes_hash = hashlib.sha256(current_image_bytes).hexdigest()
        cache_key = (image_bytes_hash, self.use_llm_for_image_analysis)

        # Check cache
        if cache_key in self.processing_cache:
            cached_data: EnrichedImageMetadata = self.processing_cache[cache_key]
            self.logger.info(f"ImageProcessingService: Cache HIT for key: {cache_key} (current raw_image.image_id: {raw_image.image_id}) -> using cached EnrichedImageMetadata originally from image_id: {cached_data.image_id}")
            
            # Create a new EnrichedImageMetadata object to ensure the image_id and original_source_identifier
            # match the current job's RawImageInput, while reusing other content-derived data from the cached object.
            # This is crucial for consistent linking in ContentStructuringService and accurate reporting.
            updated_cached_data = EnrichedImageMetadata(
                image_id=raw_image.image_id, # Use current job's image_id
                gcs_url=cached_data.gcs_url, # gcs_url is content-dependent, so reuse from cache
                alt_text=cached_data.alt_text, # Re-use cached refined alt_text
                caption=cached_data.caption,   # Re-use cached refined caption
                llm_description=cached_data.llm_description, # Re-use cached LLM description
                width=cached_data.width,       # Re-use cached dimensions
                height=cached_data.height,     # Re-use cached dimensions
                original_source_identifier=raw_image.original_source_identifier_for_gcs_path # Use current job's source identifier
            )
            # Optional: A more detailed check or logging if other fields were expected to align with raw_image but come from cache.
            # For example, if raw_image.alt_text could be different from cached_data.alt_text for the same image content
            # and we needed to decide which one to use. Current assumption is cached EIM holds the canonical version of these.
            return updated_cached_data
        
        self.logger.info(f"ImageProcessingService: Cache MISS for key: {cache_key} (image_id: {raw_image.image_id})")

        # The rest of the processing logic remains largely the same using current_image_bytes
        metadata = await self._get_image_metadata(current_image_bytes)
        if metadata.get("error"):
            error_messages.append(metadata["error"])
            self.logger.warning(f"ImageProcessingService: Filtering out image {raw_image.image_id} (source: {raw_image.source_url or raw_image.original_filename}) due to metadata extraction error: {metadata['error']}.")
            return None # Filter out images where metadata extraction failed

        # --- Apply Image Filtering Logic ---
        # This block will now only be reached if metadata extraction was successful
        img_width = metadata.get("width")
        img_height = metadata.get("height")

        if img_width is not None and img_height is not None: # Dimensions are available
            if img_width < self.MIN_IMG_WIDTH_PX or img_height < self.MIN_IMG_HEIGHT_PX:
                self.logger.info(f"ImageProcessingService: Filtering out image {raw_image.image_id} (source: {raw_image.source_url or raw_image.original_filename}) due to small dimension (W:{img_width} < {self.MIN_IMG_WIDTH_PX} or H:{img_height} < {self.MIN_IMG_HEIGHT_PX}).")
                return None
            if (img_width * img_height) < self.MIN_IMG_AREA:
                self.logger.info(f"ImageProcessingService: Filtering out image {raw_image.image_id} (source: {raw_image.source_url or raw_image.original_filename}) due to small area (Area:{img_width * img_height} < MinArea:{self.MIN_IMG_AREA}).")
                return None
            if img_height > 0 and (img_width / img_height) > self.MAX_IMG_ASPECT_RATIO_DEVIATION:
                self.logger.info(f"ImageProcessingService: Filtering out image {raw_image.image_id} (source: {raw_image.source_url or raw_image.original_filename}) due to aspect ratio (W:{img_width}/H:{img_height} > MaxDev:{self.MAX_IMG_ASPECT_RATIO_DEVIATION}).")
                return None
            if img_width > 0 and (img_height / img_width) > self.MAX_IMG_ASPECT_RATIO_DEVIATION:
                self.logger.info(f"ImageProcessingService: Filtering out image {raw_image.image_id} (source: {raw_image.source_url or raw_image.original_filename}) due to aspect ratio (H:{img_height}/W:{img_width} > MaxDev:{self.MAX_IMG_ASPECT_RATIO_DEVIATION}).")
                return None
        # else: dimensions not available, cannot apply dimension-based filters.
        # This path should ideally not be taken if metadata extraction succeeded without error
        # but width/height were somehow still None. Log if it happens.
        else:
            self.logger.warning(f"ImageProcessingService: Image {raw_image.image_id} had no metadata error, but width/height are None. Skipping dimension filters.")

        # Alt text filtering
        alt_text_lower = (raw_image.alt_text or "").lower()
        if alt_text_lower:
            if alt_text_lower in self.IRRELEVANT_ALT_TEXT_EXACT:
                self.logger.info(f"ImageProcessingService: Filtering out image {raw_image.image_id} due to exact match in irrelevant alt text: '{raw_image.alt_text}'.")
                return None
            if any(sub in alt_text_lower for sub in self.IRRELEVANT_ALT_TEXT_SUBSTRINGS):
                self.logger.info(f"ImageProcessingService: Filtering out image {raw_image.image_id} due to substring match in irrelevant alt text: '{raw_image.alt_text}'.")
                return None

        # Filename/URL segment filtering
        source_identifier_lower = (raw_image.source_url or raw_image.original_filename or "").lower()
        if source_identifier_lower:
            if any(segment in source_identifier_lower for segment in self.IRRELEVANT_FILENAME_URL_SEGMENTS):
                self.logger.info(f"ImageProcessingService: Filtering out image {raw_image.image_id} due to irrelevant segment in URL/filename: '{source_identifier_lower}'.")
                return None

        gcs_url: Optional[str] = None
        if self.gcs_client and self.gcs_bucket_name:
            file_ext = os.path.splitext(raw_image.original_filename or raw_image.image_id)[1] or (f".{metadata.get('format', 'img').lower()}" if metadata.get('format') else ".img")
            sanitized_source_id = self._sanitize_for_gcs_path(raw_image.original_source_identifier_for_gcs_path.split("/")[-1].split(".")[0])
            gcs_blob_name = f"{raw_image.source_type_for_gcs_path}/{sanitized_source_id}/{raw_image.job_id_for_gcs_path}/{raw_image.image_id}{file_ext}"
            
            gcs_result = await self._upload_to_gcs(current_image_bytes, gcs_blob_name, metadata.get("mime_type"))
            gcs_url = gcs_result.get("gcs_url")
            if gcs_result.get("error"):
                error_messages.append(gcs_result["error"])
                self.logger.error(f"ImageProcessingService: GCS upload failed for {raw_image.image_id}: {gcs_result.get('error')}", exc_info=True)
                return None 
        elif not self.gcs_bucket_name: 
            error_messages.append("GCS bucket not configured; cannot upload.")
            self.logger.warning(f"ImageProcessingService: GCS not configured. Image {raw_image.image_id} not uploaded.")
        
        llm_description: Optional[str] = None
        llm_caption_override: Optional[str] = raw_image.caption

        if self.use_llm_for_image_analysis and self.image_analysis_tool:
            self.logger.info(f"ImageProcessingService: LLM analyzing image {raw_image.image_id}")
            loop = asyncio.get_event_loop()
            analysis_input = ImageAnalysisInput(
                image_bytes=current_image_bytes,
                text_context=raw_image.alt_text or raw_image.caption 
            )
            tool_call_with_args = functools.partial(self.image_analysis_tool._run, **analysis_input.model_dump())
            llm_analysis_result_dict = await loop.run_in_executor(None, tool_call_with_args)
            
            llm_analysis_output = ImageAnalysisOutput(**llm_analysis_result_dict)
            if llm_analysis_output.error_message:
                error_messages.append(f"LLM analysis error: {llm_analysis_output.error_message}")
            else:
                llm_description = llm_analysis_output.description
                if llm_analysis_output.caption: 
                    llm_caption_override = llm_analysis_output.caption
        
        final_image_data = EnrichedImageMetadata(
            image_id=raw_image.image_id, 
            gcs_url=gcs_url,
            alt_text=raw_image.alt_text,
            caption=llm_caption_override,
            llm_description=llm_description,
            width=metadata.get("width"),
            height=metadata.get("height"),
            original_source_identifier=raw_image.original_source_identifier_for_gcs_path 
        )

        if error_messages:
            self.logger.warning(f"ImageProcessingService: Note - Errors during processing of {raw_image.image_id}: {'; '.join(error_messages)}")

        # Store in cache only if successfully processed (gcs_url might be None if GCS is not configured, but that's still a valid 'processed' state)
        # However, if critical steps like download or metadata failed, final_image_data might be None or incomplete.
        # The current logic returns None from _process_single_image on critical failures before EnrichedImageMetadata is created.
        # So, if we get an EnrichedImageMetadata object, it means major processing steps were attempted.
        if final_image_data: # final_image_data is an EnrichedImageMetadata object here
             self.processing_cache[cache_key] = final_image_data

        return final_image_data

    async def execute(self, service_input: ImageProcessingServiceInput) -> ServiceResult[List[EnrichedImageMetadata]]:
        start_time = time.time()
        processed_images_list: List[EnrichedImageMetadata] = []
        failed_image_ids: List[str] = []

        tasks = [self._process_single_image(raw_image) for raw_image in service_input.images_to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            raw_image_input = service_input.images_to_process[i]
            if isinstance(result, EnrichedImageMetadata):
                processed_images_list.append(result)
            elif isinstance(result, Exception):
                self.logger.error(f"ImageProcessingService: Exception processing image {raw_image_input.image_id}: {result}", exc_info=True)
                failed_image_ids.append(raw_image_input.image_id)
            elif result is None: 
                self.logger.warning(f"ImageProcessingService: Image {raw_image_input.image_id} was not processed successfully (returned None).")
                failed_image_ids.append(raw_image_input.image_id)
        
        duration = time.time() - start_time
        status_message = f"Processed {len(processed_images_list)} out of {len(service_input.images_to_process)} images, {len(failed_image_ids)} failed."
        self.logger.info(f"ImageProcessingService: Completed in {duration:.2f}s. {status_message}")

        if failed_image_ids and not processed_images_list:
            failure_summary = f"All {len(failed_image_ids)} images failed processing. First failure on: {failed_image_ids[0] if failed_image_ids else 'N/A'}."
            return ServiceResult.failure(error_message=failure_summary, error_details={"failed_ids": failed_image_ids, "summary": status_message})
        
        return ServiceResult.success(data=processed_images_list)

# Ensure pydantic.HttpUrl is still relevant or remove if not used.
# The imported RawImageInput uses Optional[str] for source_url, not HttpUrl.
# So HttpUrl import might be removable.