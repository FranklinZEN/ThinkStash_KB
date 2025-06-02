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
    user_id: Optional[str] = None # Added user_id

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
                                            original_source_identifier_for_gcs_path=file_path,
                                            source_type_for_gcs_path=source_type_for_gcs,
                                            job_id_for_gcs_path=job_id
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
                                source_type_for_gcs: str, 
                                base_document_metadata: DocumentMetadata, 
                                preliminary_blocks: List[PreliminaryBlock], 
                                raw_images: List[RawImageInput]
                                ) -> Optional[str]: # Return an error message string if fails, else None
        loop = asyncio.get_event_loop()
        md_parser = MarkdownIt("gfm-like", {"linkify": False}) # Using gfm-like, disable linkify to avoid ModuleNotFoundError
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
                    
                    current_text_segment = "" # Buffer for text segments within a paragraph
                    
                    # Iterate through all children of the inline token that represents the paragraph content
                    # The actual inline content is often in tokens[idx] if it's a simple paragraph,
                    # or we might need to look at tokens[idx].children if it's more complex.
                    # markdown-it-py usually puts paragraph content into a single 'inline' token.
                    
                    inline_token_children = []
                    if tokens[idx].type == "inline" and tokens[idx].children:
                        inline_token_children = tokens[idx].children
                    # Sometimes, simple text might not be wrapped in an 'inline' token with children,
                    # but could be a sequence of 'text', 'softbreak', etc., directly.
                    # However, the common case for GFM-like is an 'inline' token containing children.

                    paragraph_children_processed_until = idx # Keep track of how many tokens of the main stream are consumed by this paragraph
                    
                    temp_inline_idx = idx 
                    # The 'inline' token itself (tokens[temp_inline_idx]) contains the children.
                    # The loop should go until 'paragraph_close'.
                    
                    if tokens[temp_inline_idx].type == "inline":
                        for child_token in tokens[temp_inline_idx].children or []:
                            if child_token.type == "text":
                                current_text_segment += child_token.content
                            elif child_token.type == "softbreak":
                                current_text_segment += "\\n" # Preserve soft line breaks as newlines in text
                            elif child_token.type == "hardbreak":
                                current_text_segment += "\\n\\n" # Preserve hard line breaks as double newlines
                            elif child_token.type == "image":
                                # 1. Finalize any preceding text segment
                                if current_text_segment.strip():
                                    preliminary_blocks.append(PreliminaryBlock(
                                        block_id=f"{job_id}_{block_id_suffix}_p_txt{len(preliminary_blocks)}", type="text",
                                        text_content=current_text_segment.strip(),
                                        order=-1, page_number=None, bbox=None
                                    ))
                                    current_block_idx +=1
                                current_text_segment = "" # Reset for text after image
                                
                                # 2. Process the image
                                img_ref_idx +=1
                                img_src = child_token.attrs.get('src', '')
                                img_alt = child_token.content # alt text is in child_token.content for image
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
                                    resolved_path = img_src
                                    if not os.path.isabs(resolved_path):
                                        resolved_path = os.path.join(os.path.dirname(file_path), img_src)
                                    
                                    if os.path.exists(resolved_path):
                                        try:
                                            # Reading file bytes synchronously for now as it's inside a loop
                                            # that's already part of an async executor task for the whole md file.
                                            with open(resolved_path, 'rb') as img_f:
                                                image_data_dict["image_bytes"] = img_f.read()
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
                                current_block_idx +=1
                            # Other inline token types (strong, em, etc.) contribute to current_text_segment via their own .content
                            elif hasattr(child_token, 'content') and child_token.content:
                                current_text_segment += child_token.content
                        
                        # After iterating all children of the inline token, advance main 'idx' past this inline token
                        idx = temp_inline_idx # Main idx was already pointing to the inline token. It will be incremented at the end of the outer while loop.
                                              # We need to ensure we find paragraph_close next.
                    
                    # The next token after 'inline' should be 'paragraph_close'. We find it to correctly advance idx.
                    # This ensures that idx points to paragraph_close before the outer loop increments it.
                    temp_para_close_finder_idx = idx + 1 
                    while temp_para_close_finder_idx < len(tokens) and tokens[temp_para_close_finder_idx].type != "paragraph_close":
                        temp_para_close_finder_idx += 1
                    if temp_para_close_finder_idx < len(tokens) and tokens[temp_para_close_finder_idx].type == "paragraph_close":
                        idx = temp_para_close_finder_idx
                    else:
                        # This case should ideally not happen if markdown is well-formed
                        self.logger.warning(f"MD Service: paragraph_close token not found immediately after inline content for paragraph starting near token {original_idx_for_para_open}. Might misinterpret structure.")
                        # Advance idx by one if it's still on the inline token to avoid infinite loop.
                        if idx == temp_inline_idx : idx +=1 


                    # Finalize any remaining text segment for the paragraph
                    if current_text_segment.strip():
                        preliminary_blocks.append(PreliminaryBlock(
                            block_id=f"{job_id}_{block_id_suffix}_p_txt{len(preliminary_blocks)}", type="text",
                            text_content=current_text_segment.strip(),
                            order=-1, page_number=None, bbox=None
                        ))
                        current_block_idx += 1
                    current_text_segment = "" # Reset for next paragraph
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
        # Use job_id from input or generate one
        current_job_id = file_input.job_id or f"file_job_{uuid.uuid4().hex[:8]}"
        # Get user_id from input
        current_user_id = file_input.user_id

        preliminary_blocks: List[PreliminaryBlock] = []
        raw_images: List[RawImageInput] = []
        
        # Initialize DocumentMetadata with job_id and user_id early
        document_metadata = DocumentMetadata(
            document_id=current_job_id,
            user_id=current_user_id or "unknown_user_file_service",
            source_identifier=file_input.file_path,
            source_type=file_input.source_content_type,
            title=os.path.basename(file_input.file_path),
            extracted_at=datetime.utcnow()
            # Other fields will be populated by specific processors
        )

        if not os.path.exists(file_input.file_path):
            duration = time.time() - start_time
            # Update error reporting to be simpler
            return ServiceResult.failure(
                error_message=f"File not found: {file_input.file_path}",
                # No detailed error model needed for simple failures
            )
        
        call_error_message: Optional[str] = None # Error message from _process_... calls

        try:
            if file_input.source_content_type.lower() == "docx":
                    call_error_message = await self._process_docx(
                        file_path=file_input.file_path, 
                        job_id=current_job_id, 
                        processing_level=file_input.processing_level,
                        source_type_for_gcs=file_input.source_content_type, 
                        base_document_metadata=document_metadata, # Pass the main object
                        preliminary_blocks=preliminary_blocks, 
                        raw_images=raw_images
                    )
            elif file_input.source_content_type.lower() == "md":
                    call_error_message = await self._process_markdown(
                        file_path=file_input.file_path, 
                        job_id=current_job_id, 
                        processing_level=file_input.processing_level,
                        source_type_for_gcs=file_input.source_content_type,
                        base_document_metadata=document_metadata, # Pass the main object
                        preliminary_blocks=preliminary_blocks, 
                        raw_images=raw_images
                    )
            elif file_input.source_content_type.lower() == "txt":
                    call_error_message = await self._process_txt(
                        file_path=file_input.file_path,
                        job_id=current_job_id, # Pass job_id for block_id generation consistency
                        base_document_metadata=document_metadata, # Pass the main object
                        preliminary_blocks=preliminary_blocks
                    )
            # Fallback for file_ext_... can be removed if RoutingService handles this better,
            # or adapted if truly needed here. For now, focusing on specified types.
            else:
                    call_error_message = f"Unsupported file type: {file_input.source_content_type}"
            
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
            self.logger.error(f"FileAcquisitionService: Unhandled error processing {file_input.file_path}: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                error_message=f"Error processing file {os.path.basename(file_input.file_path)}: {str(e)}",
            ) 