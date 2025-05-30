import asyncio
import os
import uuid
import time
# import markdown # Will be replaced by markdown-it-py
from markdown_it import MarkdownIt # For Markdown processing
# from bs4 import BeautifulSoup # For cleaning HTML from Markdown - markdown-it-py gives tokens
import docx # For DOCX processing
from typing import Optional, Any, List, Dict, Union, Tuple # Added Tuple
from pydantic import BaseModel, Field, HttpUrl
import re
from urllib.parse import urlparse
from datetime import datetime # Added datetime
from docx.opc.constants import RELATIONSHIP_TYPE as RT # For image rels
from docx.text.paragraph import Paragraph as DocxParagraph # For type hinting
from docx.document import Document as DocxDocument # For type hinting
from docx.shared import Inches
import io # For image bytes stream
import logging # Added logging

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput # Import new models

# --- Pydantic Models for FileAcquisitionService ---

class FileAcquisitionServiceInput(BaseModel):
    file_path: str = Field(..., description="Path to the file to process.")
    source_content_type: str = Field(..., examples=["docx", "md", "txt"], description="The type of the file.")
    # original_source_identifier_for_gcs_path will be derived from file_path
    # source_type_for_gcs_path will be source_content_type
    # job_id_for_gcs_path will be job_id
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking.")

# Removed ProcessedFileImage and FileAcquisitionServiceOutput models

class FileAcquisitionService(BaseService):
    """
    Asynchronous service to extract text, structure, and images from various file types (DOCX, MD, TXT),
    producing PreliminaryBlock, DocumentMetadata, and RawImageInput objects.
    """

    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        self.settings = settings # Store settings if provided
        self.logger = logging.getLogger(__name__) # Initialize logger
        if self.settings and hasattr(self.settings, 'debug_mode') and self.settings.debug_mode:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO) # Default to INFO

    def _generate_image_id(self, file_type_prefix: str, job_id: str, index: int) -> str: # job_id is now required
        # job_prefix = f"{job_id}_" if job_id else f"{uuid.uuid4().hex[:4]}_" # job_id is now required
        return f"{file_type_prefix}_IMG_{job_id}_{index + 1}"

    async def _process_docx(self, 
                            file_path: str, 
                            job_id: str, 
                            processing_level: str,
                            source_type_for_gcs: str, 
                            base_document_metadata: DocumentMetadata, 
                            preliminary_blocks: List[PreliminaryBlock], 
                            raw_images: List[RawImageInput]
                            ) -> Optional[str]: # Return an error message string if fails, else None
        loop = asyncio.get_event_loop()
        current_block_idx = len(preliminary_blocks)
        img_ref_idx = len(raw_images)
        error_msg: Optional[str] = None

        try:
            document: DocxDocument = await loop.run_in_executor(None, docx.Document, file_path)

            # Extract core properties for DocumentMetadata
            core_props = document.core_properties
            base_document_metadata.author = core_props.author or None
            base_document_metadata.title = core_props.title or base_document_metadata.title # Keep filename if no title prop
            if core_props.created:
                try: base_document_metadata.creation_date = datetime.fromisoformat(str(core_props.created).replace("Z", "+00:00"))
                except: pass # Ignore parsing errors for dates
            if core_props.modified:
                try: base_document_metadata.modification_date = datetime.fromisoformat(str(core_props.modified).replace("Z", "+00:00"))
                except: pass
            base_document_metadata.subject = core_props.subject or None
            base_document_metadata.keywords = core_props.keywords.split(' ') if core_props.keywords else []
            
            # Iterate through paragraphs and inline shapes for images
            # This is a simplified approach. DOCX can have images in headers/footers, tables, etc.
            # which might require deeper inspection of document.xml parts.

            para_idx = 0
            for para in document.paragraphs:
                para_text = para.text.strip()
                para_style_name = para.style.name.lower() if para.style else ""
                block_id_suffix = f"docx_p{para_idx}"
                para_idx += 1

                # Attempt to identify headings (simplistic approach by style name)
                heading_level = 0
                if 'heading 1' in para_style_name: heading_level = 1
                elif 'heading 2' in para_style_name: heading_level = 2
                elif 'heading 3' in para_style_name: heading_level = 3
                elif 'heading 4' in para_style_name: heading_level = 4
                elif 'heading 5' in para_style_name: heading_level = 5
                elif 'heading 6' in para_style_name: heading_level = 6
                
                # Attempt to identify lists (simplistic by style name or numbering)
                is_list_item = False
                is_ordered_list = False
                list_level = 0 # Basic list level, not handling complex nesting well yet
                if 'list paragraph' in para_style_name or 'listbullet' in para_style_name or 'listnumber' in para_style_name:
                    is_list_item = True
                    if para.style.element.xpath('.//w:numPr'): # Check for numbering properties
                        is_ordered_list = True 
                        # Basic level detection based on numId (not robust for complex lists)
                        try: list_level = int(para.style.element.xpath('.//w:numId')[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')) -1
                        except: pass
                        if list_level <0: list_level = 0
                
                if heading_level > 0 and para_text:
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_{block_id_suffix}_h{heading_level}", type="heading",
                        text_content=para_text, heading_level=heading_level,
                        order=-1, page_number=None, bbox=None # DOCX has no simple page/bbox for paragraphs
                    ))
                    current_block_idx +=1
                elif is_list_item and para_text:
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_{block_id_suffix}_li", type="list_item",
                        text_content=para_text, list_item_data=para_text,
                        list_level=list_level, list_ordered=is_ordered_list,
                        order=-1, page_number=None, bbox=None
                    ))
                    current_block_idx += 1
                elif para_text: # Regular text block
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_{block_id_suffix}_t", type="text",
                        text_content=para_text, order=-1, page_number=None, bbox=None
                    ))
                    current_block_idx +=1

            # Extract images if processing_level is full_content
            if processing_level == "full_content":
                for rel_id, rel in document.part.rels.items():
                    if rel.reltype == RT.IMAGE:
                        image_part = rel.target_part
                        image_bytes = image_part.blob
                        original_filename = os.path.basename(image_part.partname)
                        img_ref_idx += 1
                        raw_image_id = self._generate_image_id("DOCX", job_id, img_ref_idx -1)
                        
                        raw_images.append(RawImageInput(
                            image_id=raw_image_id,
                            image_bytes=image_bytes,
                            original_filename=original_filename,
                            mime_type=image_part.content_type, # e.g. 'image/png'
                            source_document_id=job_id,
                            original_source_identifier_for_gcs_path=file_path,
                            source_type_for_gcs_path=source_type_for_gcs,
                            job_id_for_gcs_path=job_id
                        ))
                        preliminary_blocks.append(PreliminaryBlock(
                            block_id=f"{job_id}_docx_img{img_ref_idx-1}", type="image_placeholder",
                            image_id_ref=raw_image_id, order=-1, page_number=None, bbox=None
                        ))
                        current_block_idx +=1
            return None # Success

        except Exception as e:
            error_msg = f"Error processing DOCX file {file_path}: {str(e)}"
            self.logger.error(f"DOCX Processing Error: {error_msg}", exc_info=True)
            return error_msg

    async def _process_markdown(self, 
                                file_path: str, 
                                job_id: str, 
                                processing_level: str,
                                source_type_for_gcs: str, 
                                base_document_metadata: DocumentMetadata, 
                                preliminary_blocks: List[PreliminaryBlock], 
                                raw_images: List[RawImageInput]
                                ) -> Optional[str]: # Return an error message string if fails, else None
        loop = asyncio.get_event_loop()
        md_parser = MarkdownIt("gfm-like") # Using gfm-like for good features like tables, strikethrough etc.
        current_block_idx = len(preliminary_blocks)
        img_ref_idx = len(raw_images)
        error_msg: Optional[str] = None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = await loop.run_in_executor(None, f.read)
            
            tokens = await loop.run_in_executor(None, md_parser.parse, md_content)

            # Variables to handle list levels and types
            current_list_level = 0
            list_type_stack = [] # To track if current list is ordered or unordered

            idx = 0
            while idx < len(tokens):
                token = tokens[idx]
                block_id_suffix = f"md_b{current_block_idx}"

                if token.type == "heading_open":
                    heading_level = int(token.tag[1:])
                    idx += 1 # Move to inline content token
                    content_token = tokens[idx]
                    text_content = content_token.content.strip()
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_{block_id_suffix}_h{heading_level}", type="heading",
                        text_content=text_content, heading_level=heading_level,
                        order=-1, page_number=None, bbox=None
                    ))
                    current_block_idx += 1
                elif token.type == "paragraph_open":
                    idx += 1 # Move to inline content token
                    # Combine content from potentially multiple inline tokens until paragraph_close
                    content = ""
                    image_in_paragraph = False
                    temp_inline_idx = idx
                    while tokens[temp_inline_idx].type != "paragraph_close":
                        if tokens[temp_inline_idx].type == "inline":
                            # Check for images within inline tokens, as they are not separate block tokens for markdown-it-py
                            for child in tokens[temp_inline_idx].children or []:
                                if child.type == "image":
                                    image_in_paragraph = True
                                    img_ref_idx +=1
                                    img_src = child.attrs.get('src', '')
                                    img_alt = child.content
                                    raw_image_id = self._generate_image_id("MD", job_id, img_ref_idx -1)
                                    
                                    image_data_dict = {
                                        "image_id": raw_image_id,
                                        "alt_text": img_alt,
                                        "source_document_id": job_id,
                                        "original_source_identifier_for_gcs_path": file_path,
                                        "source_type_for_gcs_path": source_type_for_gcs,
                                        "job_id_for_gcs_path": job_id
                                    }

                                    if urlparse(img_src).scheme in ['http', 'https']:
                                        image_data_dict["source_url"] = img_src
                                    else:
                                        # Try to resolve local path (relative to MD file or absolute)
                                        resolved_path = img_src
                                        if not os.path.isabs(resolved_path):
                                            resolved_path = os.path.join(os.path.dirname(file_path), img_src)
                                        
                                        if os.path.exists(resolved_path):
                                            try:
                                                with open(resolved_path, 'rb') as img_f:
                                                    image_data_dict["image_bytes"] = await loop.run_in_executor(None, img_f.read)
                                                image_data_dict["original_filename"] = os.path.basename(resolved_path)
                                                image_data_dict["mime_type"] = f"image/{os.path.splitext(resolved_path)[1].lstrip('.').lower() or 'unknown'}"
                                            except Exception as e_img_read:
                                                self.logger.warning(f"MD Service: Could not read image file {resolved_path}: {e_img_read}")
                                                image_data_dict["source_url"] = img_src 
                                        else:
                                            self.logger.warning(f"MD Service: Local image not found {img_src} (resolved: {resolved_path}), storing as source_url.")
                                            image_data_dict["source_url"] = img_src 
                                    
                                    if processing_level == "full_content":
                                        raw_images.append(RawImageInput(**image_data_dict)) # type: ignore
                                    preliminary_blocks.append(PreliminaryBlock(
                                        block_id=f"{job_id}_{block_id_suffix}_img{img_ref_idx-1}", type="image_placeholder",
                                        image_id_ref=raw_image_id, order=-1, page_number=None, bbox=None
                                    ))
                                    current_block_idx +=1 # Each image placeholder is a block
                                else:
                                     content += child.content
                        elif tokens[temp_inline_idx].type == "text": # Sometimes raw text is not in inline
                             content += tokens[temp_inline_idx].content
                        # Skip other child types of inline like softbreak, hardbreak for simple text concatenation
                        temp_inline_idx +=1
                    idx = temp_inline_idx #  Move main idx past this paragraph
                    
                    text_content = content.strip() # Use concatenated content
                    if text_content: # Only add if there is actual text (not just an image)
                        preliminary_blocks.append(PreliminaryBlock(
                            block_id=f"{job_id}_{block_id_suffix}_p", type="text",
                            text_content=text_content, order=-1, page_number=None, bbox=None
                        ))
                        current_block_idx += 1
                elif token.type == "bullet_list_open" or token.type == "ordered_list_open":
                    current_list_level += 1
                    list_type_stack.append(token.type == "ordered_list_open")
                elif token.type == "list_item_open":
                    idx += 1 # Move to inline content for list item (usually inside a paragraph_open)
                    if tokens[idx].type == "paragraph_open": # Standard case
                         idx +=1 # Move to inline inside paragraph
                    
                    # Extract text content of the list item
                    item_content_token = tokens[idx]
                    text_content = item_content_token.content.strip()
                    is_ordered = list_type_stack[-1] if list_type_stack else False

                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_{block_id_suffix}_li", type="list_item",
                        text_content=text_content, list_item_data=text_content,
                        list_level=current_list_level -1, list_ordered=is_ordered,
                        order=-1, page_number=None, bbox=None
                    ))
                    current_block_idx += 1
                elif token.type == "bullet_list_close" or token.type == "ordered_list_close":
                    if current_list_level > 0:
                        current_list_level -= 1
                    if list_type_stack:
                        list_type_stack.pop()
                elif token.type == "fence": # Code block
                    code_content = token.content.strip()
                    lang_info = token.info.strip() if token.info else None
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_{block_id_suffix}_c", type="code_snippet",
                        code_content=code_content, code_language=lang_info,
                        order=-1, page_number=None, bbox=None
                    ))
                    current_block_idx += 1
                # Other token types like table_open/close, tr_open/close, th_open/close, td_open/close 
                # can be added here if table support is desired. For now, they become text via paragraph logic.
                idx += 1
            return None # Success
        except Exception as e:
            error_msg = f"Error processing Markdown file {file_path}: {str(e)}"
            self.logger.error(f"Markdown Processing Error: {error_msg}", exc_info=True)
            return error_msg

    async def _process_txt(self, 
                           file_path: str,
                           job_id: str, 
                           base_document_metadata: DocumentMetadata, 
                           preliminary_blocks: List[PreliminaryBlock] 
                           ) -> Optional[str]: # Return an error message string if fails, else None
        loop = asyncio.get_event_loop()
        encodings_to_try = ['utf-8', 'latin-1', 'windows-1252']
        text_content = None
        error_msg: Optional[str] = None
        current_block_idx = len(preliminary_blocks) # In case other types add blocks before this

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
                return error_msg

            # Split by double newline for paragraphs, then create PreliminaryBlock for each part
            # Filter out empty strings that might result from multiple newlines
            paragraphs = [p.strip() for p in text_content.split('\n\n') if p.strip()]

            for idx, para_text in enumerate(paragraphs):
                block_id = f"{job_id}_txt_b{current_block_idx + idx}"
                preliminary_blocks.append(PreliminaryBlock(
                    block_id=block_id,
                    type="text",
                    text_content=para_text,
                    page_number=None, # No concept of pages in TXT
                    bbox=None, # No bbox
                    order=-1 # Order will be assigned finally in execute
                ))
            # base_document_metadata.title is already set from filename
            # No other specific metadata to extract from TXT typically
            return None # Success

        except Exception as e:
            error_msg = f"Error processing TXT file {file_path}: {str(e)}"
            self.logger.error(f"TXT Processing Error: {error_msg}", exc_info=True)
            return error_msg

    async def execute(self, file_input: FileAcquisitionServiceInput) -> ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]:
        start_time = time.time()
        job_id = file_input.job_id or uuid.uuid4().hex[:8]
        file_path = file_input.file_path
        file_type = file_input.source_content_type.lower()
        # page_title = os.path.basename(file_path) # Will be part of DocumentMetadata

        preliminary_blocks: List[PreliminaryBlock] = []
        raw_images: List[RawImageInput] = []
        
        # Initialize DocumentMetadata
        document_metadata = DocumentMetadata(
            document_id=job_id,
            source_identifier=file_path,
            source_type=file_type,
            title=os.path.basename(file_path), # Default title
            extracted_at=datetime.utcnow()
            # Other fields will be populated by specific processors
        )

        if not os.path.exists(file_path):
            duration = time.time() - start_time
            # Update error reporting to be simpler
            return ServiceResult.failure(
                error_message=f"File not found: {file_path}",
                # No detailed error model needed for simple failures
            )
        
        call_error_message: Optional[str] = None # Error message from _process_... calls

        try:
            if file_type == "docx":
                    call_error_message = await self._process_docx(
                        file_path, job_id, file_input.processing_level, file_type,
                        document_metadata, preliminary_blocks, raw_images
                    )
            elif file_type == "md":
                    call_error_message = await self._process_markdown(
                        file_path, job_id, file_input.processing_level, file_type,
                        document_metadata, preliminary_blocks, raw_images
                    )
            elif file_type == "txt":
                    call_error_message = await self._process_txt(
                        file_path, job_id, document_metadata, preliminary_blocks
                    )
            # Fallback for file_ext_... can be removed if RoutingService handles this better,
            # or adapted if truly needed here. For now, focusing on specified types.
            else:
                    call_error_message = f"Unsupported file type: {file_type}"
            
            if call_error_message: # If any _process method sets an error or unhandled type
                 return ServiceResult.failure(error_message=call_error_message)

            # Assign final order to preliminary_blocks
            # For now, assume blocks are added in order. If complex sorting is needed later (e.g. for DOCX), add here.
            for i, block in enumerate(preliminary_blocks):
                block.order = i
            
            duration = time.time() - start_time # Recalculate duration at the end
            # document_metadata.processing_duration_seconds = duration # Consider adding if useful
            
            return ServiceResult.success(data=(preliminary_blocks, document_metadata, raw_images))

        except Exception as e:
            # General exception handler
            duration = time.time() - start_time
            # Log the exception e for debugging
            self.logger.error(f"FileAcquisitionService: Unhandled error processing {file_path}: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                error_message=f"Error processing file {os.path.basename(file_path)}: {str(e)}",
            ) 