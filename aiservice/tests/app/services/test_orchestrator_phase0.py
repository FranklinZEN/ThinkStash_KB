import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, ANY
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Adjust sys.path to include the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from aiservice.app.services.orchestrator import ParallelOrchestrator
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock, DocumentMetadata
from aiservice.app.models.pipeline_models import RawImageInput, EnrichedImageMetadata
from aiservice.app.models.image_processing_models import ImageProcessingServiceInput as IPS_Input_Model_Orch_Test
from aiservice.app.services.base import ServiceResult
from aiservice.app.config.settings import Settings

# For this example, let's assume simple structures for mock acquisition outputs
# Removed the MockProcessedPDFImage class, will use a dictionary instead.

class MockPDFAcquisitionServiceOutput:
    def __init__(self, images, status="success", extracted_text="pdf text", page_title="pdf title"):
        self.images = images
        self.status = status
        self.extracted_text = extracted_text
        self.page_title = page_title
        # Add other fields as per actual PDFAcquisitionServiceOutput

@pytest.mark.asyncio
async def test_orchestrator_map_pdf_images_to_raw_input():
    mock_settings = Settings() # Fill with necessary defaults
    
    mock_routing_service = AsyncMock()
    mock_pdf_acq_service = AsyncMock()
    mock_img_proc_service = AsyncMock()
    mock_file_acq_service = AsyncMock()
    mock_web_acq_service = AsyncMock()
    mock_structuring_service = AsyncMock()

    # Mock Routing output
    routing_data_mock = MagicMock()
    routing_data_mock.determined_service = "PDFAcquisitionService"
    mock_routing_service.execute.return_value = ServiceResult.success(data=routing_data_mock)

    # Mock PDF Acquisition output - USE A DICTIONARY for the image
    pdf_image1 = {
        "image_id": "pdf_img_1",
        "image_bytes": b"bytes1",
        "page_number": 1,
        "bbox": [0,0,1,1],
        "alt_text": "alt1",
        "mime_type": "image/jpeg",
        "original_filename": "page1.jpg",
        "source_document_id": "test.pdf",
        "original_source_identifier_for_gcs_path": "test.pdf",
        "source_type_for_gcs_path": "pdf",
        "job_id_for_gcs_path": "test_job_id"
    }
    # This now provides a list of dictionaries, which can be parsed into RawImageInput
    raw_images_from_acq = [RawImageInput(**pdf_image1)]

    mock_doc_meta = DocumentMetadata(
        document_id='test.pdf', 
        user_id='test_user', 
        source_identifier='test.pdf', 
        source_type='pdf',
        extracted_at=datetime.utcnow()
    )
    # The acquisition service result tuple is (preliminary_blocks, doc_metadata, raw_images)
    pdf_acq_output_data = ([], mock_doc_meta, raw_images_from_acq)
    mock_pdf_acq_service.execute.return_value = ServiceResult.success(data=pdf_acq_output_data)

    # Mock Image Processing Service to just return success with no images for this mapping test
    mock_img_proc_service.execute.return_value = ServiceResult.success(data=[])

    # Mock Structuring Service
    mock_structuring_data = MagicMock()
    mock_structuring_data.structured_content_blocks = [
        ContentBlock(
            block_id="b1", 
            type="text", 
            content="text",
            user_id="test_user",
            document_id="test.pdf"
        )
    ]
    mock_structuring_data.extracted_title = "title"
    mock_structuring_service.execute.return_value = ServiceResult.success(data=mock_structuring_data)


    orchestrator = ParallelOrchestrator(
        routing_service=mock_routing_service,
        web_acquisition_service=mock_web_acq_service,
        pdf_acquisition_service=mock_pdf_acq_service,
        file_acquisition_service=mock_file_acq_service,
        image_processing_service=mock_img_proc_service,
        content_structuring_service=mock_structuring_service,
        settings=mock_settings
    )

    orch_input = OrchestrationInput(source_identifier="test.pdf", source_type="pdf", user_id="test_user")
    await orchestrator.process(orch_input)

    mock_img_proc_service.execute.assert_called_once()
    call_args = mock_img_proc_service.execute.call_args
    passed_ips_input: IPS_Input_Model_Orch_Test = call_args[0][0]
    
    assert len(passed_ips_input.images_to_process) == 1
    mapped_raw_image: RawImageInput = passed_ips_input.images_to_process[0]

    assert mapped_raw_image.image_id == "pdf_img_1"
    assert mapped_raw_image.image_bytes == b"bytes1"
    assert mapped_raw_image.source_document_id == "test.pdf"
    assert mapped_raw_image.original_filename == "page1.jpg"
    assert mapped_raw_image.page_number == 1
    assert mapped_raw_image.bbox == [0,0,1,1]
    assert mapped_raw_image.mime_type == "image/jpeg"
    assert mapped_raw_image.alt_text == "alt1"
    assert mapped_raw_image.source_type_for_gcs_path == "pdf"
    assert mapped_raw_image.original_source_identifier_for_gcs_path == "test.pdf"
    assert mapped_raw_image.job_id_for_gcs_path is not None # Should be populated by orchestrator 