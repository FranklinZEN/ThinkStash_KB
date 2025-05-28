# Placeholder for TS-AI-Reconstruct-4: Image Processing & Persistence Agent 

from crewai import Agent, Task
from typing import List, Type, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import os
import uuid # For unique GCS blob names or temp folders
import json # For loading data from DataStore if stored as JSON strings
import re # For sanitizing text for path

# Tool Imports
from app.tools.content_processing_tools import ImageDownloaderTool, GCSUploadTool, ImageMetadataTool
from app.tools.utility_tools import DataStoreAccessTool

# Model Imports
from app.models.image_processing_models import ImageProcessingInput, ImageProcessingOutput
# ProcessedImageData is used for the items in the output list. It's defined in orchestration_models.
from app.models.orchestration_models import ProcessedImageData 
# Input image list item types from other agents' models
from app.models.pdf_acquisition_models import RawPDFImageWithID
from app.models.file_acquisition_models import RawOrLinkedImage
from app.models.web_acquisition_models import ExtractedImageURLWithID

class ImageProcessingPersistenceAgent:
    """Centralized image handling: downloads, GCS upload, metadata consolidation (V2.4)."""

    def __init__(self, 
                 image_downloader_tool: ImageDownloaderTool,
                 gcs_upload_tool: GCSUploadTool,
                 image_metadata_tool: ImageMetadataTool,
                 data_store_tool: DataStoreAccessTool):
        
        self.image_downloader_tool = image_downloader_tool
        self.gcs_upload_tool = gcs_upload_tool
        self.image_metadata_tool = image_metadata_tool
        self.data_store_tool = data_store_tool
        
        agent_tools = [
            self.image_downloader_tool, 
            self.gcs_upload_tool, 
            self.image_metadata_tool, 
            self.data_store_tool
        ]
        self.agent_instance = self._create_agent_instance(agent_tools)

    def _create_agent_instance(self, configured_tools: List[BaseModel]) -> Agent:
        return Agent(
            role='Image Processing and Persistence Specialist for V2.4',
            goal=('Receive lists of image references (raw data, file paths, or URLs with IDs) from acquisition agents. ' 
                  'Download URL-based images. Upload all valid images to GCS. Consolidate metadata (captions, alt-text, dimensions, GCS URL, original ID). ' 
                  'Store a list of ProcessedImageData objects using DataStoreAccessTool and return the reference.'),
            backstory=(
                "You are the dedicated image handler for the CoreReconstructionCrew. When content acquisition agents find images (either embedded, like in PDFs/DOCX, or linked, like in MD/web), they pass you references to these images along with their source-specific IDs and any preliminary metadata. " 
                "Your job is to: 1. Fetch image references from the DataStore. 2. If images are URLs, download them using ImageDownloaderTool. 3. Upload every valid image (downloaded or directly provided as raw data/path) to Google Cloud Storage using GCSUploadTool, ensuring unique blob names. 4. Use ImageMetadataTool to get dimensions/MIME types. 5. Consolidate all metadata (original ID, GCS URL, alt-text, captions, dimensions, etc.) into a standardized ProcessedImageData format. " 
                "Finally, you store this list of ProcessedImageData objects back into the DataStore and provide a reference to it for the final content structuring agent."
            ),
            tools=configured_tools,
            verbose=True,
            allow_delegation=False 
        )

    def get_agent(self) -> Agent:
        return self.agent_instance

    # --- Agent's Core Logic Method ---
    def execute_image_processing_pipeline(self, input_data: ImageProcessingInput) -> ImageProcessingOutput:
        print(f"ImageProcessingAgent: Starting pipeline for source: {input_data.original_source_identifier}, type: {input_data.source_type}")
        
        final_processed_images_data_list: List[ProcessedImageData] = []
        agent_status = "success_no_images_provided" 
        agent_error_message: Optional[str] = None
        images_processed_count = 0
        images_failed_count = 0
        
        # This will store unique original_source_identifiers of images to avoid reprocessing if referenced multiple times
        # For this agent, though, each item in lists should be unique already (e.g. PDF_P1_IMG1, WEB_IMG_1)
        processed_original_ids = set()

        image_sources_to_process: List[Dict[str, Any]] = [] # To hold consolidated image items

        # 1. Consolidate image references from different acquisition agents
        if input_data.pdf_image_list_ref:
            try:
                pdf_images: List[Dict] = self.data_store_tool._run(action="get", key=input_data.pdf_image_list_ref)
                if pdf_images and isinstance(pdf_images, list):
                    for item_dict in pdf_images:
                        img_item = RawPDFImageWithID(**item_dict) # Validate with Pydantic
                        # Resolve the raw_image_data_ref to an actual path (it was stored as path by PDF agent)
                        actual_image_path = self.data_store_tool._run(action="get", key=img_item.raw_image_data_ref)
                        if actual_image_path and isinstance(actual_image_path, str) and os.path.exists(actual_image_path):
                            image_sources_to_process.append({
                                "type": "path", 
                                "value": actual_image_path, 
                                "original_id": img_item.image_id,
                                "alt_text": None, # PDF images don't typically have alt text from source
                                "caption": img_item.caption, # From multimodal LLM
                                "llm_description": img_item.description # From multimodal LLM
                            })
                        else:
                            print(f"IPAgent: WARNING - Could not resolve or find path for PDF image ref: {img_item.raw_image_data_ref} (id: {img_item.image_id})")
                            images_failed_count +=1
                            agent_error_message = (agent_error_message + "; " if agent_error_message else "") + f"Path resolve fail: {img_item.image_id}"
                agent_status = "processing_started" # Status update
            except Exception as e:
                print(f"IPAgent: ERROR - Failed to retrieve/process PDF image list from ref {input_data.pdf_image_list_ref}: {e}")
                images_failed_count +=1 # Count as one major failure for the list
                agent_error_message = (agent_error_message + "; " if agent_error_message else "") + f"PDF list error: {e}"

        if input_data.generic_file_image_list_ref:
            try:
                generic_images: List[Dict] = self.data_store_tool._run(action="get", key=input_data.generic_file_image_list_ref)
                if generic_images and isinstance(generic_images, list):
                    for item_dict in generic_images:
                        img_item = RawOrLinkedImage(**item_dict)
                        if img_item.source_path_or_url:
                            is_url = img_item.source_path_or_url.startswith(("http://", "https://"))
                            image_sources_to_process.append({
                                "type": "url" if is_url else "path", 
                                "value": img_item.source_path_or_url, 
                                "original_id": img_item.image_id,
                                "alt_text": img_item.alt_text, # From MD
                                "caption": None, # Not typically from MD parser for generic files
                                "llm_description": None
                            })
                        # Potentially handle img_item.raw_data_ref if generic files could store raw image data directly
                        # For now, assuming source_path_or_url is primary for generic files
                agent_status = "processing_started"
            except Exception as e:
                print(f"IPAgent: ERROR - Failed to retrieve/process Generic File image list from ref {input_data.generic_file_image_list_ref}: {e}")
                images_failed_count +=1
                agent_error_message = (agent_error_message + "; " if agent_error_message else "") + f"Generic list error: {e}"

        if input_data.web_image_list_ref:
            try:
                web_images_json_str = self.data_store_tool._run(action="get", key=input_data.web_image_list_ref)
                if web_images_json_str and isinstance(web_images_json_str, str):
                    web_images_list_of_dicts = json.loads(web_images_json_str)
                    if web_images_list_of_dicts and isinstance(web_images_list_of_dicts, list):
                        for item_dict in web_images_list_of_dicts:
                            if isinstance(item_dict, dict): # Ensure item is a dict before Pydantic conversion
                                img_item = ExtractedImageURLWithID(**item_dict)
                                image_sources_to_process.append({
                                    "type": "url", 
                                    "value": str(img_item.image_url), # Ensure str from HttpUrl
                                    "original_id": img_item.image_id,
                                    "alt_text": img_item.alt_text, 
                                    "caption": None, 
                                    "llm_description": None
                                })
                            else:
                                print(f"IPAgent: WARNING - Item in web_images_list_of_dicts is not a dict: {item_dict}")
                                images_failed_count +=1
                        agent_status = "processing_started"
                    else:
                        print(f"IPAgent: WARNING - Parsed web_images_json_str is not a list: {web_images_list_of_dicts}")
                        images_failed_count +=1
                elif web_images_json_str: # It was retrieved but not a string (should not happen with current DS tool)
                    print(f"IPAgent: WARNING - Retrieved web_images data is not a string: {type(web_images_json_str)}")
                    images_failed_count +=1

            except json.JSONDecodeError as je:
                print(f"IPAgent: ERROR - JSONDecodeError for web image list from ref {input_data.web_image_list_ref}: {je}. Content: '{web_images_json_str[:200]}...'")
                images_failed_count +=1
                agent_error_message = (agent_error_message + "; " if agent_error_message else "") + f"Web list JSON error: {je}"
            except Exception as e:
                print(f"IPAgent: ERROR - Failed to retrieve/process Web image list from ref {input_data.web_image_list_ref}: {e}")
                images_failed_count +=1
                agent_error_message = (agent_error_message + "; " if agent_error_message else "") + f"Web list error: {e}"

        if not image_sources_to_process and agent_status == "success_no_images_provided" and images_failed_count == 0:
            print("IPAgent: No image sources found in any provided list refs.")
            return ImageProcessingOutput(status=agent_status, processed_image_data_list_ref=None, error_message=agent_error_message, images_processed_count=0, images_failed_count=0)
        elif not image_sources_to_process and images_failed_count > 0:
             print(f"IPAgent: No valid image sources to process after errors. Failed count: {images_failed_count}")
             return ImageProcessingOutput(status="error_no_valid_images_to_process", processed_image_data_list_ref=None, error_message=agent_error_message, images_processed_count=0, images_failed_count=images_failed_count)

        # 2. Process each consolidated image item
        print(f"IPAgent: Consolidated {len(image_sources_to_process)} image sources to process.")
        for image_source in image_sources_to_process:
            if image_source["original_id"] in processed_original_ids:
                print(f"IPAgent: Skipping already processed original_id: {image_source['original_id']}")
                continue

            processed_image_data: Optional[ProcessedImageData] = None
            if image_source["type"] == "path":
                processed_image_data = self._process_single_image_from_path(
                    image_local_path=image_source["value"],
                    original_id_from_source=image_source["original_id"],
                    original_source_identifier=input_data.original_source_identifier,
                    source_type=input_data.source_type,
                    job_id=input_data.job_id,
                    alt_text_from_source=image_source.get("alt_text"),
                    caption_from_source=image_source.get("caption"),
                    llm_desc_from_source=image_source.get("llm_description")
                )
            elif image_source["type"] == "url":
                processed_image_data = self._process_single_image_from_url(
                    image_url=image_source["value"],
                    original_id_from_source=image_source["original_id"],
                    original_source_identifier=input_data.original_source_identifier,
                    source_type=input_data.source_type,
                    job_id=input_data.job_id,
                    alt_text_from_source=image_source.get("alt_text"),
                    caption_from_source=image_source.get("caption"),
                    llm_desc_from_source=image_source.get("llm_description")
                )
            
            if processed_image_data:
                final_processed_images_data_list.append(processed_image_data)
                processed_original_ids.add(image_source["original_id"])
                images_processed_count += 1
            else:
                images_failed_count += 1
                err_msg = f"Processing failed for: {image_source['original_id']} ({image_source['value']})"
                agent_error_message = (agent_error_message + "; " if agent_error_message else "") + err_msg
                print(f"IPAgent: {err_msg}")

        # 3. Store the final list and return status
        final_list_ref: Optional[str] = None
        if final_processed_images_data_list:
            # Store as a list of dicts for JSON compatibility in DataStore
            final_list_as_dicts = [pid.model_dump() for pid in final_processed_images_data_list]
            final_list_key = f"processed_images_{self._sanitize_for_path(input_data.original_source_identifier)}_{input_data.job_id}"
            self.data_store_tool._run(action="put", key=final_list_key, value=final_list_as_dicts)
            final_list_ref = final_list_key
            print(f"IPAgent: Stored final list of {len(final_processed_images_data_list)} processed image data to DataStore with key: {final_list_key}")

        if images_failed_count > 0 and images_processed_count > 0:
            agent_status = "partial_success_images_processed"
        elif images_failed_count > 0 and images_processed_count == 0:
            agent_status = "error_all_images_failed"
        elif images_failed_count == 0 and images_processed_count > 0:
            agent_status = "success_images_processed"
        elif images_failed_count == 0 and images_processed_count == 0 and agent_status == "processing_started":
            # This case means lists were provided, but they were empty or all refs failed to resolve before processing stage
            agent_status = "success_no_images_found_in_refs"
        # else agent_status remains as initialized ('success_no_images_provided' or updated by list retrieval errors)

        return ImageProcessingOutput(
            status=agent_status,
            processed_image_data_list_ref=final_list_ref,
            error_message=agent_error_message,
            images_processed_count=images_processed_count,
            images_failed_count=images_failed_count
        )

    def _fetch_image_references(self, input_data: ImageProcessingInput) -> Union[List[Dict[str, Any]], str]:
        ref_to_fetch = input_data.pdf_image_list_ref or \
                       input_data.generic_file_image_list_ref or \
                       input_data.web_image_list_ref
        if not ref_to_fetch:
            return []
        try:
            retrieved_data = self.data_store_tool._run(action="get", key=ref_to_fetch)
            if retrieved_data:
                if isinstance(retrieved_data, str):
                    try: return json.loads(retrieved_data)
                    except json.JSONDecodeError as je: return f"Error JSON decoding: {je}"
                elif isinstance(retrieved_data, list):
                    return retrieved_data 
                return f"Unexpected data type from DataStore: {type(retrieved_data)}"
            return f"No data for ref: {ref_to_fetch}"
        except Exception as e: return f"Exception fetching from DataStore: {e}"

    def _sanitize_for_path(self, text: Optional[str], max_length: int = 100) -> str:
        if not text: return f"untitled_{uuid.uuid4().hex[:6]}" # More unique untitled
        text = re.sub(r'^https?://', '', text) # Remove http(s):// prefix
        text = re.sub(r'[^a-zA-Z0-9._-]', '_', text) # Replace non-alphanumeric (except ., _, -) with _
        text = re.sub(r'_+', '_', text) # Collapse multiple underscores
        text = text.strip('_') # Trim leading/trailing underscores
        return text[:max_length]

    # --- Task Definition for Agent (Conceptual) ---
    def task_process_and_persist_images(self, agent_to_use: Agent, input_data: ImageProcessingInput) -> Task:
        return Task(
            description=(
                f"Process and persist images for source: {input_data.original_source_identifier} (type: {input_data.source_type}). "
                f"Fetch image refs, download URL images, upload all to GCS, consolidate metadata, store ProcessedImageData list ref."
            ),
            expected_output=(
                "An ImageProcessingOutput model as a dictionary, with status and reference to the list of ProcessedImageData objects, or error details."
            ),
            agent=agent_to_use,
        )

    def _process_single_image_from_path(self, 
                                        image_local_path: str, 
                                        original_id_from_source: str, 
                                        original_source_identifier: str, # e.g. main PDF/DOCX path
                                        source_type: str, # e.g. pdf, docx
                                        job_id: str,
                                        alt_text_from_source: Optional[str] = None,
                                        caption_from_source: Optional[str] = None,
                                        llm_desc_from_source: Optional[str] = None) -> Optional[ProcessedImageData]:
        print(f"IPAgent: Processing local image path: {image_local_path} (orig_id: {original_id_from_source})")
        if not os.path.exists(image_local_path):
            print(f"IPAgent: ERROR - Local image path not found: {image_local_path}")
            return None

        metadata_result = self.image_metadata_tool._run(image_file_path=image_local_path)
        width = metadata_result.get("width")
        height = metadata_result.get("height")
        mime_type = metadata_result.get("mime_type", "application/octet-stream")

        file_ext = os.path.splitext(image_local_path)[1] or ".png" # Default to .png if no ext
        # Sanitize original_source_identifier for use in GCS path
        sanitized_source_id_path_part = self._sanitize_for_path(original_source_identifier.split("/")[-1].split(".")[0])
        
        # Construct a more structured GCS blob name
        gcs_blob_name = f"{source_type}/{sanitized_source_id_path_part}/{job_id}/{original_id_from_source}_{uuid.uuid4().hex[:6]}{file_ext}"
        
        print(f"IPAgent: Uploading {image_local_path} to GCS as {gcs_blob_name}")
        upload_result = self.gcs_upload_tool._run(local_file_path=image_local_path, gcs_blob_name=gcs_blob_name)

        if upload_result.get("error"):
            print(f"IPAgent: ERROR - GCS Upload failed for {image_local_path}: {upload_result['error']}")
            return None
        
        gcs_url = upload_result.get("gcs_url")
        # public_url_available = upload_result.get("public_url_available") # Not directly used in ProcessedImageData currently

        return ProcessedImageData(
            original_source_identifier=original_id_from_source, # This is the ID like PDF_P1_IMG1
            gcs_url=gcs_url,
            # public_url=public_url_available, # If we want to store it
            width=width,
            height=height,
            mime_type=mime_type,
            alt_text=alt_text_from_source,
            caption=caption_from_source, # Use caption from source if available (e.g., from PDF agent's LLM tool)
            llm_description=llm_desc_from_source, # Use LLM description from source if available
            # context_around_image - This would need to be passed down or retrieved if required here
        )

    def _process_single_image_from_url(self, 
                                        image_url: str, 
                                        original_id_from_source: str, 
                                        original_source_identifier: str, 
                                        source_type: str, 
                                        job_id: str,
                                        alt_text_from_source: Optional[str] = None,
                                        caption_from_source: Optional[str] = None,
                                        llm_desc_from_source: Optional[str] = None) -> Optional[ProcessedImageData]:
        print(f"IPAgent: Processing image URL: {image_url} (orig_id: {original_id_from_source})")
        
        temp_download_folder = f"temp_image_downloads_{job_id}_{uuid.uuid4().hex[:8]}"
        download_result = self.image_downloader_tool._run(image_url=image_url, output_folder=temp_download_folder)

        if download_result.get("error") or not download_result.get("local_path"):
            print(f"IPAgent: ERROR - Failed to download {image_url}: {download_result.get('error')}")
            if os.path.exists(temp_download_folder): # Clean up folder if download failed but folder was made
                try: 
                    import shutil
                    shutil.rmtree(temp_download_folder)
                except Exception as e_clean_fail: print(f"IPAgent: Error cleaning up temp folder {temp_download_folder} after failed download: {e_clean_fail}")
            return None

        local_path = download_result["local_path"]
        processed_data = self._process_single_image_from_path(
            image_local_path=local_path,
            original_id_from_source=original_id_from_source,
            original_source_identifier=original_source_identifier,
            source_type=source_type,
            job_id=job_id,
            alt_text_from_source=alt_text_from_source,
            caption_from_source=caption_from_source, # Pass through any metadata from source
            llm_desc_from_source=llm_desc_from_source
        )

        # Clean up the temporary downloaded file and folder
        if os.path.exists(temp_download_folder):
            try:
                import shutil
                shutil.rmtree(temp_download_folder) # This removes the folder and its contents
                print(f"IPAgent: Cleaned up temporary download folder: {temp_download_folder}")
            except Exception as e_clean:
                print(f"IPAgent: ERROR - Failed to clean up temp download folder {temp_download_folder}: {e_clean}")
        
        return processed_data

# Agent-specific methods for the image processing workflow could be added here.
# def process_and_persist_images(self, image_references_list):
#     # 1. Download images if they are URLs
#     # 2. Upload all images (downloaded or from local paths) to GCS
#     # 3. Consolidate metadata for each image
#     # 4. Return list of ProcessedImageData objects
#     pass

# Methods for downloading, GCS upload, metadata consolidation will be added. 