import asyncio
import os
import sys
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

from aiservice.app.config.settings import Settings
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock
from aiservice.app.models.pipeline_models import (
    PreliminaryBlock, DocumentMetadata, RawImageInput, EnrichedImageMetadata
)
from aiservice.app.services.routing_service import RoutingService, RoutingInput, RoutingOutput
from aiservice.app.services.base import ServiceResult
from aiservice.app.services.orchestrator import ParallelOrchestrator

# Mock Services (actual service classes for type hinting if needed, then mock instances)
from aiservice.app.services.routing_service import RoutingService
from aiservice.app.services.acquisition.web_service import WebAcquisitionService
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService
from aiservice.app.services.acquisition.file_service import FileAcquisitionService
from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService

# --- Mock Data Creation Helpers ---
def create_mock_preliminary_block(
    block_id: str, type: str, order: int, text_content: Optional[str] = None,
    image_id_ref: Optional[str] = None, # ... other fields as in previous test scripts
    page_number: int = 1
) -> PreliminaryBlock:
    return PreliminaryBlock(
        block_id=block_id, type=type, text_content=text_content, order=order,
        image_id_ref=image_id_ref, page_number=page_number, bbox=[0,0,1,1]
    )

def create_mock_document_metadata(
    doc_id: str, source_id: str, source_type: str, title: Optional[str] = "Mock Title",
    final_url: Optional[str] = None
) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=doc_id, source_identifier=source_id, source_type=source_type,
        title=title, final_url=final_url or source_id, extracted_at=datetime.utcnow()
    )

def create_mock_raw_image_input(image_id: str, original_filename: str = "mock_image.jpg") -> RawImageInput:
    return RawImageInput(
        image_id=image_id, image_bytes=b"mock_bytes", original_filename=original_filename,
        source_document_id="mock_doc_id", job_id_for_gcs_path="mock_job",
        source_type_for_gcs_path="url", original_source_identifier_for_gcs_path="mock_source_id"
    )

def create_mock_enriched_image_metadata(image_id: str, gcs_url: str = "gcs://mock/image.jpg") -> EnrichedImageMetadata:
    return EnrichedImageMetadata(
        image_id=image_id, gcs_url=gcs_url, alt_text="mock alt",
        original_source_identifier="mock_orig_src"
    )

def create_mock_content_block(block_id: str, type: str, content: Any) -> ContentBlock:
    if type == "heading":
        return ContentBlock(block_id=block_id, type=type, content=str(content), level=1)
    elif type == "list":
        return ContentBlock(block_id=block_id, type=type, items=[str(content)], ordered=False)
    return ContentBlock(block_id=block_id, type=type, content=str(content))

# --- Test Runner ---
async def run_orchestrator_test(
    test_name: str,
    orchestrator_input: OrchestrationInput,
    mock_routing_service: AsyncMock,
    mock_web_acquisition_service: AsyncMock,
    mock_pdf_acquisition_service: AsyncMock,
    mock_file_acquisition_service: AsyncMock,
    mock_image_processing_service: AsyncMock,
    mock_content_structuring_service: AsyncMock
):
    print(f"\n--- Running Orchestrator Test: {test_name} ---")
    settings = Settings() # Use default settings for the test
    orchestrator = ParallelOrchestrator(
        routing_service=mock_routing_service, # type: ignore
        web_acquisition_service=mock_web_acquisition_service, # type: ignore
        pdf_acquisition_service=mock_pdf_acquisition_service, # type: ignore
        file_acquisition_service=mock_file_acquisition_service, # type: ignore
        image_processing_service=mock_image_processing_service, # type: ignore
        content_structuring_service=mock_content_structuring_service, # type: ignore
        settings=settings
    )

    result: ServiceResult[OrchestrationOutput] = await orchestrator.process(orchestrator_input)

    if result.is_success():
        output = result.data
        print(f"  Status: Success (Code: {output.status_code})")
        print(f"  Source: {output.source_identifier}, Type: {output.source_type}, Title: {output.extracted_title}")
        print(f"  Content Blocks: {len(output.original_content_blocks) if output.original_content_blocks else 0}")
        if output.original_content_blocks:
            for cb in output.original_content_blocks:
                print(f"    - ID: {cb.block_id}, Type: {cb.type}")
        print(f"  Processed Images: {len(output.processed_images_data) if output.processed_images_data else 0}")
        if output.processed_images_data:
            for img_id, img_meta in output.processed_images_data.items():
                print(f"    - ID: {img_id}, GCS: {img_meta.gcs_url}")
        if output.document_metadata:
            print(f"  Document Metadata ID: {output.document_metadata.document_id}")
    else:
        print(f"  Status: Failed. Error: {result.error_message}")
        if result.error_details:
            print(f"    Details (Status Code from OrchestrationOutput): {result.error_details.get('status_code')}")
    print(f"--- Test Complete: {test_name} ---")
    return result

async def main():
    job_id_base = f"orch_test_{uuid.uuid4().hex[:6]}"

    # --- Mock Service Instances ---
    mock_routing = AsyncMock(spec=RoutingService)
    mock_web_acq = AsyncMock(spec=WebAcquisitionService)
    mock_pdf_acq = AsyncMock(spec=PDFAcquisitionService)
    mock_file_acq = AsyncMock(spec=FileAcquisitionService)
    mock_img_proc = AsyncMock(spec=ImageProcessingService)
    mock_struct = AsyncMock(spec=ContentStructuringService)

    # --- Test Case 1: Successful Web Workflow ---
    test_case_1_id = f"{job_id_base}_web_success"
    mock_routing.execute.return_value = ServiceResult.success(data=RoutingOutput(determined_service="WebAcquisitionService"))
    
    mock_web_doc_meta = create_mock_document_metadata(f"{test_case_1_id}_doc", "http://example.com", "url", "Example Title")
    mock_web_prelim_blocks = [create_mock_preliminary_block("p1", "text", 0, "Web content")]
    mock_web_raw_images = [create_mock_raw_image_input("web_img1")]
    mock_web_acq.execute.return_value = ServiceResult.success(data=(mock_web_prelim_blocks, mock_web_doc_meta, mock_web_raw_images))
    
    mock_enriched_images = [create_mock_enriched_image_metadata("web_img1")]
    mock_img_proc.execute.return_value = ServiceResult.success(data=mock_enriched_images)
    
    mock_content_blocks = [create_mock_content_block("cb1", "text", "Structured web content")]
    mock_struct.execute.return_value = ServiceResult.success(data=mock_content_blocks)

    input_1 = OrchestrationInput(source_identifier="http://example.com", job_id=test_case_1_id)
    await run_orchestrator_test("Successful Web Workflow", input_1, mock_routing, mock_web_acq, mock_pdf_acq, mock_file_acq, mock_img_proc, mock_struct)

    # --- Test Case 2: Routing Failure ---
    test_case_2_id = f"{job_id_base}_route_fail"
    mock_routing.execute.return_value = ServiceResult.failure(error_message="Could not determine route")
    input_2 = OrchestrationInput(source_identifier="ftp://example.com", job_id=test_case_2_id)
    await run_orchestrator_test("Routing Failure", input_2, mock_routing, mock_web_acq, mock_pdf_acq, mock_file_acq, mock_img_proc, mock_struct)

    # --- Test Case 3: Acquisition Failure (e.g., WebAcq fails) ---
    test_case_3_id = f"{job_id_base}_acq_fail"
    mock_routing.reset_mock()
    mock_web_acq.reset_mock()
    mock_routing.execute.return_value = ServiceResult.success(data=RoutingOutput(determined_service="WebAcquisitionService"))
    
    # Simulate WebAcquisitionService returning a failure with some DocumentMetadata in error_details
    failed_acq_doc_meta = create_mock_document_metadata(f"{test_case_3_id}_doc_fail", "http://failing-url.com", "url", "Failed Page")
    failed_acq_error_details = {
        "original_data": ([], failed_acq_doc_meta, []),
        "reason": "404 Not Found"
    }
    mock_web_acq.execute.return_value = ServiceResult.failure(error_message="Page not found", error_details=failed_acq_error_details)
    
    input_3 = OrchestrationInput(source_identifier="http://failing-url.com", job_id=test_case_3_id)
    await run_orchestrator_test("Acquisition Failure", input_3, mock_routing, mock_web_acq, mock_pdf_acq, mock_file_acq, mock_img_proc, mock_struct)

    # --- Test Case 4: Image Processing Failure (Partial Success) ---
    test_case_4_id = f"{job_id_base}_img_fail"
    mock_routing.reset_mock()
    mock_web_acq.reset_mock()
    mock_img_proc.reset_mock()
    mock_struct.reset_mock()

    mock_routing.execute.return_value = ServiceResult.success(data=RoutingOutput(determined_service="WebAcquisitionService"))
    # Successful acquisition (reusing mock_web_prelim_blocks, mock_web_doc_meta, mock_web_raw_images from Case 1 setup for brevity)
    mock_web_acq.execute.return_value = ServiceResult.success(data=(mock_web_prelim_blocks, mock_web_doc_meta, mock_web_raw_images))
    # Image processing fails
    mock_img_proc.execute.return_value = ServiceResult.failure(error_message="Unsupported image format")
    # Structuring should still run with no enriched images
    mock_struct.execute.return_value = ServiceResult.success(data=[create_mock_content_block("cb_no_img", "text", "Content without image data")])

    input_4 = OrchestrationInput(source_identifier="http://example.com/page_with_bad_image", job_id=test_case_4_id)
    # EXPECT partial_success_image_processing_failed in OrchestrationOutput.status_code
    result_case_4 = await run_orchestrator_test("Image Processing Failure", input_4, mock_routing, mock_web_acq, mock_pdf_acq, mock_file_acq, mock_img_proc, mock_struct)
    assert result_case_4.is_success() # The ServiceResult itself is success for partial
    assert result_case_4.data.status_code == "partial_success_image_processing_failed"
    assert result_case_4.data.error_message == "ImageProcessingService failed: Unsupported image format"

    # --- Test Case 5: Structuring Failure ---
    test_case_5_id = f"{job_id_base}_struct_fail"
    mock_routing.reset_mock()
    mock_web_acq.reset_mock()
    mock_img_proc.reset_mock()
    mock_struct.reset_mock()

    mock_routing.execute.return_value = ServiceResult.success(data=RoutingOutput(determined_service="WebAcquisitionService"))
    mock_web_acq.execute.return_value = ServiceResult.success(data=(mock_web_prelim_blocks, mock_web_doc_meta, mock_web_raw_images))
    mock_img_proc.execute.return_value = ServiceResult.success(data=mock_enriched_images) # Image processing success
    mock_struct.execute.return_value = ServiceResult.failure(error_message="Cannot structure content") # Structuring fails

    input_5 = OrchestrationInput(source_identifier="http://example.com/unstructurable", job_id=test_case_5_id)
    await run_orchestrator_test("Structuring Failure", input_5, mock_routing, mock_web_acq, mock_pdf_acq, mock_file_acq, mock_img_proc, mock_struct)

    # --- Test Case 6: Successful PDF Workflow (Direct Route) ---
    test_case_6_id = f"{job_id_base}_pdf_direct"
    mock_routing.execute.return_value = ServiceResult.success(data=RoutingOutput(determined_service="PDFAcquisitionService"))
    
    mock_pdf_doc_meta = create_mock_document_metadata(f"{test_case_6_id}_doc", "local/file.pdf", "pdf", "PDF Title")
    mock_pdf_prelim_blocks = [create_mock_preliminary_block("pdf_p1", "text", 0, "PDF content")]
    mock_pdf_raw_images = [] # No images in this PDF example
    mock_pdf_acq.execute.return_value = ServiceResult.success(data=(mock_pdf_prelim_blocks, mock_pdf_doc_meta, mock_pdf_raw_images))
    
    mock_img_proc.execute.return_value = ServiceResult.success(data=[]) # No images to process
    
    mock_pdf_content_blocks = [create_mock_content_block("pdf_cb1", "text", "Structured PDF content")]
    mock_struct.execute.return_value = ServiceResult.success(data=mock_pdf_content_blocks)

    input_6 = OrchestrationInput(source_identifier="local/file.pdf", source_type="pdf", job_id=test_case_6_id)
    await run_orchestrator_test("Successful PDF Workflow (Direct)", input_6, mock_routing, mock_web_acq, mock_pdf_acq, mock_file_acq, mock_img_proc, mock_struct)

    # --- Test Case 7: Successful File Workflow (TXT) ---
    test_case_7_id = f"{job_id_base}_file_txt_success"
    mock_routing.reset_mock()
    mock_file_acq.reset_mock()
    mock_img_proc.reset_mock()
    mock_struct.reset_mock()

    mock_routing.execute.return_value = ServiceResult.success(data=RoutingOutput(determined_service="FileAcquisitionService"))
    
    mock_txt_doc_meta = create_mock_document_metadata(f"{test_case_7_id}_doc", "local/test.txt", "txt", "TXT File Title")
    mock_txt_prelim_blocks = [create_mock_preliminary_block("txt_p1", "text", 0, "Text file content.")]
    mock_txt_raw_images = [] # TXT files typically don't have images from basic parsing
    mock_file_acq.execute.return_value = ServiceResult.success(data=(mock_txt_prelim_blocks, mock_txt_doc_meta, mock_txt_raw_images))
    
    mock_img_proc.execute.return_value = ServiceResult.success(data=[]) # No images to process
    
    mock_txt_content_blocks = [create_mock_content_block("txt_cb1", "text", "Structured TXT content")]
    mock_struct.execute.return_value = ServiceResult.success(data=mock_txt_content_blocks)

    input_7 = OrchestrationInput(source_identifier="local/test.txt", source_type="txt", job_id=test_case_7_id)
    await run_orchestrator_test("Successful File Workflow (TXT)", input_7, mock_routing, mock_web_acq, mock_pdf_acq, mock_file_acq, mock_img_proc, mock_struct)

    # --- Test Case 8: Web to PDF Redirection ---
    # This tests that if WebAcquisitionService returns data indicative of a PDF processed internally,
    # the orchestrator handles it correctly (it should be transparent now)
    test_case_8_id = f"{job_id_base}_web_to_pdf"
    mock_routing.reset_mock()
    mock_web_acq.reset_mock() # This is the key service to mock for this scenario
    mock_img_proc.reset_mock()
    mock_struct.reset_mock()

    mock_routing.execute.return_value = ServiceResult.success(data=RoutingOutput(determined_service="WebAcquisitionService"))
    
    # WebAcquisitionService internally processes a PDF and returns this standard tuple:
    mock_redirected_pdf_doc_meta = create_mock_document_metadata(f"{test_case_8_id}_doc", "http://example.com/is_actually_a.pdf", "pdf", "Redirected PDF Title")
    mock_redirected_pdf_prelim_blocks = [create_mock_preliminary_block("redir_pdf_p1", "text", 0, "Content from a PDF found at a URL")]
    mock_redirected_pdf_raw_images = [create_mock_raw_image_input("redir_pdf_img1")]
    mock_web_acq.execute.return_value = ServiceResult.success(data=(mock_redirected_pdf_prelim_blocks, mock_redirected_pdf_doc_meta, mock_redirected_pdf_raw_images))
    
    # Image processing for the image found in the redirected PDF
    mock_enriched_redirected_images = [create_mock_enriched_image_metadata("redir_pdf_img1")]
    mock_img_proc.execute.return_value = ServiceResult.success(data=mock_enriched_redirected_images)
    
    mock_redirected_pdf_content_blocks = [create_mock_content_block("redir_pdf_cb1", "text", "Structured content from redirected PDF")]
    mock_struct.execute.return_value = ServiceResult.success(data=mock_redirected_pdf_content_blocks)

    input_8 = OrchestrationInput(source_identifier="http://example.com/is_actually_a.pdf", job_id=test_case_8_id)
    result_case_8 = await run_orchestrator_test("Web to PDF Redirection", input_8, mock_routing, mock_web_acq, mock_pdf_acq, mock_file_acq, mock_img_proc, mock_struct)
    assert result_case_8.is_success()
    assert result_case_8.data.status_code == "success"
    assert result_case_8.data.source_type == "pdf" # Important: source_type should be updated by DocumentMetadata
    assert result_case_8.data.extracted_title == "Redirected PDF Title"
    assert len(result_case_8.data.original_content_blocks) == 1
    assert len(result_case_8.data.processed_images_data) == 1

    # TODO: Add more test cases:
    # - Successful File Workflow (e.g., DOCX with images)
    # - Edge cases (e.g., no images from acquisition, but structuring still works)

if __name__ == "__main__":
    asyncio.run(main()) 