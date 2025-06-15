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
from aiservice.app.config.settings import settings
from aiservice.app.models.orchestration_models import ContentBlock
from typing import List, Dict, Any
from langchain_core.tools import tool
from pydantic import BaseModel, Field, ValidationError
from markdownify import markdownify as md
import logging
import json # Import the json library

logger = logging.getLogger(__name__)

# --- Pydantic model for the tool's arguments ---
class FullTextContentExtractorToolInput(BaseModel):
    """Input model for the FullTextContentExtractorTool."""
    content_block_dicts: List[Dict[str, Any]] = Field(description="The list of content block dictionaries to process.")

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
        if isinstance(image_url, str) and os.path.exists(image_url):
            filename = os.path.basename(image_url)
            ext = os.path.splitext(filename)[1].lower()
            content_type_map = {
                '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp',
                '.tiff': 'image/tiff'
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')
            return {
                "local_path": image_url, "original_url": image_url,
                "filename": filename, "content_type": content_type, "error": None
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
            if not content_type.lower().startswith('image/'):
                return {"error": f"URL does not point to a recognized image type. Content-Type: {content_type}", "local_path": None, "original_url": image_url}

            file_extension = '.' + content_type.split('/')[-1].split(';')[0]
            if len(file_extension) > 5 or file_extension == '.None':
                if image_url.lower().endswith('.png'): file_extension = '.png'
                elif image_url.lower().endswith(('.jpg', '.jpeg')): file_extension = '.jpeg'
                else: file_extension = '.img'
            
            filename = str(uuid.uuid4()) + file_extension
            local_file_path = os.path.join(output_folder, filename)

            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return {
                "local_path": local_file_path, "original_url": image_url,
                "filename": filename, "content_type": content_type, "error": None
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Error downloading image {image_url}: {e}", "local_path": None, "original_url": image_url}
        except Exception as e_save:
            return {"error": f"Error saving image {image_url}: {e_save}", "local_path": None, "original_url": image_url}

class GCSUploadTool(BaseTool):
    name: str = "Google Cloud Storage (GCS) Image Uploader"
    description: str = (
        "Uploads a local image file to a specified Google Cloud Storage bucket."
    )
    storage_client: Any = None
    default_gcs_bucket_name: str | None = None

    def __init__(self, gcs_bucket_name_override: str = None, **kwargs):
        super().__init__(**kwargs)
        self.default_gcs_bucket_name = gcs_bucket_name_override or settings.gcs_bucket_name
        try:
            self.storage_client = storage.Client()
        except Exception as e:
            logger.critical(f"Failed to initialize Google Cloud Storage client: {e}. GCSUploadTool will not work.")
            self.storage_client = None

    def _run(self, local_file_path: str, gcs_blob_name: str, gcs_bucket_name: str = None) -> dict:
        bucket_name_to_use = gcs_bucket_name or self.default_gcs_bucket_name
        if not self.storage_client:
            return {"error": "GCS client not initialized.", "gcs_url": None}
        if not bucket_name_to_use:
            return {"error": "GCS bucket name not provided.", "gcs_url": None}
        if not isinstance(local_file_path, str) or not os.path.exists(local_file_path):
            return {"error": f"Local file not found: {local_file_path}", "gcs_url": None}
        
        try:
            bucket = self.storage_client.bucket(bucket_name_to_use)
            blob = bucket.blob(gcs_blob_name)
            ext = os.path.splitext(local_file_path)[1].lower()
            content_type_map = {
                '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.gif': 'image/gif', '.webp': 'image/webp'
            }
            gcs_content_type = content_type_map.get(ext, 'application/octet-stream')
            blob.upload_from_filename(local_file_path, content_type=gcs_content_type)
            gs_uri = f"gs://{bucket_name_to_use}/{gcs_blob_name}"
            return {"gcs_url": gs_uri, "error": None}
        except Exception as e:
            return {"error": f"Error uploading {local_file_path} to GCS: {e}", "gcs_url": None}

class ImageMetadataTool(BaseTool):
    name: str = "Image File Metadata Extractor"
    description: str = "Extracts metadata from a local image file."

    def _run(self, image_file_path: str) -> dict:
        if not isinstance(image_file_path, str) or not os.path.exists(image_file_path):
            return {"error": f"Image file not found: {image_file_path}"}
        try:
            with Image.open(image_file_path) as img:
                width, height = img.size
                img_format = img.format
                mime_type = Image.MIME.get(img_format.upper())
            return {
                "width": width, "height": height, "format": img_format,
                "mime_type": mime_type, "error": None
            }
        except Exception as e:
            return {"error": f"Error extracting metadata from {image_file_path}: {e}"}

class FullTextContentExtractorTool(BaseTool):
    name: str = "Full Text Content Extractor Tool"
    description: str = (
        "Extracts and concatenates all textual content from a list of content block dictionaries."
    )
    args_schema: type[BaseModel] = FullTextContentExtractorToolInput

    def _run(self, **kwargs) -> str:
        """
        Processes a list of content block dictionaries to extract all text,
        handling both modern BlockNote-style and legacy data formats.
        """
        content_block_dicts = kwargs.get('content_block_dicts')

        if not content_block_dicts:
            logger.error("Tool was called without 'content_block_dicts' in its arguments.")
            return "Error: The required 'content_block_dicts' argument was not provided."

        # Handle case where input is a JSON string
        if isinstance(content_block_dicts, str):
            try:
                data = json.loads(content_block_dicts)
                content_block_dicts = data.get('content_block_dicts', data)
            except json.JSONDecodeError:
                return "Error: Input was a string but could not be parsed as JSON."
        
        if not isinstance(content_block_dicts, list):
            logger.error(f"Tool input was not a list, but type {type(content_block_dicts)}.")
            return "Error: Input is not a list."

        full_text: List[str] = []
        
        for i, block in enumerate(content_block_dicts):
            if not isinstance(block, dict):
                logger.warning(f"Skipping non-dict item #{i} in input list: {block}")
                continue

            text_part = ""
            block_type = block.get("type")
            content = block.get("content")

            # Modern BlockNote.js format & Simple legacy formats
            if block_type in ["text", "heading", "list_item", "code_snippet"] and isinstance(content, str):
                text_part = content
            # BlockNote-style "paragraph" with nested inline content
            elif block_type == "paragraph" and isinstance(content, list):
                text_part = "".join(
                    item.get('text', '') 
                    for item in content 
                    if isinstance(item, dict) and item.get('type') == 'text'
                )
            # BlockNote-style "list" with nested "listItem"s
            elif block_type == "list" and isinstance(content, list):
                item_texts = []
                for item_dict in content:
                    if isinstance(item_dict, dict) and item_dict.get('type') == 'listItem':
                        item_texts.append("".join(
                            inline.get('text', '')
                            for inline in item_dict.get('content', [])
                            if isinstance(inline, dict) and inline.get('type') == 'text'
                        ))
                text_part = "\\n".join(filter(None, item_texts))
            # Legacy simple list of strings
            elif block_type == "list" and "items" in block and isinstance(block["items"], list):
                 item_texts = [str(item) for item in block["items"] if isinstance(item, str)]
                 text_part = "\\n".join(item_texts)
            # Image captions and alt text
            elif block_type == "image":
                img_texts = []
                # Modern props structure
                props = block.get("props", {})
                if isinstance(props, dict):
                    if props.get("alt"): img_texts.append(f"Image Alt Text: {props.get('alt')}")
                    if props.get("caption"): img_texts.append(f"Image Caption: {props.get('caption')}")
                # Legacy content structure
                elif isinstance(content, dict):
                     if content.get("alt_text"): img_texts.append(f"Image Alt Text: {content.get('alt_text')}")
                     if content.get("caption"): img_texts.append(f"Image Caption: {content.get('caption')}")
                text_part = "; ".join(img_texts)

            if text_part.strip():
                full_text.append(text_part.strip())

        if not full_text:
            logger.warning("No textual content was extracted from the provided blocks.")
            return "Error: No content available for title generation."

        return "\\n\\n".join(full_text)

class HTMLToMarkdownTool(BaseTool):
    name: str = "HTML to Markdown Converter"
    description: str = "Converts a string of HTML content into Markdown."

    def _run(self, html_content: str) -> str:
        if not isinstance(html_content, str):
            return "Error: Input must be a string of HTML content."
        try:
            return md(html_content, heading_style="ATX")
        except Exception as e:
            return f"Error during HTML to Markdown conversion: {e}"