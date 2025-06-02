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
import tempfile # Added for temporary file handling for GCS downloads
from google.cloud import storage # Added for GCS interaction
from urllib.parse import urlparse # Added for parsing GCS paths

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput

# --- Pydantic Models for PDFAcquisitionService ---

class PDFAcquisitionServiceInput(BaseModel):
    file_path: str = Field(..., description="Path to the PDF file (local or gs://) to process.")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking.")
    user_id: Optional[str] = None # Added user_id

class PDFAcquisitionService(BaseService):
    """
    Asynchronous service to extract text and image placeholders from PDF files,
    producing PreliminaryBlock, DocumentMetadata, and RawImageInput objects.
    Can handle local file paths or gs:// GCS paths.
    """
    GCS_PREFIX = "gs://"

    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        self.settings = settings 
        self.logger = logging.getLogger(__name__)
        if self.settings and hasattr(self.settings, 'debug_mode') and self.settings.debug_mode:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        
        try:
            self.gcs_storage_client = storage.Client()
            self.logger.info("GCS Storage client initialized successfully.")
        except Exception as e_gcs_init:
            self.gcs_storage_client = None # Ensure it's None if init fails
            self.logger.error(f"Failed to initialize GCS Storage client: {e_gcs_init}. GCS downloads will fail.")

    async def _download_gcs_file(self, gcs_path: str) -> Tuple[Optional[str], Optional[str]]:
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
            
            # Create a temporary file to download to
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file_path = temp_file.name
            temp_file.close() # Close the file handle so blob.download_to_filename can use it

            await asyncio.get_event_loop().run_in_executor(None, blob.download_to_filename, temp_file_path)
            self.logger.info(f"Successfully downloaded {gcs_path} to {temp_file_path}")
            return temp_file_path, None
        except Exception as e:
            self.logger.error(f"Error downloading {gcs_path} from GCS: {e}")
            # Clean up temp file if created before error
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e_unlink:
                    self.logger.error(f"Failed to cleanup temp file {temp_file_path} after GCS download error: {e_unlink}")
            return None, str(e)

    async def execute(self, pdf_input: PDFAcquisitionServiceInput) -> ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]:
        start_time = time.time()
        job_id = pdf_input.job_id or uuid.uuid4().hex[:8]
        
        original_file_path = pdf_input.file_path
        processing_file_path = original_file_path
        is_gcs_source = original_file_path.startswith(self.GCS_PREFIX)
        temp_gcs_file_path: Optional[str] = None

        preliminary_blocks: List[PreliminaryBlock] = []
        raw_images: List[RawImageInput] = []
        document_metadata: Optional[DocumentMetadata] = None
        doc: Optional[fitz.Document] = None
        loop = asyncio.get_event_loop()

        try:
            if is_gcs_source:
                if not self.gcs_storage_client:
                    return ServiceResult.failure(error_message="GCS client not initialized. Cannot process GCS path.")
                self.logger.info(f"Processing GCS PDF: {original_file_path}")
                temp_gcs_file_path, download_error = await self._download_gcs_file(original_file_path)
                if download_error or not temp_gcs_file_path:
                    return ServiceResult.failure(error_message=f"Failed to download GCS file {original_file_path}: {download_error}")
                processing_file_path = temp_gcs_file_path
            
            pdf_filename = os.path.basename(original_file_path) # Use original path for filename

            if not os.path.exists(processing_file_path):
                return ServiceResult.failure(
                    error_message=f"File not found: {processing_file_path} (original: {original_file_path})"
                )

            doc = await loop.run_in_executor(None, fitz.open, processing_file_path)
            
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
                user_id=pdf_input.user_id or "unknown_user_pdf_service",
                source_identifier=original_file_path, # Always use the original path here
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
                        base_image_info = await loop.run_in_executor(None, doc.extract_image, xref)
                        if not base_image_info or not base_image_info.get("image") or not base_image_info.get("ext"):
                            self.logger.warning(f"PDFAcquisitionService: Skipping image with xref {xref} on page {page_num+1} due to missing data.")
                            continue

                        image_bytes = base_image_info["image"]
                        image_ext = base_image_info["ext"]
                        # Find bounding box of the image on the page
                        get_image_rects_func = functools.partial(page.get_image_rects, xref, transform=False)
                        image_rects = await loop.run_in_executor(None, get_image_rects_func)
                        img_bbox = list(image_rects[0].irect) if image_rects and image_rects[0].irect else [0,0,0,0] # (x0,y0,x1,y1)
                        
                        image_id = f"{job_id}_p{page_num+1}_img{img_idx}_{xref}"
                        prelim_block = PreliminaryBlock(
                            block_id=image_id,
                            type="image_placeholder",
                            page_number=page_num+1,
                            bbox=img_bbox,
                            order=-1, # Will be set later
                            image_id_ref=image_id # Corrected from image_data_ref
                        )
                        preliminary_blocks.append(prelim_block)
                        raw_images.append(RawImageInput(
                            image_id=image_id,
                            image_bytes=image_bytes,
                            original_filename=f"page{page_num+1}_img{img_idx}.{image_ext}",
                            mime_type=f"image/{image_ext}",
                            source_document_id=document_metadata.document_id, 
                            page_number=page_num+1,
                            bbox=img_bbox,
                            original_source_identifier_for_gcs_path=original_file_path,
                            source_type_for_gcs_path=document_metadata.source_type, 
                            job_id_for_gcs_path=job_id 
                        ))

            # Sorting all blocks by page number and then by vertical position (y0 of bbox)
            def sort_key(block: PreliminaryBlock):
                y_coord = block.bbox[1] if block.bbox and len(block.bbox) > 1 else 0
                x_coord = block.bbox[0] if block.bbox and len(block.bbox) > 0 else 0
                return (block.page_number, y_coord, x_coord)

            preliminary_blocks.sort(key=sort_key)
            for i, block in enumerate(preliminary_blocks):
                block.order = i

            duration_ms = (time.time() - start_time) * 1000
            self.logger.info(f"PDFAcquisitionService for '{original_file_path}' completed in {duration_ms:.2f} ms. Blocks: {len(preliminary_blocks)}, Images: {len(raw_images)}.")
            if document_metadata:
                return ServiceResult.success(data=(preliminary_blocks, document_metadata, raw_images))
            else:
                # This case should ideally not be reached if DocumentMetadata is always created.
                return ServiceResult.failure(error_message="Document metadata could not be created.")

        except FileNotFoundError:
            return ServiceResult.failure(error_message=f"File not found: {processing_file_path}")
        except RuntimeError as e_runtime: # Catching RuntimeError which PyMuPDF commonly raises
            self.logger.error(f"PyMuPDF RuntimeError in PDFAcquisitionService for {processing_file_path} (original: {original_file_path}): {e_runtime}", exc_info=True)
            error_details = {"original_data": ([], document_metadata if document_metadata else None, [])}
            return ServiceResult.failure(error_message=f"PDFAcquisitionService runtime error: {e_runtime}", error_details=error_details)
        except Exception as e:
            self.logger.error(f"Unexpected error in PDFAcquisitionService for {processing_file_path} (original: {original_file_path}): {e}", exc_info=True)
            # Pass document_metadata in error_details if it was created
            error_details = {"original_data": ([], document_metadata if document_metadata else None, [])}
            return ServiceResult.failure(error_message=f"PDFAcquisitionService unexpected error: {e}", error_details=error_details)
        finally:
            if doc:
                try:
                    await loop.run_in_executor(None, doc.close)
                except Exception as e_close:
                    self.logger.error(f"Error closing PDF document {processing_file_path}: {e_close}")
            if temp_gcs_file_path and os.path.exists(temp_gcs_file_path):
                try:
                    # Run os.unlink in an executor if it might block, or keep it sync if it's quick
                    await loop.run_in_executor(None, os.unlink, temp_gcs_file_path)
                    self.logger.info(f"Successfully deleted temporary GCS file: {temp_gcs_file_path}")
                except Exception as e_unlink:
                    self.logger.error(f"Failed to delete temporary GCS file {temp_gcs_file_path}: {e_unlink}")

# --- Example Usage / Testing ---
async def main_test_pdf_service():
    # Basic test setup (replace with actual testing framework)
    # Configure basic logging for the test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger_main = logging.getLogger("main_test")

    # Example: Create dummy settings if your service uses them for configuration
    class DummySettings:
        debug_mode = True # Or False, to test logger level setting in service
        # Add other settings PDFAcquisitionService might expect, if any

    settings_instance = DummySettings() # type: ignore
    pdf_service = PDFAcquisitionService(settings=settings_instance)

    # --- Test Case 1: Local PDF file ---
    # Create a dummy PDF file for testing
    dummy_pdf_path = "dummy_test.pdf"
    try:
        doc_test = fitz.open() # Create a new PDF
        page_test = doc_test.new_page()
        page_test.insert_text((50, 72), "Hello, PyMuPDF! This is a test.")
        # Add a small image to test image extraction (optional)
        # pix = fitz.Pixmap(fitz.csGRAY, (0, 0, 10, 10), 0) # Small 10x10 black square
        # page_test.insert_image(page_test.rect, pixmap=pix)
        doc_test.save(dummy_pdf_path)
        doc_test.close()
        logger_main.info(f"Created dummy PDF: {dummy_pdf_path}")

        pdf_input_local = PDFAcquisitionServiceInput(file_path=dummy_pdf_path, job_id="local_pdf_test_001", user_id="test_user_local")
        result_local = await pdf_service.execute(pdf_input_local)

        if result_local.is_success() and result_local.data:
            blocks, metadata, images = result_local.data
            logger_main.info(f"Local PDF Test SUCCEEDED. Blocks: {len(blocks)}, Title: {metadata.title}, Images: {len(images)}")
            # for i, block in enumerate(blocks):
            #     logger_main.info(f"  Block {i}: Type={block.type}, Order={block.order}, Page={block.page_number}, Text/Ref='{block.text_content if block.text_content else block.image_data_ref}'")
        else:
            logger_main.error(f"Local PDF Test FAILED: {result_local.error_message}")
            if result_local.error_details:
                 logger_main.error(f"Error details: {result_local.error_details}")

    except Exception as e_test:
        logger_main.error(f"Error in local PDF test setup or execution: {e_test}")
    finally:
        if os.path.exists(dummy_pdf_path):
            os.remove(dummy_pdf_path)
            logger_main.info(f"Cleaned up dummy PDF: {dummy_pdf_path}")
    
    # --- Test Case 2: GCS PDF file (requires GCS setup and a file in a bucket) ---
    # Note: This test will only run if GCS client initialized successfully in PDFAcquisitionService
    # and if you have a GCS bucket and PDF file accessible.
    # Replace with your actual GCS path for testing.
    # GCS_TEST_PDF_PATH = "gs://your-gcs-bucket-name/path/to/your-test-file.pdf"
    # if pdf_service.gcs_storage_client and GCS_TEST_PDF_PATH != "gs://your-gcs-bucket-name/path/to/your-test-file.pdf":
    #     logger_main.info(f"\nAttempting GCS PDF Test with: {GCS_TEST_PDF_PATH}")
    #     pdf_input_gcs = PDFAcquisitionServiceInput(file_path=GCS_TEST_PDF_PATH, job_id="gcs_pdf_test_001", user_id="test_user_gcs")
    #     result_gcs = await pdf_service.execute(pdf_input_gcs)
        
    #     if result_gcs.is_success() and result_gcs.data:
    #         blocks_gcs, metadata_gcs, images_gcs = result_gcs.data
    #         logger_main.info(f"GCS PDF Test SUCCEEDED. Blocks: {len(blocks_gcs)}, Title: {metadata_gcs.title}, Images: {len(images_gcs)}")
    #     else:
    #         logger_main.error(f"GCS PDF Test FAILED: {result_gcs.error_message}")
    #         if result_gcs.error_details:
    #             logger_main.error(f"GCS Error details: {result_gcs.error_details}")
    # else:
    #     logger_main.warning("\nSkipping GCS PDF Test: GCS client not available in service or GCS_TEST_PDF_PATH not set.")

if __name__ == "__main__":
    asyncio.run(main_test_pdf_service()) 
