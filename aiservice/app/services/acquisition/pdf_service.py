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
        doc: Optional[fitz.Document] = None
        loop = asyncio.get_event_loop()

        if not os.path.exists(pdf_input.file_path):
            # No duration calculation here as it's an early exit
            return ServiceResult.failure(
                error_message=f"File not found: {pdf_input.file_path}"
            )

        try:
            doc = await loop.run_in_executor(None, fitz.open, pdf_input.file_path)
            
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
                extracted_at=datetime.utcnow(),
                total_pages=len(doc),
                language_detected=None,
            )

            for page_num in range(len(doc)):
                page: fitz.Page = await loop.run_in_executor(None, doc.load_page, page_num)
                
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
                page_specific_prelim_blocks = []

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
                        # This was 'image' block from get_text('dict'), often less reliable than get_images()
                        # We rely on get_images() later for robust image extraction.
                        pass 
                
                refined_page_blocks = []
                for block_to_refine in page_specific_prelim_blocks:
                    if block_to_refine.type == "text" and block_to_refine.text_content:
                        lines = block_to_refine.text_content.split('\n') 
                        current_refined_parts = [] 
                        non_list_text_parts = []
                        list_marker_pattern = re.compile(r"^(?:\s*(?:[a-zA-Z][.)]|[*•\-]|\d+[.)])\s+)")
                        block_had_list_items = False

                        for line_idx, line_text in enumerate(lines):
                            if not isinstance(line_text, str):
                                non_list_text_parts.append(str(line_text))
                                continue

                            match = list_marker_pattern.match(line_text)
                            if match:
                                block_had_list_items = True
                                marker_full = match.group(0)
                                marker_content = marker_full.strip()
                                item_text = line_text[len(marker_full):].strip()
                                
                                if not item_text: 
                                    non_list_text_parts.append(line_text)
                                    continue
                                
                                is_ordered_list_type = False 
                                if marker_content.endswith(('.', ')')):
                                    check_marker = marker_content[:-1].strip()
                                    if check_marker.isdigit() or (len(check_marker) == 1 and check_marker.isalpha()):
                                        is_ordered_list_type = True
                                elif marker_content.isdigit():
                                    is_ordered_list_type = True
                                
                                if non_list_text_parts:
                                    current_refined_parts.append(PreliminaryBlock(
                                        block_id=f"{block_to_refine.block_id}_txt_pre_li{line_idx}", type="text",
                                        text_content="\n".join(non_list_text_parts).strip(),
                                        page_number=block_to_refine.page_number, bbox=block_to_refine.bbox, order=-1
                                    ))
                                    non_list_text_parts = []
                                
                                current_refined_parts.append(PreliminaryBlock(
                                    block_id=f"{block_to_refine.block_id}_li{line_idx}", type="list_item",
                                    text_content=item_text, page_number=block_to_refine.page_number, bbox=block_to_refine.bbox, order=-1,
                                    list_item_data=item_text, list_level=0, list_ordered=is_ordered_list_type
                                ))
                            else:
                                non_list_text_parts.append(line_text)
                        
                        if block_had_list_items:
                            if non_list_text_parts:
                                current_refined_parts.append(PreliminaryBlock(
                                    block_id=f"{block_to_refine.block_id}_txt_post_li", type="text",
                                    text_content="\n".join(non_list_text_parts).strip(),
                                    page_number=block_to_refine.page_number, bbox=block_to_refine.bbox, order=-1
                                ))
                            refined_page_blocks.extend(current_refined_parts) 
                        else:
                            refined_page_blocks.append(block_to_refine)
                    else: 
                        refined_page_blocks.append(block_to_refine)
                preliminary_blocks.extend(refined_page_blocks)

                if pdf_input.processing_level == "full_content":
                    image_list_infos = await loop.run_in_executor(None, page.get_images, True)
                    for img_idx, img_info in enumerate(image_list_infos):
                        xref = img_info[0]
                        try:
                            base_image_dict = await loop.run_in_executor(None, doc.extract_image, xref)
                            if not base_image_dict: 
                                continue
                            
                            image_bytes = base_image_dict.get("image")
                            img_extension = base_image_dict.get("ext")

                            if not image_bytes or not img_extension:
                                continue

                            raw_image_id = f"img_{job_id}_p{page_num + 1}_xref{xref}_idx{img_idx}"
                            mime_type = f"image/{img_extension.lower()}"
                            if img_extension.lower() == 'jpx': mime_type = 'image/jp2'

                            raw_img_obj = RawImageInput(
                                image_id=raw_image_id,
                                image_bytes=image_bytes,
                                source_document_id=job_id, 
                                original_filename=pdf_filename,
                                page_number=page_num + 1,
                                bbox=None, 
                                mime_type=mime_type,
                                original_source_identifier_for_gcs_path=pdf_input.file_path,
                                source_type_for_gcs_path="pdf",
                                job_id_for_gcs_path=job_id
                            )
                            raw_images.append(raw_img_obj)

                            placeholder_block_id = f"{job_id}_p{page_num + 1}_imgplaceholder_{img_idx}"
                            img_bbox_on_page = None
                            try:
                                img_bboxes_on_page = await loop.run_in_executor(None, page.get_image_bboxes, img_info, transform=False)
                                if img_bboxes_on_page:
                                    img_bbox_on_page = list(img_bboxes_on_page[0])
                            except Exception as e_bbox:
                                print(f"PDFAcquisitionService: INFO - Could not get bbox for image xref {xref} on page {page_num + 1}: {e_bbox}")

                            preliminary_blocks.append(PreliminaryBlock(
                                block_id=placeholder_block_id,
                                type="image_placeholder",
                                image_id_ref=raw_image_id,
                                page_number=page_num + 1,
                                bbox=img_bbox_on_page,
                                order=-1,
                                custom_attributes={"original_img_xref": xref}
                            ))
                        except Exception as e_img:
                            print(f"PDFAcquisitionService: Error processing image xref {xref} on page {page_num + 1}: {e_img}")
                            continue
            
            def sort_key(block: PreliminaryBlock):
                page_val = block.page_number if block.page_number is not None else float('inf')
                y0_val = float('inf')
                if block.bbox and isinstance(block.bbox, (list, tuple)) and len(block.bbox) >= 2:
                    y0_val = block.bbox[1] 
                x0_val = float('inf')
                if block.bbox and isinstance(block.bbox, (list, tuple)) and len(block.bbox) >= 1:
                    x0_val = block.bbox[0]
                return (page_val, y0_val, x0_val)

            preliminary_blocks.sort(key=sort_key)
            for i, block in enumerate(preliminary_blocks):
                block.order = i
            
            if document_metadata is None: 
                print("PDFAcquisitionService: ERROR - DocumentMetadata was not initialized!")
                document_metadata = DocumentMetadata(
                    document_id=job_id, 
                    source_identifier=pdf_input.file_path, 
                    source_type="pdf",
                    title=pdf_filename,
                    extracted_at=datetime.utcnow(),
                    total_pages=len(doc) if doc else 0
                )
            
            duration = time.time() - start_time
            print(f"PDFAcquisitionService: Completed for {pdf_filename} in {duration:.2f}s. Blocks: {len(preliminary_blocks)}, Images: {len(raw_images)}") # Keep this for success logging
            return ServiceResult.success(data=(preliminary_blocks, document_metadata, raw_images))

        except FileNotFoundError:
            # duration not applicable as it's an early check or OS error
            return ServiceResult.failure(
                error_message=f"File not found: {pdf_input.file_path}"
            )
        except fitz.fitz.TraitError as e_fitz_trait:
            duration = time.time() - start_time
            error_msg = f"PyMuPDF TraitError processing PDF '{pdf_filename}': {str(e_fitz_trait)}. Document might be malformed or password-protected."
            print(f"PDFAcquisitionService: {error_msg}")
            return ServiceResult.failure(error_message=error_msg)
        except fitz.fitz.FileDataError as e_fitz_data:
            duration = time.time() - start_time
            error_msg = f"PyMuPDF FileDataError processing PDF '{pdf_filename}': {str(e_fitz_data)}. Document might be corrupted, empty, or not a valid PDF."
            print(f"PDFAcquisitionService: {error_msg}")
            return ServiceResult.failure(error_message=error_msg)
        except RuntimeError as e_runtime: 
            duration = time.time() - start_time
            error_msg = f"Runtime error processing PDF '{pdf_filename}': {str(e_runtime)}. Check if PDF is password-protected."
            if "password" in str(e_runtime).lower():
                 error_msg = f"PDF '{pdf_filename}' is password-protected and cannot be opened."
            print(f"PDFAcquisitionService: {error_msg}")
            return ServiceResult.failure(error_message=error_msg)
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Unexpected error processing PDF '{pdf_filename}': {str(e)}"
            print(f"PDFAcquisitionService: {error_msg}") 
            import traceback
            traceback.print_exc()
            return ServiceResult.failure(
                error_message=f"Error parsing PDF '{pdf_filename}': {str(e)}",
            )
        finally:
            if doc:
                try:
                    await loop.run_in_executor(None, doc.close)
                except Exception as e_close:
                     print(f"PDFAcquisitionService: Error closing document '{pdf_filename}' after processing: {e_close}")

        # The old way of constructing PDFAcquisitionServiceOutput and returning ServiceResult
        # is replaced by direct construction of the Tuple for success, or simple failure message.
        # The detailed status strings like "success_text_only" are less critical now,
        # as the presence/absence of data in the tuple components implies the outcome. 