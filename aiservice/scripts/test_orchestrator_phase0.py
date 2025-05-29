# aiservice/tests/scripts/test_ips_plain.py
import sys
import os

# Add the project root directory (E:\ThinkStash) to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# aiservice/tests/services/test_orchestrator.py
import pytest
from unittest.mock import AsyncMock, MagicMock, ANY # ANY can be used for job_id

from aiservice.app.services.orchestrator import ParallelOrchestrator
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock
from aiservice.app.models.pipeline_models import RawImageInput, EnrichedImageMetadata # For type hints and asserts
from aiservice.app.models.image_processing_models import ImageProcessingServiceInput as IPS_Input_Model_Orch_Test
from aiservice.app.services.base import ServiceResult
from aiservice.app.config.settings import Settings

# --- Mock Acquisition Output Models (simplified, use actual definitions) ---
# You'll need to import or define mocks for:
# PDFAcquisitionServiceOutput, ProcessedPDFImage, 
# WebAcquisitionServiceOutput, ProcessedWebImage,
# FileAcquisitionServiceOutput, ProcessedFileImage
# from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionServiceOutput, ProcessedPDFImage (etc.)

# For this example, let's assume simple structures for mock acquisition outputs
class MockProcessedPDFImage:
    def __init__(self, image_id, image_bytes, page_number=None, bbox=None, alt_text=None, mime_type=None, original_filename=None):
        self.image_id = image_id
        self.image_bytes = image_bytes
        self.page_number = page_number
        self.bbox = bbox
        self.alt_text = alt_text
        self.mime_type = mime_type
        self.original_filename = original_filename
        self.caption = None # Add other fields as needed

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
    mock_img_proc_service = AsyncMock() # Key: We'll check what's passed to this
    mock_file_acq_service = AsyncMock()
    mock_web_acq_service = AsyncMock()
    mock_structuring_service = AsyncMock()

    # Mock Routing output
    routing_data_mock = MagicMock()
    routing_data_mock.determined_service = "PDFAcquisitionService"
    mock_routing_service.execute.return_value = ServiceResult.success(data=routing_data_mock)

    # Mock PDF Acquisition output
    pdf_image1 = MockProcessedPDFImage(
        image_id="pdf_img_1", 
        image_bytes=b"bytes1", 
        page_number=1, 
        bbox=[0,0,1,1], 
        alt_text="alt1",
        mime_type="image/jpeg",
        original_filename="page1.jpg"
    )
    pdf_acq_output_data = MockPDFAcquisitionServiceOutput(images=[pdf_image1])
    mock_pdf_acq_service.execute.return_value = ServiceResult.success(data=pdf_acq_output_data)

    # Mock Image Processing Service to just return success with no images for this mapping test
    mock_img_proc_service.execute.return_value = ServiceResult.success(data=[])

    # Mock Structuring Service
    mock_structuring_data = MagicMock()
    mock_structuring_data.structured_content_blocks = [ContentBlock(block_id="b1", type="text", content="text")]
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

    orch_input = OrchestrationInput(source_identifier="test.pdf", source_type="pdf")
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