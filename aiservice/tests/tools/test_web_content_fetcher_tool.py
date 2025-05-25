# File: aiservice/tests/tools/test_web_content_fetcher_tool.py
"""Unit tests for the WebContentFetcherTool."""

import pytest
import requests_mock # Already added to requirements.txt
from app.tools.web_content_fetcher_tool import WebContentFetcherTool, WebContent, FetchedWebImage
from pydantic import HttpUrl

@pytest.fixture
def tool() -> WebContentFetcherTool:
    """Pytest fixture to provide an instance of the tool."""
    return WebContentFetcherTool()

def test_fetch_simple_html_success(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test successful fetching and parsing of a simple HTML page."""
    test_url = "http://example.com/simple"
    mock_html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Title</title></head>
    <body>
        <h1>Main Heading</h1>
        <p>This is the first paragraph of main content.</p>
        <article>
            <p>This is article content.</p>
            <img src=\"image1.jpg\" alt=\"Alt text for image 1\">
            <figure>
                <img src=\"/images/image2.png\" alt=\"Alt text 2\">
                <figcaption>Caption for image 2</figcaption>
            </figure>
        </article>
        <p>Another paragraph outside article.</p>
        <script>console.log('ignore me')</script>
        <style>.ignore{color:red;}</style>
        <footer>Footer content</footer>
    </body>
    </html>
    """
    requests_mock.get(test_url, text=mock_html_content, status_code=200, headers={'Content-Type': 'text/html'})

    result = tool.run(url=test_url)

    assert result.status == "success"
    assert result.original_url == HttpUrl(test_url)
    assert result.final_url == HttpUrl(test_url)
    assert result.page_title == "Test Title"
    
    # Trafilatura should focus on the main content. 
    # The exact output can be sensitive to its algorithm, so we check for key phrases.
    assert "This is article content." in result.extracted_text
    assert "Main Heading" in result.extracted_text # Trafilatura might pick this up too
    assert "Footer content" not in result.extracted_text # Should be excluded
    assert "ignore me" not in result.extracted_text

    assert result.images is not None
    assert len(result.images) == 2

    img1_found = any(img.url == HttpUrl("http://example.com/image1.jpg") and img.alt_text == "Alt text for image 1" for img in result.images)
    img2_found = any(
        img.url == HttpUrl("http://example.com/images/image2.png") and 
        img.alt_text == "Alt text 2" and 
        img.caption == "Caption for image 2" 
        for img in result.images
    )
    assert img1_found, "Image 1 from article not found or incorrect."
    assert img2_found, "Image 2 from figure not found or incorrect."
    
    assert result.pdf_bytes is None
    assert result.error_message is None

# Test for Initial URL Type Filtering (TS-AI-4.1 V1.2, Step 2.b)
@pytest.mark.parametrize(
    "test_url, expected_error_message_part",
    [
        ("https://www.youtube.com/watch?v=7j1t3UZA1TY", "video platform homepage"),
        ("https://www.facebook.com/feed/", "social media feed"),
        ("https://twitter.com/home", "social media feed"),
        ("https://www.linkedin.com/company/somecompany/", "generic user/profile page"),
        ("http://instagram.com/p/shortcode", "video platform homepage"),
        ("http://tiktok.com/some/user/video/123", "video platform homepage"),
        ("http://reddit.com/r/popular", "social media feed")
    ]
)
def test_initial_url_type_filtering(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker, test_url: str, expected_error_message_part: str):
    """Test that various unsupported URL types are filtered out before HTTP requests."""
    # No HTTP request should be made, so no need to mock a specific response for test_url.
    # We can mock a generic one to catch if a request is unexpectedly made.
    requests_mock.get(requests_mock.ANY, real_http=True) # Allow other mocks if any, but we don't expect one for test_url

    result = tool.run(url=test_url)

    assert result.status == "unsupported_url_type"
    assert result.original_url == HttpUrl(test_url)
    assert expected_error_message_part in result.error_message
    assert result.extracted_text is None
    assert result.images is None
    assert result.pdf_bytes is None

@pytest.mark.parametrize(
    "test_url",
    [
        ("https://www.linkedin.com/pulse/article-title-here"),
        ("https://x.com/username/status/1234567890"),
        ("https://www.reddit.com/r/programming/comments/xyz123/a_great_programming_article/")
    ]
)
def test_allowed_social_media_posts_pass_initial_filter(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker, test_url: str):
    """
    Test that specifically allowed social media post URLs pass the initial filter
    and would proceed to fetching (which we mock as a simple success here).
    """
    # Mock a successful fetch for these allowed URLs to show they passed the filter.
    mock_html_content = "<html><head><title>Allowed Post</title></head><body>Some content</body></html>"
    requests_mock.get(test_url, text=mock_html_content, status_code=200, headers={'Content-Type': 'text/html'})

    result = tool.run(url=test_url)

    # We are primarily checking they didn't get blocked by "unsupported_url_type".
    # The actual processing result will depend on the mocked HTML.
    assert result.status != "unsupported_url_type"
    # A more specific assertion would be that it proceeds to fetching, e.g., status == "success" for this mock.
    assert result.status == "success" # Based on the simple mock_html_content
    assert result.page_title == "Allowed Post"

# Test for Tier 1 Paywall Detection (Strict Domains - TS-AI-4.1 V1.2)
def test_strict_paywall_domain_check(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test that URLs from strictly paywalled domains are flagged before HTTP requests."""
    strict_domain_url = "http://wsj.com/some-article"
    
    # No HTTP request should be made for strictly paywalled domains (initial check).
    # Mock a generic one to catch if a request is unexpectedly made.
    requests_mock.get(requests_mock.ANY, real_http=True)

    result = tool.run(url=strict_domain_url)

    assert result.status == "strict_paywall_domain"
    assert result.original_url == HttpUrl(strict_domain_url)
    assert "Site (from initial URL) is known to have a strict paywall" in result.error_message
    assert result.extracted_text is None
    assert result.images is None

def test_strict_paywall_domain_after_redirect(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test strict paywall detection if redirected to a strictly paywalled domain."""
    initial_url = "http://some-shortener.com/article"
    strict_redirect_url = "https://wsj.com/redirected-article"

    # Mock the redirect
    requests_mock.get(initial_url, status_code=302, headers={'Location': strict_redirect_url})
    # Crucially, no further mocks for strict_redirect_url, as it shouldn't be fetched if caught by domain check.

    result = tool.run(url=initial_url)

    assert result.status == "strict_paywall_domain"
    assert result.original_url == HttpUrl(initial_url)
    assert result.final_url == HttpUrl(strict_redirect_url)
    assert "Redirected to a site known for a strict paywall" in result.error_message
    assert result.extracted_text is None
    assert result.images is None

# Test for Tier 2 Paywall Detection (Keywords/Selectors - TS-AI-4.1 V1.2)
@pytest.mark.parametrize(
    "paywall_html_content, expected_message_part",
    [
        ("<html><head><title>Paywall Page</title></head><body>Please subscribe to continue reading.</body></html>", "keyword: 'subscribe'"),
        ("<html><head><title>Login Wall</title></head><body><div class=\"modal-paywall\">You must log in to continue.</div></body></html>", "CSS selector: '.modal-paywall'"),
        ("<html><title>Restricted</title><body><p>This is premium content for members only.</p></body></html>", "keyword: 'premium content'"),
        ("<html><title>Join Us</title><body><div id=\"paywall-dialog-special\">Become a member to unlock.</div></body></html>", "CSS selector: '[id*=paywall]'") # Test attribute selector
    ]
)
def test_suspected_paywall_patterns(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker, paywall_html_content: str, expected_message_part: str):
    """Test detection of paywalls based on keywords or CSS selectors in fetched HTML."""
    test_url = "http://example.com/article-with-paywall-clues"
    requests_mock.get(test_url, text=paywall_html_content, status_code=200, headers={'Content-Type': 'text/html'})

    result = tool.run(url=test_url)

    assert result.status == "suspected_paywall_patterns"
    assert result.original_url == HttpUrl(test_url)
    assert expected_message_part in result.error_message
    assert result.page_title is not None # Should still attempt to get title
    assert result.extracted_text is not None # Should return some preview text
    assert len(result.extracted_text) > 0
    assert result.images is None # No images processed if paywall suspected this early

def test_paywall_detection_on_http_error_page(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test if paywall keywords are detected on an HTTP error page (e.g., 403)."""
    test_url = "http://example.com/forbidden-article"
    error_html_content = "<html><title>Forbidden</title><body>Access denied. To read this premium content, please subscribe.</body></html>"
    requests_mock.get(test_url, text=error_html_content, status_code=403, headers={'Content-Type': 'text/html'})

    result = tool.run(url=test_url)

    assert result.status == "suspected_paywall_patterns"
    assert "Paywall suspected (keywords) on 403 error page" in result.error_message
    assert result.extracted_text is not None

# Test for Tier 3 Paywall Detection (Post-Extraction - TS-AI-4.1 V1.2)
def test_error_paywall_post_extraction(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test paywall detection after content extraction if text is minimal and has keywords."""
    test_url = "http://example.com/minimal-content-paywall"
    # This HTML has no obvious paywall selectors or widespread keywords in the raw HTML,
    # but the main extracted content will be short and contain a keyword.
    mock_html_content = """
    <html><head><title>Minimal Article</title></head>
    <body>
        <div class=\"article-body\">
            <p>Welcome to our site. To read the full story, please subscribe.</p>
            <p>Only a small preview is available here.</p>
        </div>
        <div>Some other unrelated divs that trafilatura might ignore.</div>
    </body></html>
    """
    # Trafilatura might extract something like: "Welcome to our site. To read the full story, please subscribe. Only a small preview is available here."
    requests_mock.get(test_url, text=mock_html_content, status_code=200, headers={'Content-Type': 'text/html'})

    result = tool.run(url=test_url)

    assert result.status == "error_paywall" # As per our tool's Tier 3 logic
    assert result.original_url == HttpUrl(test_url)
    assert result.page_title == "Minimal Article"
    assert "Paywall encountered (short content with keywords after parse)" in result.error_message
    assert result.extracted_text is not None
    assert "please subscribe" in result.extracted_text.lower()
    assert len(result.extracted_text) < 500 # Check against the threshold in the tool

# Test for PDF Download (TS-AI-4.1 V1.2, Step 2.e)
def test_pdf_download_from_url(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test correct handling of a URL that points directly to a PDF file."""
    pdf_url = "http://example.com/document.pdf"
    mock_pdf_content = b"%PDF-1.4\n%Fake PDF content"
    # Mock response with PDF content type
    requests_mock.get(pdf_url, content=mock_pdf_content, status_code=200, headers={'Content-Type': 'application/pdf'})

    result = tool.run(url=pdf_url)

    assert result.status == "pdf_content_downloaded"
    assert result.original_url == HttpUrl(pdf_url)
    assert result.final_url == HttpUrl(pdf_url)
    assert result.pdf_bytes == mock_pdf_content
    assert result.page_title == "document.pdf" # Should derive from URL path
    assert result.extracted_text is None
    assert result.images is None
    assert result.error_message is None

def test_pdf_download_with_content_disposition(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test PDF download where filename is in Content-Disposition header."""
    pdf_url = "http://example.com/download-pdf.php?id=123"
    mock_pdf_content = b"%PDF-1.7\n%Another Fake PDF"
    content_disposition_filename = "My Important Document.pdf"
    headers = {
        'Content-Type': 'application/pdf',
        'Content-Disposition': f'attachment; filename="{content_disposition_filename}"'
    }
    requests_mock.get(pdf_url, content=mock_pdf_content, status_code=200, headers=headers)

    result = tool.run(url=pdf_url)

    assert result.status == "pdf_content_downloaded"
    assert result.pdf_bytes == mock_pdf_content
    assert result.page_title == content_disposition_filename

# Test for Unsupported Content Type (after successful fetch)
def test_unsupported_content_type_after_fetch(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test handling of unsupported content types like images or plain text after a successful fetch."""
    test_url_image = "http://example.com/image.jpg"
    requests_mock.get(test_url_image, content=b"fake image data", status_code=200, headers={'Content-Type': 'image/jpeg'})
    
    result_image = tool.run(url=test_url_image)
    assert result_image.status == "unsupported_content_type"
    assert result_image.original_url == HttpUrl(test_url_image)
    assert "Content type 'image/jpeg' is not HTML or PDF" in result_image.error_message

    test_url_text_plain = "http://example.com/data.txt"
    requests_mock.get(test_url_text_plain, text="just plain text", status_code=200, headers={'Content-Type': 'text/plain'})
    
    result_text_plain = tool.run(url=test_url_text_plain)
    assert result_text_plain.status == "unsupported_content_type"
    assert result_text_plain.original_url == HttpUrl(test_url_text_plain)
    assert "Content type 'text/plain' is not HTML or PDF" in result_text_plain.error_message

# Test for Network Errors (fetch_error - TS-AI-4.1 V1.2)
@pytest.mark.parametrize(
    "error_condition, expected_message_part",
    [
        (requests_mock.exceptions.Timeout("Request timed out"), "Request timed out"),
        (requests_mock.exceptions.ConnectionError("Failed to connect"), "Network fetch error"), # Maps to RequestException
        (requests_mock.exceptions.InvalidURL("Invalid URL provided"), "Network fetch error") # Maps to RequestException
    ]
)
def test_network_fetch_errors_request_exceptions(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker, error_condition: Exception, expected_message_part: str):
    """Test various requests.exceptions leading to 'fetch_error'."""
    test_url = "http://example.com/network-error"
    requests_mock.get(test_url, exc=error_condition)

    result = tool.run(url=test_url)

    assert result.status == "fetch_error"
    assert result.original_url == HttpUrl(test_url)
    assert expected_message_part in result.error_message

@pytest.mark.parametrize(
    "http_status_code, expected_message_part",
    [
        (404, "HTTP error: 404"),
        (500, "HTTP error: 500"),
        (400, "HTTP error: 400"),
    ]
)
def test_network_fetch_errors_http_status(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker, http_status_code: int, expected_message_part: str):
    """Test HTTP status codes (4xx, 5xx) not specifically handled as paywalls, leading to 'fetch_error'."""
    test_url = f"http://example.com/http-error-{http_status_code}"
    # For these generic HTTP errors, we don't expect paywall keywords in the response body, 
    # so the tool should classify them as general fetch_error.
    requests_mock.get(test_url, status_code=http_status_code, text=f"Error page for {http_status_code}")

    result = tool.run(url=test_url)
    
    assert result.status == "fetch_error"
    assert result.original_url == HttpUrl(test_url)
    assert expected_message_part in result.error_message

# Test for specific HTTP 403/401/451 errors that *don't* contain paywall keywords
# (those *with* keywords are tested in test_paywall_detection_on_http_error_page)
def test_http_403_without_paywall_keywords(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test a 403 error response that doesn't contain paywall keywords, resulting in fetch_error."""
    test_url = "http://example.com/forbidden-no-clues"
    error_html_content = "<html><title>Forbidden</title><body>Access strictly denied. No further info.</body></html>"
    requests_mock.get(test_url, text=error_html_content, status_code=403, headers={'Content-Type': 'text/html'})

    result = tool.run(url=test_url)

    assert result.status == "fetch_error"
    assert "HTTP error: 403" in result.error_message
    assert "Paywall suspected" not in result.error_message # Ensure it didn't get misclassified

# Test for HTTP Redirects
def test_redirect_handling(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test that the tool correctly follows redirects and reports original and final URLs."""
    original_url = "http://example.com/initial"
    redirect_once_url = "http://example.com/redirect1"
    final_url = "http://example.com/final-destination"

    # Mock a chain of redirects: initial -> redirect1 -> final
    requests_mock.get(original_url, status_code=302, headers={'Location': redirect_once_url})
    requests_mock.get(redirect_once_url, status_code=301, headers={'Location': final_url})
    
    # Mock the final destination page content
    final_html_content = "<html><head><title>Final Page</title></head><body>Content of the final page.</body></html>"
    requests_mock.get(final_url, text=final_html_content, status_code=200, headers={'Content-Type': 'text/html'})

    result = tool.run(url=original_url)

    assert result.status == "success"
    assert result.original_url == HttpUrl(original_url)
    assert result.final_url == HttpUrl(final_url)
    assert result.page_title == "Final Page"
    assert "Content of the final page" in result.extracted_text

# Test for Edge Cases (No content, no title, no images - TS-AI-4.1 V1.2)
def test_edge_case_no_title(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test a page that has content but no <title> tag."""
    test_url = "http://example.com/no-title"
    mock_html_content = "<html><head></head><body><p>Some content here.</p></body></html>"
    requests_mock.get(test_url, text=mock_html_content, status_code=200, headers={'Content-Type': 'text/html'})

    result = tool.run(url=test_url)

    assert result.status == "success"
    assert result.page_title is None
    assert "Some content here" in result.extracted_text

def test_edge_case_no_meaningful_text_content(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test a page with HTML structure but no real textual content for Trafilatura to extract."""
    test_url = "http://example.com/no-text"
    # Trafilatura might return very little or None for such a page.
    mock_html_content = "<html><head><title>No Text Page</title></head><body><div><img src='onlyimage.jpg'></div><span></span></body></html>"
    requests_mock.get(test_url, text=mock_html_content, status_code=200, headers={'Content-Type': 'text/html'})

    result = tool.run(url=test_url)

    # Expect parse_error if no text AND no images are found (as per tool logic)
    # If an image *was* found, it might be success with text as None.
    # Current mock has an image, let's make it findable.
    mock_html_content_with_image = "<html><head><title>No Text Page</title></head><body><div><img src='http://example.com/onlyimage.jpg' alt='lone image'></div></body></html>"
    requests_mock.get(test_url, text=mock_html_content_with_image, status_code=200, headers={'Content-Type': 'text/html'})
    result_with_image = tool.run(url=test_url)

    if not result_with_image.images:
        assert result_with_image.status == "parse_error" # No text, no images
        assert "Trafilatura and BeautifulSoup could not extract significant text or images" in result_with_image.error_message
    else:
        assert result_with_image.status == "success" # Image found, text might be None or empty
        assert result_with_image.extracted_text is None or len(result_with_image.extracted_text.strip()) == 0
        assert len(result_with_image.images) == 1
        assert result_with_image.images[0].url == HttpUrl("http://example.com/onlyimage.jpg")

    # Test with truly empty content that Trafilatura returns None for, and no images
    mock_html_empty_for_trafilatura = "<html><head><title>Empty</title></head><body><div></div></body></html>"
    requests_mock.get("http://example.com/truly-no-content", text=mock_html_empty_for_trafilatura, status_code=200, headers={'Content-Type': 'text/html'})
    result_truly_empty = tool.run(url="http://example.com/truly-no-content")
    assert result_truly_empty.status == "parse_error"
    assert "Trafilatura and BeautifulSoup could not extract significant text or images" in result_truly_empty.error_message

def test_edge_case_no_images(tool: WebContentFetcherTool, requests_mock: requests_mock.Mocker):
    """Test a page with text content but no images."""
    test_url = "http://example.com/no-images"
    mock_html_content = "<html><head><title>Text Only</title></head><body><p>This page has text but no images at all.</p></body></html>"
    requests_mock.get(test_url, text=mock_html_content, status_code=200, headers={'Content-Type': 'text/html'})

    result = tool.run(url=test_url)

    assert result.status == "success"
    assert "This page has text but no images" in result.extracted_text
    assert result.images is None or len(result.images) == 0

# TODO: Add more test cases as per TS-AI-4.4, V1.2 plan:
# - Parse errors (if possible to simulate for trafilatura/bs4 more directly for internal errors)
# - Advanced caption extraction scenarios

# TODO: Add more test cases as per TS-AI-4.4, V1.2 plan:
# - Parse errors (if possible to simulate for trafilatura/bs4)
# - Edge cases: pages with no images, no main content, no title
# - Advanced caption extraction scenarios 