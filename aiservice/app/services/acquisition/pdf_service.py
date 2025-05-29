import asyncio
import fitz # PyMuPDF
import os
import uuid
import time
import re
from typing import Optional, Any, List, Dict, Tuple
from pydantic import BaseModel, Field
from datetime import datetime
import functools # Added for functools.partial

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput

# --- Pydantic Models for PDFAcquisitionService ---

class PDFAcquisitionServiceInput(BaseModel):
    file_path: str = Field(..., description="Path to the PDF file to process.")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking.")
    # original_source_identifier_for_gcs_path will be derived from file_path
    # source_type_for_gcs_path will be 'pdf'
    # job_id_for_gcs_path will be job_id

class PDFAcquisitionService(BaseService):
    """
    Asynchronous service to extract text and image placeholders from PDF files,
    producing PreliminaryBlock, DocumentMetadata, and RawImageInput objects.
    """
    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        # LLM image analysis is no longer performed by this service.
        # It will be handled by ImageProcessingService based on RawImageInput.

    async def execute(self, pdf_input: PDFAcquisitionServiceInput) -> ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]:
        start_time = time.time()
        job_id = pdf_input.job_id or uuid.uuid4().hex[:8]
        pdf_filename = os.path.basename(pdf_input.file_path)

        preliminary_blocks: List[PreliminaryBlock] = []
        raw_images: List[RawImageInput] = []
        document_metadata: Optional[DocumentMetadata] = None 

        if not os.path.exists(pdf_input.file_path):
            duration = time.time() - start_time
            # Simpler error return
            return ServiceResult.failure(
                error_message=f"File not found: {pdf_input.file_path}",
                # No detailed error model needed here as per new design for simple failures
            )

        loop = asyncio.get_event_loop()
        doc: Optional[fitz.Document] = None # Define doc here to ensure it's in scope for finally

        try:
            doc = await loop.run_in_executor(None, fitz.open, pdf_input.file_path)
            
            # Populate DocumentMetadata
            pdf_meta = await loop.run_in_executor(None, getattr, doc, 'metadata')
            creation_dt = None
            modification_dt = None
            if pdf_meta:
                if pdf_meta.get('creationDate'):
                    try:
                        raw_date = pdf_meta['creationDate']
                        clean_date_str = raw_date[2:16]
                        creation_dt = datetime.strptime(clean_date_str, '%Y%m%d%H%M%S')
                    except (ValueError, TypeError) as e_creation:
                        print(f"PDFAcquisitionService: Warning - Could not parse creationDate '{pdf_meta['creationDate']}': {e_creation}")
                if pdf_meta.get('modDate'):
                    try:
                        raw_date = pdf_meta['modDate']
                        clean_date_str = raw_date[2:16]
                        modification_dt = datetime.strptime(clean_date_str, '%Y%m%d%H%M%S')
                    except (ValueError, TypeError) as e_mod:
                        print(f"PDFAcquisitionService: Warning - Could not parse modDate '{pdf_meta['modDate']}': {e_mod}")

            document_metadata = DocumentMetadata(
                document_id=job_id,
                source_identifier=pdf_input.file_path,
                source_type="pdf",
                title=pdf_meta.get('title') if pdf_meta else pdf_filename,
                author=pdf_meta.get('author') if pdf_meta else None,
                subject=pdf_meta.get('subject') if pdf_meta else None,
                keywords=pdf_meta.get('keywords').split(' ') if pdf_meta and pdf_meta.get('keywords') else [],
                creation_date=creation_dt,
                modification_date=modification_dt,
                extracted_at=datetime.utcnow(), # Ensure this is set
                total_pages=len(doc),
                language_detected=None,
            )

            # --- Page iteration and content extraction logic ---
            for page_num in range(len(doc)):
                page: fitz.Page = await loop.run_in_executor(None, doc.load_page, page_num)
                
                # Corrected call to page.get_text using functools.partial
                get_text_dict_sorted = functools.partial(page.get_text, "dict", sort=True)
                page_text_dict = await loop.run_in_executor(None, get_text_dict_sorted)

                font_styles = {}
                for block_content in page_text_dict.get("blocks", []) :
                    if block_content["type"] == 0: # Text block
                        for line in block_content.get("lines", []):
                            for span in line.get("spans", []):
                                style_key = (span["size"], span["font"])
                                font_styles[style_key] = font_styles.get(style_key, 0) + len(span["text"])
                
                body_text_style = None
                if font_styles:
                    body_text_style = max(font_styles, key=font_styles.get)

                current_block_idx = 0

                page_specific_prelim_blocks = [] # Accumulate blocks for this page first

                for block_dict_item in page_text_dict.get("blocks", []) :
                    if block_dict_item["type"] == 0: # Text block
                        block_text_content = ""
                        is_heading_candidate = False
                        heading_level_candidate = None
                        span_bboxes_list = []
                        if body_text_style: 
                            num_heading_spans = 0
                            num_total_spans = 0
                            span_font_sizes = []
                            current_line_spans_bboxes = []
                            for line_dict in block_dict_item.get("lines", []):
                                for span_dict in line_dict.get("spans", []):
                                    num_total_spans += 1
                                    span_font_sizes.append(span_dict["size"])
                                    is_bold = (span_dict["flags"] & 16) > 0 
                                    if span_dict["size"] > body_text_style[0] + 1.0 or (is_bold and span_dict["size"] >= body_text_style[0] - 0.5) :
                                        num_heading_spans +=1
                                    current_line_spans_bboxes.append(span_dict["bbox"])
                                    block_text_content += span_dict["text"]
                                if current_line_spans_bboxes:
                                    span_bboxes_list.extend(current_line_spans_bboxes)
                                    current_line_spans_bboxes = []
                                block_text_content += " " 
                            block_text_content = block_text_content.strip()
                            if not block_text_content: continue
                            if num_total_spans > 0 and (num_heading_spans / num_total_spans) > 0.6:
                                is_heading_candidate = True
                                avg_span_size = sum(span_font_sizes) / len(span_font_sizes) if span_font_sizes else body_text_style[0]
                                if avg_span_size > body_text_style[0] * 1.4: heading_level_candidate = 1
                                elif avg_span_size > body_text_style[0] * 1.2: heading_level_candidate = 2
                                elif avg_span_size > body_text_style[0] * 1.05: heading_level_candidate = 3
                                else: heading_level_candidate = 4 
                        else: 
                             for line_dict in block_dict_item.get("lines", []):
                                for span_dict in line_dict.get("spans", []):
                                    block_text_content += span_dict["text"]
                                    span_bboxes_list.append(span_dict["bbox"])
                                block_text_content += " "
                             block_text_content = block_text_content.strip()
                             if not block_text_content: continue
                        block_bbox = block_dict_item["bbox"] 
                        if span_bboxes_list:
                            min_x0 = min(b[0] for b in span_bboxes_list)
                            min_y0 = min(b[1] for b in span_bboxes_list)
                            max_x1 = max(b[2] for b in span_bboxes_list)
                            max_y1 = max(b[3] for b in span_bboxes_list)
                            block_bbox = [min_x0, min_y0, max_x1, max_y1]
                        block_type = "text"
                        prelim_block_specific_fields = {"text_content": block_text_content}
                        if is_heading_candidate and heading_level_candidate is not None:
                            block_type = "heading"
                            prelim_block_specific_fields = {"text_content": block_text_content, "heading_level": heading_level_candidate}
                        page_specific_prelim_blocks.append(PreliminaryBlock(
                            block_id=f"{job_id}_p{page_num + 1}_b{current_block_idx}", type=block_type,
                            page_number=page_num + 1, bbox=block_bbox, order=-1, 
                            custom_attributes={}, **prelim_block_specific_fields
                        ))
                        current_block_idx += 1
                    elif block_dict_item["type"] == 1 and pdf_input.processing_level == "full_content": 
                        pass 
                
                # Refine page_specific_prelim_blocks for list items
                refined_page_blocks = []
                for block_to_refine in page_specific_prelim_blocks:
                    if block_to_refine.type == "text":
                        lines = block_to_refine.text_content.split('\\n') 
                        non_list_text_parts = []
                        # Restoring full regex with reordered alternatives
                        list_marker_pattern = re.compile(r"^(\s*(?:[a-zA-Z][.)]|[*•\-]|\d+[.)])\s+)")
                        is_ordered_list_type = False
                        block_had_list_items = False
                        for line_idx, line_text in enumerate(lines):
                            match = list_marker_pattern.match(line_text)
                            if match:
                                block_had_list_items = True
                                marker = match.group(1).strip()
                                item_text = line_text[len(match.group(0)):].strip()
                                if not item_text: 
                                    non_list_text_parts.append(line_text)
                                    continue
                                is_ordered_list_type = False 
                                if marker[-1] == '.' or marker[-1] == ')':
                                    marker_content = marker[:-1].strip()
                                    if marker_content.isdigit() or (len(marker_content) == 1 and marker_content.isalpha()):
                                        is_ordered_list_type = True
                                if non_list_text_parts: 
                                    refined_page_blocks.append(PreliminaryBlock(
                                        block_id=f"{block_to_refine.block_id}_txt_pre_li{line_idx}", type="text",
                                        text_content="\n".join(non_list_text_parts).strip(),
                                        page_number=block_to_refine.page_number, bbox=block_to_refine.bbox, order=-1
                                    ))
                                    non_list_text_parts = []
                                refined_page_blocks.append(PreliminaryBlock(
                                    block_id=f"{block_to_refine.block_id}_li{line_idx}", type="list_item",
                                    text_content=item_text, page_number=block_to_refine.page_number, bbox=block_to_refine.bbox, order=-1,
                                    list_item_data=item_text, list_level=0, list_ordered=is_ordered_list_type
                                ))
                            else:
                                non_list_text_parts.append(line_text)
                        
                        # After processing all lines in the block_to_refine:
                        if non_list_text_parts: # Any remaining text after the last list item or if no list items
                            refined_page_blocks.append(PreliminaryBlock(
                                block_id=f"{block_to_refine.block_id}_txt_post_li", type="text",
                                text_content="\n".join(non_list_text_parts).strip(),
                                page_number=block_to_refine.page_number, bbox=block_to_refine.bbox, order=-1
                            ))
                        
                        # If the block_to_refine had no list items at all, it means its original form is what we want.
                        # If it did have list items, its content has been broken down into list_items and potentially txt_pre/post_li parts.
                        # So, only add the original block_to_refine if it wasn't processed for lists.
                        if not block_had_list_items:
                             refined_page_blocks.append(block_to_refine)
                    else: # If block_to_refine is not of type "text" (e.g., already a heading), add it as is.
                        refined_page_blocks.append(block_to_refine)
                preliminary_blocks.extend(refined_page_blocks) # Add processed blocks for this page to the main list

                # Image Extraction (ensure block_id for image placeholders is unique)
                if pdf_input.processing_level == "full_content":
                    image_list_infos = await loop.run_in_executor(None, page.get_images, True)
                    for img_idx, img_info in enumerate(image_list_infos):
                        xref = img_info[0]
                        try:
                            base_image_dict = await loop.run_in_executor(None, doc.extract_image, xref)
                            if not base_image_dict: continue
                            image_bytes = base_image_dict["image"]
                            img_extension = base_image_dict["ext"]
                            raw_image_id = f"img_{job_id}_p{page_num + 1}_xref{xref}_idx{img_idx}"
                            img_bbox_on_page = None
                            try:
                                bbox_or_rects = await loop.run_in_executor(None, page.get_image_bbox, img_info)
                                if isinstance(bbox_or_rects, list) and len(bbox_or_rects) > 0 and isinstance(bbox_or_rects[0], fitz.Rect):
                                    img_bbox_on_page = list(bbox_or_rects[0])
                                elif isinstance(bbox_or_rects, fitz.Rect):
                                    img_bbox_on_page = list(bbox_or_rects)
                            except AttributeError as e_bbox_attr: 
                                print(f"PDFAcquisitionService: Info - page.get_image_bbox attribute error for image xref {xref} on page {page_num+1}: {e_bbox_attr}")
                            except Exception as e_bbox: 
                                print(f"PDFAcquisitionService: Warning - Error getting bbox for image xref {xref} on page {page_num+1}: {e_bbox}")
                            raw_images.append(RawImageInput(
                                image_id=raw_image_id, image_bytes=image_bytes, source_url=None,
                                original_filename=f"image_p{page_num+1}_{xref}.{img_extension}",
                                source_document_id=job_id, page_number=page_num + 1, bbox=img_bbox_on_page,
                                mime_type=f"image/{img_extension}", alt_text=None, caption=None,
                                original_source_identifier_for_gcs_path=pdf_input.file_path,
                                source_type_for_gcs_path="pdf", job_id_for_gcs_path=job_id
                            ))
                            preliminary_blocks.append(PreliminaryBlock( # Add image placeholder to the main list directly
                                block_id=f"{job_id}_p{page_num + 1}_img{img_idx}", type="image_placeholder", # Uses img_idx now
                                image_id_ref=raw_image_id, page_number=page_num + 1, bbox=img_bbox_on_page,
                                order=-1
                            ))
                        except Exception as e_img_extract:
                            print(f"PDFAcquisitionService: Error extracting/processing image xref {xref} on page {page_num+1}: {e_img_extract}")            
            # --- End of Page Iteration ---

            # Sort all PreliminaryBlocks from all pages and assign final order
            def sort_key(block: PreliminaryBlock):
                y_coord = block.bbox[1] if block.bbox and len(block.bbox) > 1 else 0
                x_coord = block.bbox[0] if block.bbox and len(block.bbox) > 0 else 0
                return (block.page_number or 0, y_coord, x_coord)
            
            preliminary_blocks.sort(key=sort_key)
            for i, block in enumerate(preliminary_blocks):
                block.order = i
            
            return ServiceResult.success(data=(preliminary_blocks, document_metadata, raw_images))

        except Exception as e:
            # Ensure doc is closed if opened and an error occurs after opening
            # This is complex because 'doc' might not be assigned if fitz.open itself fails.
            # A more robust solution would be a try/finally within the executor for fitz.open and close.
            # For now, this is a general catch.
            print(f"PDFAcquisitionService: Error processing PDF '{pdf_filename}': {str(e)}")
            # Attempt to close doc if it exists (and fitz.open was successful)
            # This might still fail if doc is not in a closable state or fitz.open itself failed.
            if 'doc' in locals() and doc and hasattr(doc, 'close') and not doc.is_closed:
                 try:
                     await loop.run_in_executor(None, doc.close)
                     print(f"PDFAcquisitionService: Closed document '{pdf_filename}' after exception.")
                 except Exception as e_close:
                     print(f"PDFAcquisitionService: Error closing document '{pdf_filename}' after exception: {e_close}")
            
            duration = time.time() - start_time
            return ServiceResult.failure(
                error_message=f"Error parsing PDF '{pdf_filename}': {str(e)}",
            )
        finally:
            if doc:
                try:
                    await loop.run_in_executor(None, doc.close)
                    print(f"PDFAcquisitionService: Closed document '{pdf_filename}' in finally block.")
                except Exception as e_close_final:
                    print(f"PDFAcquisitionService: Error closing document '{pdf_filename}' in finally block: {e_close_final}")
        
        # The old way of constructing PDFAcquisitionServiceOutput and returning ServiceResult
        # is replaced by direct construction of the Tuple for success, or simple failure message.
        # The detailed status strings like "success_text_only" are less critical now,
        # as the presence/absence of data in the tuple components implies the outcome. 