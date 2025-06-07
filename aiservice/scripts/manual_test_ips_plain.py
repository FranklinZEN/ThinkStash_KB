# aiservice/tests/scripts/test_ips_plain.py
import sys
import os

# Add the project root directory (E:\ThinkStash) to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch # unittest.mock is standard

from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.models.pipeline_models import RawImageInput, EnrichedImageMetadata
from aiservice.app.models.image_processing_models import ImageProcessingServiceInput
from aiservice.app.services.base import ServiceResult
from aiservice.app.config.settings import Settings # Assuming default instantiation works or provide values

VALID_1X1_PNG_BYTES = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

def create_mock_raw_image(image_id: str, has_bytes: bool, has_url: bool) -> RawImageInput:
    # ... (same as pytest example) ...
    return RawImageInput(
        image_id=image_id,
        image_bytes=VALID_1X1_PNG_BYTES if has_bytes else None,
        source_url="http://example.com/fake_image.png" if has_url else None,
        original_filename=f"{image_id}.png",
        source_document_id="test_doc_ips",
        page_number=1,
        bbox=[0.1, 0.1, 0.2, 0.2],
        mime_type="image/png" if has_bytes or not has_url else None,
        alt_text=f"Alt for {image_id}",
        caption=f"Caption for {image_id}",
        original_source_identifier_for_gcs_path="doc_gcs_id_ips",
        source_type_for_gcs_path="test_source",
        job_id_for_gcs_path="job_ips_123"
    )

async def test_ips_process_image_with_bytes_no_gcs_no_llm():
    print("Testing IPS with bytes, no GCS, no LLM...")
    mock_settings = Settings(use_llm_for_image_analysis=False, gcs_bucket_name=None)
    service = ImageProcessingService(settings=mock_settings, image_analysis_tool=None)
    
    raw_image = create_mock_raw_image("img_bytes_1", has_bytes=True, has_url=False)
    service_input = ImageProcessingServiceInput(images_to_process=[raw_image])

    result: ServiceResult[List[EnrichedImageMetadata]] = await service.execute(service_input)

    assert result.status == "success", f"Expected success, got {result.status}"
    assert result.data is not None, "Result data should not be None"
    assert len(result.data) == 1, f"Expected 1 metadata object, got {len(result.data)}"
    
    meta = result.data[0]
    assert meta.image_id == "img_bytes_1"
    assert meta.width == 1
    print("IPS with bytes, no GCS, no LLM OK.")

async def test_ips_process_image_with_url_no_gcs_no_llm():
    print("Testing IPS with URL, no GCS, no LLM...")
    # Patching with unittest.mock.patch as a context manager
    with patch('aiohttp.ClientSession.get') as mock_aiohttp_get:
        # Configure the mock for aiohttp response
        mock_response = AsyncMock()
        mock_response.read.return_value = VALID_1X1_PNG_BYTES
        mock_response.raise_for_status = MagicMock()
        
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.return_value = mock_response
        mock_aiohttp_get.return_value = mock_session_context

        mock_settings = Settings(use_llm_for_image_analysis=False, gcs_bucket_name=None)
        service = ImageProcessingService(settings=mock_settings, image_analysis_tool=None)
        
        raw_image = create_mock_raw_image("img_url_1", has_bytes=False, has_url=True)
        service_input = ImageProcessingServiceInput(images_to_process=[raw_image])

        result: ServiceResult[List[EnrichedImageMetadata]] = await service.execute(service_input)
        
        mock_aiohttp_get.assert_called_once_with(raw_image.source_url)
        assert result.status == "success"
        assert len(result.data) == 1
        meta = result.data[0]
        assert meta.image_id == "img_url_1"
        assert meta.width == 1
        print("IPS with URL, no GCS, no LLM OK.")

async def main():
    print("--- Running ImageProcessingService Tests (Plain Python) ---")
    try:
        await test_ips_process_image_with_bytes_no_gcs_no_llm()
        await test_ips_process_image_with_url_no_gcs_no_llm()
        # ... call other async test functions ...
        print("--- All ImageProcessingService Tests Passed ---")
    except AssertionError as e:
        print(f"!!! Assertion Failed: {e} !!!")
    except Exception as e:
        print(f"!!! An unexpected error occurred: {e} !!!")


if __name__ == "__main__":
    asyncio.run(main())