import pytest
import asyncio
from typing import List, Tuple, Optional, Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch

from pydantic import BaseModel
import httpx

from aiservice.app.config.settings import Settings, WebServiceSpecificSettings
from aiservice.app.services.acquisition.web_service import WebAcquisitionService, WebAcquisitionServiceInput
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput, BaseMetadata

# --- Test Fixtures and Mocks ---

@pytest.fixture
def mock_settings() -> Settings:
    """Fixture to create a mock Settings object for tests."""
    settings = Settings()
    # You can override specific settings for tests here if needed
    # For example:
    settings.web_service = WebServiceSpecificSettings(
        use_playwright_for_image_filtering=False, # Disable for most unit tests for speed
        min_image_width=50,
        min_image_height=50,
        min_image_area=2500,
        # Set other web_service specific settings if necessary
    )
    settings.default_request_timeout_seconds = 5
    return settings

@pytest.fixture
def web_acquisition_service(mock_settings: Settings) -> WebAcquisitionService:
    """Fixture to create an instance of the WebAcquisitionService."""
    return WebAcquisitionService(settings=mock_settings)

# A more advanced mock for httpx responses
class MockHttpxResponse:
    def __init__(self, status_code: int, html_content: str, url: str):
        self.status_code = status_code
        self.html_content = html_content
        self._url = url

    @property
    def url(self) -> str:
        return self._url
    
    @property
    def headers(self) -> Dict[str, str]:
        return {'content-type': 'text/html; charset=utf-8'}

    async def aread(self) -> bytes:
        return self.html_content.encode('utf-8')

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(message="Error", request=MagicMock(), response=self)

# --- Test Cases ---

@pytest.mark.asyncio
async def test_service_instantiation(web_acquisition_service: WebAcquisitionService):
    """
    Tests if the WebAcquisitionService can be instantiated correctly.
    """
    assert web_acquisition_service is not None
    assert isinstance(web_acquisition_service, WebAcquisitionService)
    assert web_acquisition_service.settings is not None
    assert web_acquisition_service.service_settings.use_playwright_for_image_filtering is False


@pytest.mark.asyncio
async def test_simple_html_extraction(web_acquisition_service: WebAcquisitionService):
    """
    Tests basic content extraction from a simple HTML string.
    Mocks the httpx call to avoid actual network requests.
    """
    test_url = "http://example.com/test-article"
    test_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Title</title></head>
    <body>
        <main>
            <h1>Main Heading</h1>
            <p>This is the first paragraph of text.</p>
            <p>This is the second.</p>
            <img src="/images/test_image.jpg" alt="A test image">
        </main>
    </body>
    </html>
    """
    
    mock_response = MockHttpxResponse(status_code=200, html_content=test_html, url=test_url)

    # Patch the AsyncClient context manager
    with patch('httpx.AsyncClient', new_callable=AsyncMock) as mock_async_client:
        # Configure the __aenter__ method's return value (the client instance)
        mock_client_instance = mock_async_client.return_value.__aenter__.return_value
        # Configure the get method on that instance to return our mock response
        mock_client_instance.get.return_value = mock_response

        service_input = WebAcquisitionServiceInput(url=test_url, job_id="test_job_01", user_id="test_user")
        result = await web_acquisition_service.execute(service_input)

        # Assertions
        assert result.is_success()
        assert result.data is not None
        
        blocks, metadata, images = result.data
        
        assert isinstance(blocks, list)
        assert isinstance(metadata, DocumentMetadata)
        assert isinstance(images, list)
        
        # Check Metadata
        assert metadata.title == "Test Title"
        assert metadata.source_identifier == test_url
        assert metadata.final_url == test_url
        
        # Check Blocks (Trafilatura can be complex, so we check for key content)
        assert len(blocks) > 0, "No blocks were extracted"
        
        # Find heading
        heading_block = next((b for b in blocks if b.type == 'heading'), None)
        assert heading_block is not None
        assert "Main Heading" in heading_block.text_content

        # Find text
        text_content_full = " ".join(b.text_content for b in blocks if b.type == 'text')
        assert "first paragraph" in text_content_full
        assert "second" in text_content_full

        # Find image placeholder
        image_placeholder_block = next((b for b in blocks if b.type == 'image_placeholder'), None)
        assert image_placeholder_block is not None
        assert image_placeholder_block.image_id_ref is not None

        # Check RawImageInput
        assert len(images) == 1
        raw_image = images[0]
        assert isinstance(raw_image, RawImageInput)
        assert raw_image.source_url == "http://example.com/images/test_image.jpg"
        assert raw_image.alt_text == "A test image"
        assert raw_image.image_id == image_placeholder_block.image_id_ref
        assert raw_image.job_id_for_gcs_path == "test_job_01"


@pytest.mark.asyncio
async def test_paywall_detection(web_acquisition_service: WebAcquisitionService):
    """
    Tests that the service correctly identifies content as being behind a paywall.
    """
    test_url = "http://wsj.com/test-article" # A domain in the VERY_STRICT_PAYWALL_DOMAINS set
    test_html = """
    <!DOCTYPE html>
    <html>
    <body>
        <div>
            <p>This is a short snippet of the article...</p>
            <div class="modal-paywall">
                <h2>Subscribe to read</h2>
                <p>Get unlimited access by subscribing now.</p>
            </div>
        </div>
    </body>
    </html>
    """
    mock_response = MockHttpxResponse(status_code=200, html_content=test_html, url=test_url)

    with patch('httpx.AsyncClient', new_callable=AsyncMock) as mock_async_client:
        mock_client_instance = mock_async_client.return_value.__aenter__.return_value
        mock_client_instance.get.return_value = mock_response
        
        service_input = WebAcquisitionServiceInput(url=test_url)
        result = await web_acquisition_service.execute(service_input)
        
        assert result.is_success()
        blocks, metadata, images = result.data
        
        assert metadata.is_paywalled is True
        assert "paywall" in metadata.content_summary.lower()
        assert len(blocks) == 0
        assert len(images) == 0


@pytest.mark.asyncio
async def test_http_error_handling(web_acquisition_service: WebAcquisitionService):
    """
    Tests that the service returns a failure result when an HTTP error occurs.
    """
    test_url = "http://example.com/not-found"
    mock_response = MockHttpxResponse(status_code=404, html_content="", url=test_url)

    with patch('httpx.AsyncClient', new_callable=AsyncMock) as mock_async_client:
        mock_client_instance = mock_async_client.return_value.__aenter__.return_value
        mock_client_instance.get.return_value = mock_response
        
        service_input = WebAcquisitionServiceInput(url=test_url)
        result = await web_acquisition_service.execute(service_input)

        assert not result.is_success()
        assert "Failed to process URL" in result.error_message
        assert "404" in result.error_message # Check that the status code is in the error
        assert result.data is None 