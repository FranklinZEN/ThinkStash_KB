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
import tempfile # Added for temporary file handling for GCS downloads
from google.cloud import storage # Added for GCS interaction

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput # Import new models

# --- Pydantic Models for FileAcquisitionService ---

class FileAcquisitionServiceInput(BaseModel):
    file_path: str = Field(..., description="Path to the file (local or gs://) to process.")
    source_content_type: str = Field(..., examples=["docx", "md", "txt", "gcs_docx", "gcs_md", "gcs_txt", "gcs_file_ext_..."], description="The type/extension of the file, prefixed with 'gcs_' if applicable.")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking.")
    user_id: Optional[str] = None # Added user_id

# Removed ProcessedFileImage and FileAcquisitionServiceOutput models

class FileAcquisitionService(BaseService):
    """
    Asynchronous service to extract text, structure, and images from various file types (DOCX, MD, TXT),
    producing PreliminaryBlock, DocumentMetadata, and RawImageInput objects.
    Can handle local file paths or gs:// GCS paths.
    """

    GCS_PREFIX = "gs://"

    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        self.settings = settings # Store settings if provided
        self.logger = logging.getLogger(__name__) # Initialize logger
        if self.settings and hasattr(self.settings, 'debug_mode') and self.settings.debug_mode:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO) # Default to INFO

        try:
            self.gcs_storage_client = storage.Client()
            self.logger.info("GCS Storage client initialized successfully for FileAcquisitionService.")
        except Exception as e_gcs_init:
            self.gcs_storage_client = None
            self.logger.error(f"FileAcquisitionService: Failed to initialize GCS Storage client: {e_gcs_init}. GCS downloads will fail.")

    def _generate_image_id(self, file_type_prefix: str, job_id: str, index: int) -> str: # job_id is now required
        # job_prefix = f"{job_id}_" if job_id else f"{uuid.uuid4().hex[:4]}_" # job_id is now required
        return f"{file_type_prefix}_IMG_{job_id}_{index + 1}"

    async def _download_gcs_file(self, gcs_path: str, original_filename_for_suffix: str) -> Tuple[Optional[str], Optional[str]]:
        """Downloads a file from GCS to a temporary local path. Returns (temp_file_path, error_message)."""
        if not self.gcs_storage_client:
            return None, "GCS client not initialized."
        try:
            parsed_url = urlparse(gcs_path)
            bucket_name = parsed_url.netloc
            blob_name = parsed_url.path.lstrip('/')

            if not bucket_name or not blob_name:
                return None, f"Invalid GCS path: {gcs_path}. Could not parse bucket/blob name."

            bucket = self.gcs_storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            _, file_extension = os.path.splitext(original_filename_for_suffix)
            if not file_extension and blob_name: # Fallback if original_filename_for_suffix had no extension
                 _, file_extension = os.path.splitext(blob_name)

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension or ".tmp")
            temp_file_path = temp_file.name
            temp_file.close()

            await asyncio.get_event_loop().run_in_executor(None, blob.download_to_filename, temp_file_path)
            self.logger.info(f"FileAcquisitionService: Successfully downloaded {gcs_path} to {temp_file_path}")
            return temp_file_path, None
        except Exception as e:
            self.logger.error(f"FileAcquisitionService: Error downloading {gcs_path} from GCS: {e}")
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e_unlink:
                    self.logger.error(f"FileAcquisitionService: Failed to cleanup temp file {temp_file_path} after GCS download error: {e_unlink}")
            return None, str(e)

    async def _process_docx(self, 
                            file_path: str, 
                            job_id: str, 
                            processing_level: str,
                            source_identifier_for_gcs_imgs: str, # Original GCS path or local file path for image metadata
                            base_document_metadata: DocumentMetadata, 
                            preliminary_blocks: List[PreliminaryBlock], 
                            raw_images: List[RawImageInput]
                            ) -> Optional[str]: # Return an error message string if fails, else None
        loop = asyncio.get_event_loop()
        error_msg: Optional[str] = None

        try:
            document: DocxDocument = await loop.run_in_executor(None, docx.Document, file_path)

            # Extract core properties for DocumentMetadata
            core_props = document.core_properties
            base_document_metadata.author = core_props.author or None
            # Keep filename from base_document_metadata if no title prop, or use core_props.title
            base_document_metadata.title = core_props.title or base_document_metadata.title 
            if core_props.created:
                try: base_document_metadata.creation_date = datetime.fromisoformat(str(core_props.created).replace("Z", "+00:00"))
                except ValueError: self.logger.warning(f"DOCX: Could not parse core_props.created: {core_props.created}")
                except Exception as e_date: self.logger.warning(f"DOCX: Error parsing core_props.created: {e_date}")

            if core_props.modified:
                try: base_document_metadata.modification_date = datetime.fromisoformat(str(core_props.modified).replace("Z", "+00:00"))
                except ValueError: self.logger.warning(f"DOCX: Could not parse core_props.modified: {core_props.modified}")
                except Exception as e_date: self.logger.warning(f"DOCX: Error parsing core_props.modified: {e_date}")
            base_document_metadata.subject = core_props.subject or None
            base_document_metadata.keywords = core_props.keywords.split(' ') if core_props.keywords else []
            
            # Iterate through paragraphs to extract text and inline images in order
            for para_g_idx, para_object in enumerate(document.paragraphs):
                # --- 1. Process Text-like content from the paragraph ---
                para_text = para_object.text.strip()
                para_style_name = para_object.style.name.lower() if para_object.style and para_object.style.name else ""
                
                heading_level = 0
                if 'heading 1' in para_style_name: heading_level = 1
                elif 'heading 2' in para_style_name: heading_level = 2
                elif 'heading 3' in para_style_name: heading_level = 3
                elif 'heading 4' in para_style_name: heading_level = 4
                elif 'heading 5' in para_style_name: heading_level = 5
                elif 'heading 6' in para_style_name: heading_level = 6
                
                is_list_item = False
                is_ordered_list = False
                list_level = 0 
                if 'list paragraph' in para_style_name or 'listbullet' in para_style_name or 'listnumber' in para_style_name:
                    is_list_item = True
                    # Check for numbering properties to determine if ordered
                    # Accessing para_object.style.element.xpath requires style to be defined.
                    if para_object.style and para_object.style.element and para_object.style.element.xpath('.//w:numPr'): 
                        is_ordered_list = True 
                        try: 
                            num_id_val = para_object.style.element.xpath('.//w:numId')[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                            if num_id_val is not None:
                                list_level = int(num_id_val) -1
                        except (IndexError, ValueError, TypeError): 
                            self.logger.debug(f"DOCX: Could not determine list_level for para {para_g_idx}")
                        if list_level < 0: list_level = 0
                
                if heading_level > 0 and para_text:
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_docx_p{para_g_idx}_h{heading_level}", type="heading",
                        text_content=para_text, heading_level=heading_level,
                        order=-1, page_number=None, bbox=None
                    ))
                elif is_list_item and para_text:
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_docx_p{para_g_idx}_li", type="list_item",
                        text_content=para_text, list_item_data=para_text,
                        list_level=list_level, list_ordered=is_ordered_list,
                        order=-1, page_number=None, bbox=None
                    ))
                elif para_text: 
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_docx_p{para_g_idx}_t", type="text",
                        text_content=para_text, order=-1, page_number=None, bbox=None
                    ))

                # --- 2. Process Inline Images within the paragraph's runs ---
                if processing_level == "full_content":
                    for run in para_object.runs:
                        # nsmap = run.element.nsmap # Namespace map from the run element - not directly used in xpath() a la lxml
                        
                        # Handle <w:drawing> elements
                        # Corrected XPath queries without the namespaces argument
                        for drawing_element in run.element.xpath('.//w:drawing'):
                            blip_elements = drawing_element.xpath('.//a:graphic/a:graphicData/pic:pic/pic:blipFill/a:blip/@r:embed')
                            if not blip_elements: # Fallback for simpler structures if the above is too specific
                                blip_elements = drawing_element.xpath('.//a:blip/@r:embed') # Get the embed attribute directly

                            for r_embed_id in blip_elements: # blip_elements now contains attribute values if found
                                # r_embed_id is already the string value of the r:embed attribute
                                if r_embed_id:
                                    try:
                                        if r_embed_id not in document.part.rels:
                                            self.logger.warning(f"DOCX: rId {r_embed_id} from drawing not in document.part.rels (para {para_g_idx}). Skipping.")
                                            continue

                                        image_part = document.part.rels[r_embed_id].target_part
                                        image_bytes = image_part.blob
                                        original_filename = os.path.basename(image_part.partname)
                                        
                                        current_img_idx = len(raw_images)
                                        raw_image_id = self._generate_image_id("DOCX", job_id, current_img_idx)
                                        
                                        raw_images.append(RawImageInput(
                                            image_id=raw_image_id, image_bytes=image_bytes,
                                            original_filename=original_filename, mime_type=image_part.content_type,
                                            source_document_id=job_id,
                                            user_id=base_document_metadata.user_id, # Pass user_id
                                            job_id=job_id, # Pass job_id
                                            document_id=base_document_metadata.document_id, # Pass document_id from metadata
                                            source_identifier_of_document=source_identifier_for_gcs_imgs # Original GCS or local path
                                        ))
                                        preliminary_blocks.append(PreliminaryBlock(
                                            block_id=f"{job_id}_docx_p{para_g_idx}_draw_img{current_img_idx}", type="image_placeholder",
                                            image_id_ref=raw_image_id, order=-1, 
                                            page_number=None, bbox=None 
                                        ))
                                    except KeyError:
                                        self.logger.warning(f"DOCX: KeyError for rId {r_embed_id} (drawing, para {para_g_idx}). Skipping.")
                                    except Exception as e_img_inline:
                                        self.logger.error(f"DOCX: Error processing drawing image (rId {r_embed_id}, para {para_g_idx}): {e_img_inline}", exc_info=True)
                        
                        # Handle <w:pict> elements (VML images)
                        # Corrected XPath queries without the namespaces argument
                        for pict_element in run.element.xpath('.//w:pict'):
                            imagedata_elements = pict_element.xpath('.//v:imagedata/@r:embed') # Get the embed attribute directly
                            for r_embed_id in imagedata_elements: # imagedata_elements now contains attribute values
                                # r_embed_id is already the string value of the r:embed attribute
                                if r_embed_id:
                                    try:
                                        if r_embed_id not in document.part.rels:
                                            self.logger.warning(f"DOCX: rId {r_embed_id} from VML pict not in document.part.rels (para {para_g_idx}). Skipping.")
                                            continue
                                        
                                        image_part = document.part.rels[r_embed_id].target_part
                                        image_bytes = image_part.blob
                                        original_filename = os.path.basename(image_part.partname)
                                        current_img_idx = len(raw_images)
                                        raw_image_id = self._generate_image_id("DOCX", job_id, current_img_idx)
                                        
                                        raw_images.append(RawImageInput(
                                            image_id=raw_image_id, image_bytes=image_bytes,
                                            original_filename=original_filename, mime_type=image_part.content_type,
                                            source_document_id=job_id,
                                            original_source_identifier_for_gcs_path=file_path,
                                            source_type_for_gcs_path=source_type_for_gcs,
                                            job_id_for_gcs_path=job_id
                                        ))
                                        preliminary_blocks.append(PreliminaryBlock(
                                            block_id=f"{job_id}_docx_p{para_g_idx}_vml_img{current_img_idx}", type="image_placeholder",
                                            image_id_ref=raw_image_id, order=-1,
                                            page_number=None, bbox=None
                                        ))
                                    except KeyError:
                                        self.logger.warning(f"DOCX: KeyError for rId {r_embed_id} (VML, para {para_g_idx}). Skipping.")
                                    except Exception as e_img_vml:
                                        self.logger.error(f"DOCX: Error processing VML image (rId {r_embed_id}, para {para_g_idx}): {e_img_vml}", exc_info=True)
            return None # Success

        except Exception as e:
            error_msg = f"Error processing DOCX file {file_path}: {str(e)}"
            self.logger.error(f"DOCX Processing Error: {error_msg}", exc_info=True)
            return error_msg

    async def _process_markdown(self, 
                                file_path: str, 
                                job_id: str, 
                                processing_level: str,
                                source_identifier_for_gcs_imgs: str, 
                                base_document_metadata: DocumentMetadata, 
                                preliminary_blocks: List[PreliminaryBlock], 
                                raw_images: List[RawImageInput]
                                ) -> Optional[str]:
        loop = asyncio.get_event_loop()
        # Ensure linkify-it-py is installed if linkify is True, or set linkify to False
        # For now, assuming linkify-it-py is installed or will be.
        md_parser = MarkdownIt("gfm-like", {"html": False, "linkify": True})
        
        current_block_idx = len(preliminary_blocks) # Start after any existing blocks
        img_ref_idx = len(raw_images)
        error_msg: Optional[str] = None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = await loop.run_in_executor(None, f.read)
            
            tokens = await loop.run_in_executor(None, md_parser.parse, md_content)

            active_block_content: str = ""
            active_block_type: Optional[str] = None
            # Specific attributes for different block types
            active_heading_level: int = 0
            list_level_stack: List[int] = [] 
            list_ordered_stack: List[bool] = []
            current_code_language: Optional[str] = None

            # Helper function to finalize the current active block
            def finalize_active_block():
                nonlocal current_block_idx, active_block_type, active_block_content
                nonlocal active_heading_level, list_level_stack, list_ordered_stack
                
                if not active_block_type or not active_block_content.strip():
                    active_block_content = "" # Clear buffer if only whitespace
                    return

                block_to_add = None
                if active_block_type == "heading":
                    block_to_add = PreliminaryBlock(
                        block_id=f"{job_id}_md_b{current_block_idx}_h{active_heading_level}", type="heading",
                        text_content=active_block_content.strip(), heading_level=active_heading_level,
                        order=-1)
                elif active_block_type == "text":
                    block_to_add = PreliminaryBlock(
                        block_id=f"{job_id}_md_b{current_block_idx}_p", type="text",
                        text_content=active_block_content.strip(), order=-1)
                elif active_block_type == "list_item":
                    current_list_level = max(0, len(list_level_stack) - 1)
                    current_list_ordered = list_ordered_stack[-1] if list_ordered_stack else False
                    self.logger.debug(f"Finalizing list_item: Content='{active_block_content.strip()[:50]}', Level={current_list_level}, Ordered={current_list_ordered}")
                    block_to_add = PreliminaryBlock(
                        block_id=f"{job_id}_md_b{current_block_idx}_li", type="list_item",
                        text_content=active_block_content.strip(), 
                        list_item_data=active_block_content.strip(), 
                        list_level=current_list_level, 
                        list_ordered=current_list_ordered,
                        order=-1)
                
                if block_to_add:
                    self.logger.debug(f"Adding block: {block_to_add.type}, ID: {block_to_add.block_id}, Content Preview: '{getattr(block_to_add, 'text_content', '')[:30]}'")
                    preliminary_blocks.append(block_to_add)
                    current_block_idx += 1
                
                active_block_content = "" 


            for i, token in enumerate(tokens):
                # Log entry for each token
                self.logger.debug(f"Token[{i}]: Type='{token.type}', Tag='{token.tag}', Nesting={token.nesting}, Level={token.level}, ActiveType='{active_block_type}', Buffer='{active_block_content[:30]}'")

                if token.type == 'heading_open':
                    finalize_active_block() 
                    active_block_type = "heading"
                    active_heading_level = int(token.tag[1:])
                    active_block_content = "" # Start fresh for heading
                elif token.type == 'heading_close':
                    # Content for heading is in active_block_content from inline tokens
                    finalize_active_block() 
                    active_block_type = None 
                
                elif token.type == 'paragraph_open':
                    if active_block_type == "list_item":
                        # This paragraph is inside a list item.
                        # Add a newline if there's already content from a previous paragraph in this list item.
                        if active_block_content.strip():
                            active_block_content += "\\n\\n" # Simulating a paragraph break within the list item
                    else:
                        # This paragraph starts a new text block (not inside a list item)
                        finalize_active_block()
                        active_block_type = "text"
                        active_block_content = "" # Start fresh for new text block
                elif token.type == 'paragraph_close':
                    if active_block_type == "text":
                        # This closes a standard text block, finalize it.
                        finalize_active_block()
                        active_block_type = None
                    # If active_block_type is "list_item", we do NOT finalize here.
                    # The list item content (which may span multiple paragraphs)
                    # will be finalized when 'list_item_close' is encountered.
                
                elif token.type == 'bullet_list_open':
                    finalize_active_block() 
                    list_level_stack.append(token.level)
                    list_ordered_stack.append(False)
                    active_block_type = None 
                elif token.type == 'ordered_list_open':
                    finalize_active_block()
                    list_level_stack.append(token.level)
                    list_ordered_stack.append(True)
                    active_block_type = None

                elif token.type == 'list_item_open':
                    # Finalize any block that was active before this list item started.
                    # Example: text paragraph followed by a list.
                    if active_block_type != "list_item": # Should not happen if lists are structured correctly
                        finalize_active_block()
                    active_block_type = "list_item"
                    active_block_content = "" # Reset for this new list item's content
                elif token.type == 'list_item_close':
                    # This is the point to finalize all accumulated content for the current list item.
                    if active_block_type == "list_item":
                        finalize_active_block()
                    active_block_type = None # Ready for next item or list_close

                elif token.type == 'bullet_list_close' or token.type == 'ordered_list_close':
                    # Finalize any pending list item that might not have been closed explicitly by list_item_close
                    # (though markdown-it usually provides list_item_close for each item).
                    if active_block_type == "list_item":
                         finalize_active_block() # Should ideally be empty if list_item_close handled it.

                    if list_level_stack: list_level_stack.pop()
                    if list_ordered_stack: list_ordered_stack.pop()
                    active_block_type = None 

                elif token.type == 'fence' or token.type == 'code_block':
                    finalize_active_block() 
                    active_block_type = None 
                    
                    code_content = token.content
                    current_code_language = token.info.strip() if token.info else None
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_md_b{current_block_idx}_code", type="code_snippet",
                        code_content=code_content, code_language=current_code_language,
                        order=-1))
                    current_block_idx += 1

                elif token.type == 'hr':
                    finalize_active_block() 
                    active_block_type = None 
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_md_b{current_block_idx}_hr", type="horizontal_rule", order=-1))
                    current_block_idx += 1

                elif token.type == 'inline':
                    if token.children:
                        for child_idx, child in enumerate(token.children):
                            if child.type == 'text':
                                active_block_content += child.content
                            elif child.type == 'softbreak':
                                active_block_content += '\\n'
                            elif child.type == 'hardbreak':
                                active_block_content += '\\n'
                            elif child.type == 'image' and processing_level == "full_content":
                                finalize_active_block() 
                                active_block_type = None 

                                img_src = child.attrs.get('src', '')
                                alt_text = child.content or None 
                                title_attr = child.attrs.get('title', None)

                                if img_src:
                                    raw_image_id = self._generate_image_id("MD", job_id, img_ref_idx)
                                    
                                    image_input_data = {
                                        "image_id": raw_image_id,
                                        "source_url": img_src if urlparse(img_src).scheme in ['http', 'https'] else None,
                                        "alt_text": alt_text,
                                        "original_filename": None, 
                                        "mime_type": None, 
                                        "image_bytes": None,
                                        "source_document_id": base_document_metadata.document_id,
                                        "page_number": None, 
                                        "bbox": None, 
                                        "original_source_identifier_for_gcs_path": source_identifier_for_gcs_imgs,
                                        "source_type_for_gcs_path": base_document_metadata.source_type,
                                        "job_id_for_gcs_path": job_id,
                                        "user_id": base_document_metadata.user_id, # from base_document_metadata
                                        "document_id": base_document_metadata.document_id # ensure document_id is passed, also from base
                                    }
                                    if not image_input_data["source_url"] and not img_src.startswith('data:'):
                                        resolved_path = img_src
                                        if not os.path.isabs(resolved_path):
                                            base_dir = os.path.dirname(file_path) if os.path.isfile(file_path) else os.getcwd()
                                            resolved_path = os.path.join(base_dir, img_src)
                                        
                                        if os.path.exists(resolved_path):
                                            try:
                                                with open(resolved_path, 'rb') as img_f:
                                                    image_input_data["image_bytes"] = img_f.read()
                                                image_input_data["original_filename"] = os.path.basename(resolved_path)
                                                img_ext = os.path.splitext(resolved_path)[1].lstrip('.').lower()
                                                if img_ext in ['jpg', 'jpeg']: image_input_data["mime_type"] = "image/jpeg"
                                                elif img_ext == 'png': image_input_data["mime_type"] = "image/png"
                                                elif img_ext == 'gif': image_input_data["mime_type"] = "image/gif"
                                                elif img_ext == 'webp': image_input_data["mime_type"] = "image/webp"
                                                else: image_input_data["mime_type"] = "image/unknown"
                                            except Exception as e_img_read:
                                                self.logger.warning(f"MD Service: Could not read image file {resolved_path}: {e_img_read}")
                                                image_input_data["source_url"] = img_src 
                                        else:
                                            self.logger.warning(f"MD Service: Local image ref not found '{img_src}' (resolved: '{resolved_path}'). Storing as source_url if possible.")
                                            image_input_data["source_url"] = img_src 
                                    
                                    raw_images.append(RawImageInput(**image_input_data))
                                    preliminary_blocks.append(PreliminaryBlock(
                                        block_id=f"{job_id}_md_b{current_block_idx}_img{img_ref_idx}", type="image_placeholder",
                                        image_id_ref=raw_image_id, 
                                        custom_attributes={"alt_text": alt_text, "title_attr": title_attr, "original_src": img_src},
                                        order=-1))
                                    current_block_idx += 1
                                    img_ref_idx += 1
                            elif child.content: 
                                active_block_content += child.content
                    elif token.content: 
                        active_block_content += token.content
                
                elif token.content and active_block_type : 
                    active_block_content += token.content

            finalize_active_block() 

            return None 
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
        
        original_file_path = file_input.file_path
        processing_file_path = original_file_path # Will be updated if GCS
        is_gcs_source = original_file_path.startswith(self.GCS_PREFIX)
        temp_gcs_file_path: Optional[str] = None
        loop = asyncio.get_event_loop()

        effective_content_type = file_input.source_content_type
        if effective_content_type.startswith("gcs_file_ext_"):
            # e.g., gcs_file_ext_banana -> banana
            effective_content_type = effective_content_type[len("gcs_file_ext_"):]
        elif effective_content_type.startswith("gcs_"):
            # e.g., gcs_docx -> docx
            effective_content_type = effective_content_type[len("gcs_"):]
        # Now effective_content_type is the actual file type like 'docx', 'md', 'txt', or 'banana'

        preliminary_blocks: List[PreliminaryBlock] = []
        raw_images: List[RawImageInput] = []
        file_basename = os.path.basename(original_file_path)

        document_metadata = DocumentMetadata(
            document_id=job_id,
            user_id=file_input.user_id or f"unknown_user_file_service_{job_id}",
            source_identifier=original_file_path, # Use original path for identification
            source_type=effective_content_type, 
            title=file_basename, # Default title, can be overridden by specific processors
            extracted_at=datetime.utcnow()
            # Other fields like author, creation_date will be populated by specific processors
        )
        
        error_message: Optional[str] = None

        try:
            if is_gcs_source:
                if not self.gcs_storage_client:
                    self.logger.error("FileAcquisitionService: GCS client not initialized. Cannot process GCS path.")
                    return ServiceResult.failure(error_message="GCS client not initialized for FileAcquisitionService.")
                
                self.logger.info(f"FileAcquisitionService: Processing GCS file: {original_file_path} with type {file_input.source_content_type}")
                temp_gcs_file_path, download_error = await self._download_gcs_file(original_file_path, file_basename)
                if download_error or not temp_gcs_file_path:
                    self.logger.error(f"FileAcquisitionService: Failed to download GCS file {original_file_path}: {download_error}")
                    return ServiceResult.failure(error_message=f"Failed to download GCS file {original_file_path}: {download_error}")
                processing_file_path = temp_gcs_file_path
            
            # Critical: Check existence of the file path that will be processed
            if not os.path.exists(processing_file_path):
                self.logger.error(f"FileAcquisitionService: File not found at processing path: {processing_file_path} (original: {original_file_path})")
                return ServiceResult.failure(error_message=f"File not found: {processing_file_path}")

            if effective_content_type == "docx":
                error_message = await self._process_docx(
                    processing_file_path, 
                    job_id, 
                    file_input.processing_level,
                    original_file_path, # Pass original GCS path for image linking
                    document_metadata, 
                    preliminary_blocks, 
                    raw_images
                )
            elif effective_content_type == "md":
                error_message = await self._process_markdown(
                    processing_file_path, 
                    job_id, 
                    file_input.processing_level,
                    original_file_path, # Pass original GCS path for image linking
                    document_metadata, 
                    preliminary_blocks, 
                    raw_images
                )
            elif effective_content_type == "txt":
                error_message = await self._process_txt(
                    processing_file_path, 
                    job_id, 
                    document_metadata, 
                    preliminary_blocks
                )
            else:
                error_message = f"Unsupported effective_content_type: {effective_content_type} (from original: {file_input.source_content_type})"
                self.logger.error(error_message)
            
            if error_message:
                return ServiceResult.failure(error_message=f"FileAcquisitionService failed: {error_message}")

            # Final sorting of blocks by their 'order' attribute if set, or keep as is
            # The individual _process_* methods are responsible for setting order within their context.
            # A global sort might be needed if blocks from different sources (e.g., text then images from docx) don't have continuous order.
            # For now, assuming _process_* methods handle order sufficiently for their generated blocks.
            # If _process_* methods assign order starting from 0 for each call, then this sort is necessary.
            # However, they seem to append to the lists, so their relative order should be maintained.
            # Let's ensure order is explicitly set if not done by processors, or sort here.
            # For simplicity, and since PDF service does a final sort, let's add one here too.
            
            # Sort all collected blocks by their 'order' attribute.
            # If 'order' was -1 (placeholder), they might end up at the beginning.
            # It's better if _process_* methods assign meaningful order numbers.
            # Assuming PreliminaryBlock has an 'order' field that's an int.
            # The current _process_* methods set order to -1. This needs fixing in those methods,
            # or a more sophisticated sorting here.
            # For now, let's re-assign order based on append sequence if they are -1.

            current_order_idx = 0
            for pb_idx, pb in enumerate(preliminary_blocks):
                if pb.order == -1 or pb.order is None: # If order not set by processor
                    pb.order = current_order_idx
                current_order_idx = max(current_order_idx, pb.order) + 1
            
            # If processors do set order, but not globally unique, then a sort by current_order_idx might be bad.
            # Let's assume processors append in document order.
            # The PDF service sorts by page, then y-coord, then x-coord. File types here don't have pages.
            # So, simple sequential order is likely best if processors don't set it well.
            # The current change: re-number all blocks sequentially.
            for i, block in enumerate(preliminary_blocks):
                block.order = i


            duration_ms = (time.time() - start_time) * 1000
            self.logger.info(f"FileAcquisitionService for '{original_file_path}' (type: {effective_content_type}) completed in {duration_ms:.2f} ms. Blocks: {len(preliminary_blocks)}, Images: {len(raw_images)}")
            return ServiceResult.success(data=(preliminary_blocks, document_metadata, raw_images))

        except FileNotFoundError as e_fnf: # Should be caught by os.path.exists, but as a safeguard
            self.logger.error(f"FileAcquisitionService FileNotFoundError for {original_file_path}: {e_fnf}", exc_info=True)
            return ServiceResult.failure(error_message=f"File not found: {original_file_path}")
        except Exception as e:
            self.logger.error(f"FileAcquisitionService unexpected error for {original_file_path} (type: {file_input.source_content_type}): {e}", exc_info=True)
            return ServiceResult.failure(error_message=f"FileAcquisitionService failed: {str(e)}")
        finally:
            if temp_gcs_file_path and os.path.exists(temp_gcs_file_path):
                try:
                    await loop.run_in_executor(None, os.unlink, temp_gcs_file_path)
                    self.logger.info(f"FileAcquisitionService: Successfully deleted temporary GCS file: {temp_gcs_file_path}")
                except Exception as e_unlink:
                    self.logger.error(f"FileAcquisitionService: Failed to delete temporary GCS file {temp_gcs_file_path}: {e_unlink}")

# Ensure other methods like _process_docx, _process_markdown, _process_txt are robust.
# ... existing code ... 