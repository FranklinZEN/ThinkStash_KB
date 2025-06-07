#!/usr/bin/env python
# coding: utf-8
"""Defines tools for content processing within CrewAI agents."""

import requests
from PIL import Image
from google.cloud import storage
from crewai.tools import BaseTool
import os
import uuid
import io
from aiservice.app.config.settings import settings
from aiservice.app.models.orchestration_models import ContentBlock
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from markdownify import markdownify as md

# Note: The 'tool' decorator from langchain_core.tools is not used here,
# as these are standard BaseTool classes for CrewAI.

class ImageDownloaderTool(BaseTool):
    name: str = "Image Downloader from URL"
    description: str = (
        "Downloads an image from a given URL and saves it to a specified temporary local folder. "
        "Input: 'image_url' (string: the URL of the image to download), "
        "'output_folder' (string: local folder to save the downloaded image, defaults to 'temp_downloaded_images')."
        "Returns a dictionary with 'local_path' on success or 'error'."
    )
    # This tool does not require an LLM, so args_schema can be None or defined with Pydantic.

    def _run(self, image_url: str, output_folder: str = "temp_downloaded_images") -> dict:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        try:
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            file_extension = os.path.splitext(image_url.split('?')[0])[-1] or '.jpg'
            local_filename = f"{uuid.uuid4()}{file_extension}"
            local_path = os.path.join(output_folder, local_filename)

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return {"local_path": local_path}
        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to download image: {e}"}


class FullTextContentExtractorTool(BaseTool):
    name: str = "Full Text Content Extractor Tool"
    description: str = (
        "Extracts and concatenates all textual content from a list of content block dictionaries. "
        "Input must be a list of dictionaries, where each dictionary represents a content block. "
        "The key in the kickoff inputs should be 'content_block_dicts'."
    )

    def _parse_input_dicts(self, content_block_dicts: List[Dict[str, Any]]) -> List[ContentBlock]:
        """Safely parse a list of dictionaries into ContentBlock models."""
        parsed_blocks = []
        for i, block_dict in enumerate(content_block_dicts):
            try:
                # Add dummy values for required fields if they are missing, to allow parsing
                block_dict.setdefault('block_id', f'temp_id_{i}')
                block_dict.setdefault('user_id', 'temp_user')
                block_dict.setdefault('document_id', 'temp_doc')
                block_dict.setdefault('order_index', i)
                parsed_blocks.append(ContentBlock.model_validate(block_dict))
            except ValidationError as e:
                # Skip blocks that fail validation
                print(f"Skipping a block due to validation error: {e}")
                continue
        return parsed_blocks

    def _extract_text_from_list(self, items: List[Any]) -> str:
        """Helper to extract text from a list block's 'items'."""
        item_texts = []
        if not items:
            return ""
        for item in items:
            content = ""
            if isinstance(item, str):
                content = item
            elif isinstance(item, dict) and 'content' in item and isinstance(item['content'], str):
                content = item['content']
            
            if content.strip(): # Only append non-empty strings
                item_texts.append(content)
        
        # FIX: Join list items with a double newline for clear separation.
        return "\n\n".join(item_texts)

    def _extract_text_from_block(self, block: ContentBlock) -> Optional[str]:
        """Helper to extract text from a single ContentBlock based on its type."""
        block_type = block.type
        if block_type in ["text", "heading", "math_text", "code_snippet"]:
            return block.content
        if block_type == "list":
            return self._extract_text_from_list(block.items)
        if block_type == "table":
            # FIX: Do not convert to markdown. Just return the raw HTML table content.
            # The LLM is capable of understanding HTML.
            return block.content
        return None # Return None for non-textual block types like 'image'

    def _run(self, content_block_dicts: List[Dict[str, Any]]) -> str:
        """Processes a list of content block dictionaries to extract all text."""
        if not isinstance(content_block_dicts, list):
            return "Error: Input is not a list of content blocks."

        parsed_blocks = self._parse_input_dicts(content_block_dicts)
        
        text_parts = []
        for block in parsed_blocks:
            block_text = self._extract_text_from_block(block)
            if block_text and block_text.strip():
                text_parts.append(block_text.strip())
        
        # FIX: Join different blocks with a double newline. Return empty string if no text.
        return "\n\n".join(text_parts)