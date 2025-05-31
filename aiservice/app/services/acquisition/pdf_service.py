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
import logging # Added logging

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput

# --- Pydantic Models for PDFAcquisitionService ---

class PDFAcquisitionServiceInput(BaseModel):
    file_path: str = Field(..., description="Path to the PDF file to process.")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking.")
    user_id: Optional[str] = Field(None, description="Optional user ID for tracking and associating with metadata.")
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
        self.settings = settings # Store settings if provided for future use (e.g. debug_mode)
        self.logger = logging.getLogger(__name__) # Initialize logger
        if self.settings and hasattr(self.settings, 'debug_mode') and self.settings.debug_mode:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO) # Default to INFO
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
                        self.logger.warning(f"PDFAcquisitionService: Warning - Could not parse creationDate '{pdf_meta['creationDate']}': {e_creation}")
                if pdf_meta.get('modDate'):
                    try:
                        raw_date = pdf_meta['modDate']
                        clean_date_str = raw_date[2:16]
                        modification_dt = datetime.strptime(clean_date_str, '%Y%m%d%H%M%S')
                    except (ValueError, TypeError) as e_mod:
                        self.logger.warning(f"PDFAcquisitionService: Warning - Could not parse modDate '{pdf_meta['modDate']}': {e_mod}")

            document_metadata = DocumentMetadata(
                document_id=job_id,
                user_id=pdf_input.user_id,
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
                            
                            if not image_bytes:
                                self.logger.warning(f"PDFAcquisitionService: Warning - Could not extract image bytes for xref {xref} on page {page_num + 1} of {pdf_input.file_path}. Skipping image.")
                                continue

                            image_id = f"{job_id}_p{page_num + 1}_img{img_idx}"
                            
                            # Attempt to get bounding box from image info itself if available
                            # PyMuPDF's get_images(full=True) provides (xref, smask, width, height, bpc, colorspace, ...)
                            # The bounding box of the *image usage* on the page is more complex.
                            # We will use a placeholder bbox or try to find it via page.get_image_rects()
                            # This part might need refinement if precise image bbox on page is critical.
                            img_bbox_on_page = None
                            try:
                                # Directly call page.get_image_bbox with img_info and transform=False (as the third positional arg)
                                bbox_or_rects = await loop.run_in_executor(None, page.get_image_bbox, img_info, False)
                                
                                if isinstance(bbox_or_rects, fitz.Rect) and bbox_or_rects.is_valid and not bbox_or_rects.is_empty:
                                    img_bbox_on_page = list(bbox_or_rects)
                            except Exception as e_img_bbox:
                                self.logger.warning(f"PDFAcquisitionService: Warning - Could not get image bbox for xref {xref} on page {page_num + 1}: {e_img_bbox}")
                            
                            new_raw_image = RawImageInput(
                                image_id=image_id,
                                image_bytes=image_bytes,
                                source_document_id=pdf_input.file_path,
                                original_filename=f"image_{xref}.{img_extension}",
                                page_number=page_num + 1,
                                bbox=img_bbox_on_page, # Bounding box on the page
                                mime_type=f"image/{img_extension}" if img_extension else None,
                                alt_text=None, # PDFs generally don't have structured alt text for images like HTML
                                caption=None,  # Captions might be inferred from nearby text later if needed
                                original_source_identifier_for_gcs_path=pdf_input.file_path, # For GCS path
                                source_type_for_gcs_path="pdf", # For GCS path
                                job_id_for_gcs_path=job_id # For GCS path
                            )
                            raw_images.append(new_raw_image)

                            # Create an image placeholder block
                            # The order of this placeholder relative to text blocks needs to be determined.
                            # For now, we add it after all text blocks for the page, then sort globally.
                            preliminary_blocks.append(PreliminaryBlock(
                                block_id=f"{job_id}_p{page_num + 1}_imgph{img_idx}",
                                type="image_placeholder",
                                image_id_ref=image_id,
                                page_number=page_num + 1,
                                bbox=img_bbox_on_page, # Use the same bbox as the raw image input
                                order=-1, # Will be sorted later
                                custom_attributes={"original_xref": xref}
                            ))
                        except Exception as e_img_extract:
                            self.logger.error(f"PDFAcquisitionService: Failed to extract image (xref {xref}, idx {img_idx}) on page {page_num + 1} of '{pdf_input.file_path}': {e_img_extract}", exc_info=True)
            
            # Sort all preliminary blocks by page number, then by an estimated vertical position (y0 of bbox)
            # and for images/placeholders that might not have a reliable y0 initially, use a secondary key or ensure order is stable.
            def sort_key(block: PreliminaryBlock):
                primary_sort = block.page_number if block.page_number is not None else float('inf')
                
                secondary_sort_val = float('inf') # Default for items without a bbox or with unusual bbox
                if block.bbox and len(block.bbox) >= 2:
                    secondary_sort_val = block.bbox[1] # y0 - vertical position
                    if block.type == "image_placeholder" and block.bbox[1] == 0.0 and block.bbox[0] == 0.0: # Potentially unplaced image
                         # Attempt to place them after text blocks on the same page if y0 is 0.0 (often a sign of unplaced)
                         # This is a heuristic. A more robust way would be to interleave based on original document structure.
                         secondary_sort_val = float('inf') # Put at end of page if bbox is [0,0,0,0] or similar
                
                # Ensure stable sort for items with same page and y0, using block_id as tie-breaker
                return (primary_sort, secondary_sort_val, block.block_id)

            preliminary_blocks.sort(key=sort_key)
            
            # Assign final order based on the sort
            for i, block in enumerate(preliminary_blocks):
                block.order = i

            if document_metadata is None: 
                self.logger.error("PDFAcquisitionService: ERROR - DocumentMetadata was not initialized!")
                document_metadata = DocumentMetadata(
                    document_id=job_id, 
                    source_identifier=pdf_input.file_path, 
                    source_type="pdf",
                    title=pdf_filename,
                    extracted_at=datetime.utcnow(),
                    total_pages=len(doc) if doc else 0
                )
            
            duration = time.time() - start_time
            self.logger.info(f"PDFAcquisitionService: Completed for {pdf_filename} in {duration:.2f}s. Blocks: {len(preliminary_blocks)}, Images: {len(raw_images)}") # Keep this for success logging
            return ServiceResult.success(data=(preliminary_blocks, document_metadata, raw_images))

        except fitz.fitz.EmptyFileError:
            # No duration calculation here as it's an early exit
            return ServiceResult.failure(error_message=f"File is empty or corrupted: {pdf_input.file_path}")
        except Exception as e_main:
            duration = time.time() - start_time
            self.logger.error(f"PDFAcquisitionService: Failed to process '{pdf_input.file_path}' in {duration:.2f}s: {e_main}", exc_info=True)
            return ServiceResult.failure(
                error_message=f"Error processing PDF '{pdf_filename}': {str(e_main)}",
                error_details={ "filename": pdf_filename, "duration_seconds": duration }
            )
        finally:
            if doc:
                await loop.run_in_executor(None, doc.close)
        
        duration = time.time() - start_time
        self.logger.info(f"PDFAcquisitionService: Successfully processed '{pdf_input.file_path}' in {duration:.2f}s. Blocks: {len(preliminary_blocks)}, Images: {len(raw_images)}.")
        
        return ServiceResult.success(
            data=(preliminary_blocks, document_metadata, raw_images),
            details={"filename": pdf_filename, "job_id": job_id, "duration_ms": duration, "pages_processed": len(doc) if doc else 0}
        )

# Example usage (for testing purposes)
async def main_test_pdf_service():
    # Basic test setup (replace with actual testing framework)
    # Configure basic logging for the test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    print("Starting PDFAcquisitionService test...")
    
    # Create a dummy settings object if your service expects one
    class DummySettings:
        debug_mode = True # Or False, to test logger level setting in service
        # Add any other settings attributes your service __init__ might access
    
    dummy_settings = DummySettings()
    service = PDFAcquisitionService(settings=dummy_settings)
    
    # --- Test Case 1: Valid PDF ---
    # Replace with a path to an actual PDF file for testing
    # For example: test_pdf_path = "path/to/your/test.pdf" 
    # Ensure the PDF exists at this path or the test will fail.
    test_pdf_path = r"E:\ThinkStash\ Embedding-Based Retrieval for Airbnb Search.pdf" # Using a raw string for Windows path

    if not os.path.exists(test_pdf_path):
        print(f"Test PDF not found at: {test_pdf_path}. Skipping test.")
        return

    print(f"Processing PDF: {test_pdf_path}")
    pdf_input = PDFAcquisitionServiceInput(file_path=test_pdf_path, job_id="testjob001")
    
    result = await service.execute(pdf_input)
    
    if result.success:
        print("\n--- Test Case 1: Success ---")
        prelim_blocks, doc_meta, raw_imgs = result.data
        print(f"Document Metadata: {doc_meta.model_dump_json(indent=2) if doc_meta else 'None'}")
        print(f"Number of Preliminary Blocks: {len(prelim_blocks)}")
        print(f"Number of Raw Images: {len(raw_imgs)}")
        
        # Print some details of the first few blocks and images
        for i, block in enumerate(prelim_blocks[:5]):
            print(f"  Block {i+1}: type={block.type}, order={block.order}, page={block.page_number}, bbox={block.bbox}")
            if block.type == "text" or block.type == "heading":
                print(f"    Text: '{block.text_content[:100]}...'")
            elif block.type == "image_placeholder":
                print(f"    Image ID Ref: {block.image_id_ref}")
        
        for i, img in enumerate(raw_imgs[:3]):
            print(f"  Image {i+1}: id={img.image_id}, page={img.page_number}, bbox={img.bbox}, filename={img.original_filename}, mime={img.mime_type}")
            print(f"    GCS Path Params: job_id={img.job_id_for_gcs_path}, source_id={img.original_source_identifier_for_gcs_path}, type={img.source_type_for_gcs_path}")

    else:
        print("\n--- Test Case 1: Failure ---")
        print(f"Error: {result.error_message}")
        if result.details:
            print(f"Details: {result.details}")

    # --- Test Case 2: File Not Found ---
    print("\n--- Test Case 2: File Not Found ---")
    non_existent_path = "path/to/non_existent_file.pdf"
    pdf_input_non_existent = PDFAcquisitionServiceInput(file_path=non_existent_path, job_id="testjob002")
    result_non_existent = await service.execute(pdf_input_non_existent)
    if not result_non_existent.success:
        print(f"Successfully handled non-existent file: {result_non_existent.error_message}")
    else:
        print("Test Case 2 failed: Expected failure for non-existent file.")

    # --- Test Case 3: Empty/Corrupted PDF (manual setup needed) ---
    # You would need to create an empty or corrupted PDF file and provide its path
    # empty_pdf_path = "path/to/your/empty_or_corrupt.pdf"
    # if os.path.exists(empty_pdf_path):
    #     print("\n--- Test Case 3: Empty/Corrupted PDF ---")
    #     pdf_input_empty = PDFAcquisitionServiceInput(file_path=empty_pdf_path, job_id="testjob003")
    #     result_empty = await service.execute(pdf_input_empty)
    #     if not result_empty.success and "empty or corrupted" in result_empty.error_message:
    #         print(f"Successfully handled empty/corrupted file: {result_empty.error_message}")
    #     else:
    #         print(f"Test Case 3 failed or was skipped. Result: {result_empty}")
    # else:
    #     print("\nSkipping Test Case 3: Empty/Corrupted PDF not found.")


if __name__ == "__main__":
    # Ensure an event loop is running if this script is executed directly
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError: # No event loop running
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(main_test_pdf_service())
