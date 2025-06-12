#!/usr/bin/env python
# coding: utf-8
"""Defines tools for content processing within CrewAI agents."""

import requests
from PIL import Image # Pillow for image metadata
from google.cloud import storage # Google Cloud Storage
from crewai.tools import BaseTool
import os
import uuid # For generating unique filenames
import io # For handling image bytes
from aiservice.app.config.settings import settings # Corrected import for V2.5 settings
from aiservice.app.models.orchestration_models import ContentBlock # Corrected import
from typing import List, Dict, Any
from langchain_core.tools import tool
from pydantic import BaseModel, Field # Assuming Pydantic v2
from markdownify import markdownify as md # For converting HTML to Markdown

class ImageDownloaderTool(BaseTool):
    name: str = "Image Downloader from URL"
    description: str = (
        "Downloads an image from a given URL and saves it to a specified temporary local folder. "
        "Input: 'image_url' (string: the URL of the image to download), "
        "'output_folder' (string: local folder to save the downloaded image, defaults to 'temp_downloaded_images')."
        "Returns a dictionary with 'local_path' (string) to the saved image, 'original_url' (string), "
        "'filename' (string), 'content_type' (string) from response headers, and 'error' (string, if any)."
    )

    def _run(self, image_url: str, output_folder: str = "temp_downloaded_images") -> dict:
        """Downloads an image from a URL or confirms a local file path.

        Args:
            image_url: The URL of the image or a local file path.
            output_folder: Local folder to save the image if downloaded.

        Returns:
            A dictionary with image details or an error message.
        """
        # Check if image_url is a local path first
        if isinstance(image_url, str) and os.path.exists(image_url):
            print(f"ImageDownloaderTool: Identified '{image_url}' as an existing local file path.")
            # For local files, we don't download. We just confirm its existence and format the output.
            filename = os.path.basename(image_url)
            # Try to guess content type for local files, similar to GCSUploadTool
            ext = os.path.splitext(filename)[1].lower()
            content_type_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp',
                '.tiff': 'image/tiff'
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')
            return {
                "local_path": image_url, # It's already local
                "original_url": image_url, # Treat path as original identifier
                "filename": filename,
                "content_type": content_type,
                "error": None
            }

        if not isinstance(image_url, str) or not image_url.startswith(('http://', 'https://')):
            return {"error": "Invalid image URL or non-existent local path provided.", "local_path": None}

        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder, exist_ok=True)
            except OSError as e:
                return {"error": f"Could not create output folder {output_folder}: {e}", "local_path": None}
        
        try:
            response = requests.get(image_url, stream=True, timeout=20)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', 'application/octet-stream')
            # Basic check for image content types
            if not content_type.lower().startswith('image/'):
                return {"error": f"URL does not point to a recognized image type. Content-Type: {content_type}", "local_path": None, "original_url": image_url}

            # Generate a unique filename to avoid collisions
            file_extension = '.' + content_type.split('/')[-1].split(';')[0] # e.g., .jpeg, .png
            if file_extension == '.None' or len(file_extension) > 5 : # Basic sanity check for extension
                 # Try to guess from URL if content_type is too generic (e.g. application/octet-stream for a .png link)
                if image_url.lower().endswith('.png'): file_extension = '.png'
                elif image_url.lower().endswith(('.jpg', '.jpeg')): file_extension = '.jpeg'
                elif image_url.lower().endswith('.gif'): file_extension = '.gif'
                else: file_extension = '.img' # Fallback generic extension
            
            filename = str(uuid.uuid4()) + file_extension
            local_file_path = os.path.join(output_folder, filename)

            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return {
                "local_path": local_file_path,
                "original_url": image_url,
                "filename": filename,
                "content_type": content_type,
                "error": None
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Error downloading image {image_url}: {e}", "local_path": None, "original_url": image_url}
        except Exception as e_save:
            return {"error": f"Error saving image {image_url} to {local_file_path}: {e_save}", "local_path": None, "original_url": image_url}

class GCSUploadTool(BaseTool):
    name: str = "Google Cloud Storage (GCS) Image Uploader"
    description: str = (
        "Uploads a local image file to a specified Google Cloud Storage bucket. "
        "Input: 'local_file_path' (string: path to the local image file), "
        "'gcs_blob_name' (string: desired name for the image blob in GCS, should be unique, can include folders e.g., 'folder/image.png')."
        "An optional 'gcs_bucket_name' can be provided if not set during initialization. "
        "Returns a dictionary with 'gcs_url' (string) of the uploaded image and 'error' (string, if any). "
        "NOTE: Requires GCS credentials to be configured in the environment (GOOGLE_APPLICATION_CREDENTIALS)."
    )
    storage_client: storage.Client | None = None
    default_gcs_bucket_name: str | None = None

    def __init__(self, gcs_bucket_name_override: str = None, **kwargs):
        super().__init__(**kwargs)
        # Use override if provided, otherwise use settings, then None
        self.default_gcs_bucket_name = gcs_bucket_name_override or settings.gcs_bucket_name
        
        try:
            self.storage_client = storage.Client()
            current_desc = self.description # Store original description part
            if self.default_gcs_bucket_name:
                 self.description = f"{current_desc} Default bucket configured: {self.default_gcs_bucket_name}."
            else:
                self.description = f"{current_desc} GCS bucket name needs to be provided at runtime as it was not found in settings."
        except Exception as e:
            print(f"CRITICAL: Failed to initialize Google Cloud Storage client: {e}. GCSUploadTool will not work.")
            self.storage_client = None
            self.description += " ERROR: GCS Client not initialized."

    def _run(self, local_file_path: str, gcs_blob_name: str, gcs_bucket_name: str = None) -> dict:
        """Uploads an image to GCS.

        Args:
            local_file_path: Path to the local image file.
            gcs_blob_name: Desired name for the image blob in GCS (e.g., unique_id.png or images/unique_id.png).
            gcs_bucket_name: Optional. GCS bucket name if not set during initialization.

        Returns:
            A dictionary with the GCS URL of the image or an error.
        """
        bucket_name_to_use = gcs_bucket_name or self.default_gcs_bucket_name
        if not self.storage_client:
            return {"error": "GCS client not initialized. Check credentials and setup.", "gcs_url": None}
        if not bucket_name_to_use:
            return {"error": "GCS bucket name not provided (neither in call nor in config/env).", "gcs_url": None}
        if not isinstance(local_file_path, str) or not os.path.exists(local_file_path):
            return {"error": f"Local file not found or invalid path: {local_file_path}", "gcs_url": None}
        if not isinstance(gcs_blob_name, str) or not gcs_blob_name.strip():
            return {"error": "Invalid GCS blob name provided.", "gcs_url": None}

        try:
            bucket = self.storage_client.bucket(bucket_name_to_use)
            blob = bucket.blob(gcs_blob_name)
            
            # Determine content type from file extension for GCS metadata (basic)
            # More robust would be to use python-magic or get from ImageMetadataTool if available
            ext = os.path.splitext(local_file_path)[1].lower()
            content_type_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            gcs_content_type = content_type_map.get(ext, 'application/octet-stream')

            blob.upload_from_filename(local_file_path, content_type=gcs_content_type)
            # Making the blob public for this example; adjust permissions as needed for your application
            # blob.make_public() 
            # return {"gcs_url": blob.public_url, "error": None} 
            # Using a gs:// URI format is often more standard for internal references
            gs_uri = f"gs://{bucket_name_to_use}/{gcs_blob_name}"
            # Attempt to get a public URL if needed, but permissions might prevent this by default
            # For signed URLs, more complex logic is needed.
            public_url = None
            try:
                 # blob.make_public() # Requires specific GCS permissions; avoid by default
                 public_url = blob.public_url # This might error if not public or if permissions are wrong
            except Exception as e_public_url:
                print(f"Note: Could not retrieve public_url for GCS blob {gs_uri}: {e_public_url}. Blob might not be public.")

            return {"gcs_url": gs_uri, "public_url_available": public_url, "error": None}

        except Exception as e:
            return {"error": f"Error uploading {local_file_path} to GCS gs://{bucket_name_to_use}/{gcs_blob_name}: {e}", "gcs_url": None}

class ImageMetadataTool(BaseTool):
    name: str = "Image File Metadata Extractor"
    description: str = (
        "Extracts metadata (dimensions: width, height; format/MIME type) from a local image file using Pillow. "
        "Input: 'image_file_path' (string: path to the local image file)."
        "Returns a dictionary with 'width', 'height', 'format', 'mime_type', and 'error' (if any)."
    )

    def _run(self, image_file_path: str) -> dict:
        """Extracts metadata from a local image file.

        Args:
            image_file_path: Path to the local image file.

        Returns:
            A dictionary with image metadata or an error.
        """
        if not isinstance(image_file_path, str) or not os.path.exists(image_file_path):
            return {"error": f"Image file not found or invalid path: {image_file_path}"}

        try:
            with Image.open(image_file_path) as img:
                width, height = img.size
                img_format = img.format
                mime_type = Image.MIME.get(img_format.upper()) # Pillow provides common MIME types
            return {
                "width": width,
                "height": height,
                "format": img_format,
                "mime_type": mime_type,
                "error": None
            }
        except Exception as e:
            return {"error": f"Error extracting metadata from image {image_file_path}: {e}"}

class FullTextContentExtractorTool(BaseTool):
    name: str = "Full Text Content Extractor Tool"
    description: str = (
        "Extracts and concatenates all textual content from a list of content block dictionaries. "
        "Input must be a list of dictionaries, where each dictionary represents a content block. "
        "The key in the kickoff inputs should be 'content_block_dicts'."
    )

    def _run(self, content_block_dicts: List[Dict[str, Any]]) -> str:
        """Processes a list of content block dictionaries to extract all text.

        Args:
            content_block_dicts: A list of dictionaries, where each dictionary
                                 is expected to conform to ContentBlock structure.

        Returns:
            A single string concatenating all extracted textual content, separated by newlines.
        """
        input_repr = str(content_block_dicts)
        print(f"[FullTextContentExtractorTool DEBUG] Received content_block_dicts (first 1000 chars): {input_repr[:1000]}{'...' if len(input_repr) > 1000 else ''}")

        full_text: List[str] = []
        
        if not isinstance(content_block_dicts, list):
            error_msg = f"Error: Input content_block_dicts is not a list. Received type: {type(content_block_dicts)}."
            print(f"[FullTextContentExtractorTool ERROR] {error_msg}")
            return error_msg

        parsed_content_blocks: List[ContentBlock] = [] 
        for i, cb_dict in enumerate(content_block_dicts):
            if not isinstance(cb_dict, dict):
                dict_repr = str(cb_dict)
                print(f"[FullTextContentExtractorTool WARNING] Item at index {i} in content_block_dicts is not a dictionary. Skipping. Item (first 200 chars): {dict_repr[:200]}{'...' if len(dict_repr) > 200 else ''}")
                continue
            try:
                block = ContentBlock(**cb_dict)
                parsed_content_blocks.append(block)
            except Exception as e:
                dict_repr = str(cb_dict)
                print(f"[FullTextContentExtractorTool WARNING] Failed to parse content_block_dict at index {i} into ContentBlock: {e}. Dict (first 200 chars): {dict_repr[:200]}{'...' if len(dict_repr) > 200 else ''}. Skipping this block.")
                continue

        if not parsed_content_blocks and content_block_dicts: 
            error_msg = "Error: Could not parse any input content blocks for text extraction."
            print(f"[FullTextContentExtractorTool ERROR] {error_msg} All {len(content_block_dicts)} input dicts failed parsing.")
            return error_msg
        
        print(f"[FullTextContentExtractorTool DEBUG] Successfully parsed {len(parsed_content_blocks)} ContentBlock Pydantic objects out of {len(content_block_dicts)} input dicts.")

        for block_idx, block in enumerate(parsed_content_blocks):
            extracted_text_from_block = ""

            # Prioritize block.content for types where it's the primary text holder as per ContentBlock model
            if block.type in ["text", "heading", "code_snippet", "math_text"]:
                if block.content and isinstance(block.content, str) and block.content.strip():
                    extracted_text_from_block = block.content.strip()
            # Special handling for 'table' type if its textual content is in block.content (e.g. HTML string)
            # Or if it needs parsing from block.rows (more structured)
            elif block.type == "table":
                table_text_parts = []
                # Scenario 1: block.content is a simple string (e.g., a pre-rendered HTML table or descriptive text)
                if isinstance(block.content, str) and block.content.strip():
                    table_text_parts.append(block.content.strip())
                    # TODO: Consider if HTML tables in block.content need further parsing to extract clean text

                # Scenario 2: block.content is a dictionary containing structured table data like 'rows'
                elif isinstance(block.content, dict):
                    # Check for a title or caption for the table within the content dictionary
                    table_title = block.content.get('title')
                    if table_title and isinstance(table_title, str) and table_title.strip():
                        table_text_parts.append(f"Table Title: {table_title.strip()}")
                    
                    table_caption = block.content.get('caption')
                    if table_caption and isinstance(table_caption, str) and table_caption.strip():
                        table_text_parts.append(f"Table Caption: {table_caption.strip()}")

                    actual_rows = block.content.get('rows')
                    if actual_rows and isinstance(actual_rows, list):
                        table_cell_texts: List[str] = []
                        for row_idx, row_obj_any in enumerate(actual_rows):
                            # Assuming row_obj_any could be a dict representing a row, or a list of cells directly
                            # For now, let's assume rows are lists of cells, or dicts with a 'cells' key
                            # This needs to align with how TableBlockRow is defined or how tables are structured in ContentBlock.content
                            
                            cells_to_process = []
                            if isinstance(row_obj_any, dict) and 'cells' in row_obj_any and isinstance(row_obj_any['cells'], list):
                                cells_to_process = row_obj_any['cells']
                            elif isinstance(row_obj_any, list): # If a row is directly a list of cells
                                cells_to_process = row_obj_any
                            else:
                                print(f"[FullTextContentExtractorTool DEBUG] Table row {row_idx} in block {block_idx} is not a recognized list or dict with cells. Skipping row.")
                                continue
                                
                            row_texts: List[str] = []
                            for cell_idx, cell_content_union in enumerate(cells_to_process):
                                cell_text = ""
                                if isinstance(cell_content_union, str) and cell_content_union.strip():
                                    cell_text = cell_content_union.strip()
                                elif isinstance(cell_content_union, dict):
                                    if 'text' in cell_content_union and isinstance(cell_content_union['text'], str) and cell_content_union['text'].strip():
                                        cell_text = cell_content_union['text'].strip()
                                    elif 'content' in cell_content_union and isinstance(cell_content_union['content'], str) and cell_content_union['content'].strip():
                                        cell_text = cell_content_union['content'].strip()
                                    # Could add more checks if cells are complex nested blocks
                                if cell_text:
                                    row_texts.append(cell_text)
                            if row_texts:
                                table_cell_texts.append(" | ".join(row_texts))
                        if table_cell_texts:
                            # Join all row strings with newlines to represent table structure
                            table_text_parts.append("\n".join(table_cell_texts))
                    elif actual_rows is not None: # actual_rows exists but is not a list
                         print(f"[FullTextContentExtractorTool WARNING] Table block {block_idx} has 'rows' but it's not a list. Type: {type(actual_rows)}. Skipping row processing.")
                if table_text_parts:
                    extracted_text_from_block = "\n".join(filter(None, table_text_parts)) # Join parts, filter empty
            
            # Handling for 'list' type (ContentBlock.items is List[Union[str, Dict[str, Any]]])
            elif block.type == "list" and block.items:
                list_item_texts: List[str] = []
                for item_obj_union in block.items:
                    item_text = ""
                    if isinstance(item_obj_union, str) and item_obj_union.strip():
                        item_text = item_obj_union.strip()
                    elif isinstance(item_obj_union, dict):
                        # Try to get text from common dict structures if list items are dicts
                        if 'text' in item_obj_union and isinstance(item_obj_union['text'], str) and item_obj_union['text'].strip():
                            item_text = item_obj_union['text'].strip()
                        elif 'content' in item_obj_union and isinstance(item_obj_union['content'], str) and item_obj_union['content'].strip():
                            item_text = item_obj_union['content'].strip()
                    if item_text:
                        list_item_texts.append(item_text)
                if list_item_texts:
                    extracted_text_from_block = "\n".join(list_item_texts) # Join list items with a single newline

            # Handling for 'image' type (extract alt_text and caption if available)
            elif block.type == "image":
                img_texts = []
                if block.alt_text and isinstance(block.alt_text, str) and block.alt_text.strip():
                    img_texts.append(f"Image Alt Text: {block.alt_text.strip()}")
                if block.caption and isinstance(block.caption, str) and block.caption.strip():
                    img_texts.append(f"Image Caption: {block.caption.strip()}")
                if img_texts:
                    extracted_text_from_block = "; ".join(img_texts)
            
            # Note: The ContentBlock model does not show a dedicated 'list_item', 'code', or 'quote' type with a 'text' field.
            # 'code_snippet' uses 'content'. If there are other types like 'quote' from Trafilatura output, they need specific handling
            # or mapping to one of the defined ContentBlock types during upstream processing.

            if extracted_text_from_block:
                full_text.append(extracted_text_from_block)
                log_text = extracted_text_from_block.replace('\n', ' ')
                print(f"[FullTextContentExtractorTool DEBUG] Extracted from block {block_idx} (type: {block.type}, ID: {block.block_id if hasattr(block, 'block_id') and block.block_id else 'N/A'}): '{log_text[:150]}{'...' if len(log_text) > 150 else ''}'")
            else:
                print(f"[FullTextContentExtractorTool DEBUG] No text extracted from block {block_idx} (type: {block.type}, ID: {block.block_id if hasattr(block, 'block_id') and block.block_id else 'N/A'})")

        if not full_text:
            print("[FullTextContentExtractorTool INFO] No textual content found in any of the processed blocks that could be extracted.")
            return "Error: No content available for title generation." 
            
        final_concatenated_text = "\n\n".join(full_text)
        log_final_text = final_concatenated_text.replace('\n', ' ')
        print(f"[FullTextContentExtractorTool DEBUG] Final concatenated text (first 200 chars, newlines replaced): '{log_final_text[:200]}{'...' if len(log_final_text) > 200 else ''}'")
        
        return final_concatenated_text

# Example Usage:
if __name__ == '__main__':
    # ImageDownloaderTool Example
    print("--- ImageDownloaderTool Example ---")
    downloader = ImageDownloaderTool()
    # A small, publicly accessible image for testing
    test_image_url = "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
    download_result = downloader._run(image_url=test_image_url, output_folder="temp_downloads")
    print(download_result)
    if download_result["local_path"] and os.path.exists(download_result["local_path"]):
        downloaded_file_for_next_steps = download_result["local_path"]
        print(f"Downloaded to: {downloaded_file_for_next_steps}")

        # ImageMetadataTool Example
        print("\n--- ImageMetadataTool Example ---")
        meta_tool = ImageMetadataTool()
        metadata_result = meta_tool._run(downloaded_file_for_next_steps)
        print(metadata_result)

        # GCSUploadTool Example (Illustrative - Requires GCS Setup & Credentials)
        print("\n--- GCSUploadTool Example (Illustrative - requires GCS setup) ---")
        # The GCSUploadTool will now try to get bucket name from .env via config.py first
        # You can still override by passing gcs_bucket_name to _run or __init__
        gcs_uploader = GCSUploadTool() # Initialize, it will try to get bucket_name from config
        print(f"GCSUploader Tool Description: {gcs_uploader.description}")

        if gcs_uploader.storage_client and gcs_uploader.default_gcs_bucket_name:
            test_blob_name = f"test_uploads/{str(uuid.uuid4())}_{os.path.basename(downloaded_file_for_next_steps)}"
            upload_result = gcs_uploader._run(local_file_path=downloaded_file_for_next_steps, gcs_blob_name=test_blob_name)
            print(upload_result)
            if upload_result.get("gcs_url"):
                print(f"Uploaded to GCS: {upload_result['gcs_url']}")
                # Note: blob.public_url might not be available depending on GCS permissions.
                if upload_result.get("public_url_available"):
                    print(f"Public URL (if accessible): {upload_result['public_url_available']}")
        elif not gcs_uploader.storage_client:
            print("Skipping GCSUploadTool example: GCS client not initialized (check credentials).")
        else:
            print(f"Skipping GCSUploadTool example: Default GCS bucket name not configured (GCS_BUCKET_NAME in .env or passed to init). Current default: {gcs_uploader.default_gcs_bucket_name}")

        # Cleanup downloaded file
        if os.path.exists(downloaded_file_for_next_steps):
            os.remove(downloaded_file_for_next_steps)
        if os.path.exists("temp_downloads") and not os.listdir("temp_downloads"):
            try: os.rmdir("temp_downloads")
            except OSError: pass # Ignore if removal fails (e.g. still in use by another process quickly)
    else:
        print(f"Download failed, cannot proceed with further tool examples for {test_image_url}.") 