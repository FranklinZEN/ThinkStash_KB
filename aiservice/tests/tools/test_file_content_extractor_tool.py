# File: aiservice/tests/tools/test_file_content_extractor_tool.py
"""Unit tests for the FileContentExtractorTool."""

import pytest
import os
from app.tools.file_content_extractor_tool import FileContentExtractorTool, FileContent, ExtractedFileImage
from app.models.content_models import ImageRefUrl # Though not directly output by this tool, it's related for MD
from pydantic import HttpUrl

# Directory for test files
TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), "test_files_for_extractor")

@pytest.fixture(scope="session", autouse=True)
def create_test_files_directory():
    """Ensure the test_files directory exists before tests run."""
    if not os.path.exists(TEST_FILES_DIR):
        os.makedirs(TEST_FILES_DIR)
    # Create a dummy .txt file for basic testing
    txt_content = "This is a sample text file.\nIt has multiple lines.\nAnd some special characters: äöüß €uro."
    with open(os.path.join(TEST_FILES_DIR, "sample.txt"), "w", encoding="utf-8") as f:
        f.write(txt_content)
    
    # Create a dummy .md file for testing linked image extraction
    md_content = ("# Markdown Test\n\nThis is a test paragraph.\n" 
                  "![Alt text for image 1](http://example.com/image1.png)\n"
                  "Some more text.\n"
                  "![Alt 2](https://another.example.com/image2.jpg \"Optional Title\")\n"
                  "Text with no image.\n"
                  "![Relative Alt](../images/relative.gif)\n" # Relative, should be ignored by current web URL logic
                  "![No Alt]()\n" # No URL, should be ignored
                  "![Valid Alt But No URL]()\n"
                  "![Malformed URL](htp://bad.url)\n"
                 )
    with open(os.path.join(TEST_FILES_DIR, "sample.md"), "w", encoding="utf-8") as f:
        f.write(md_content)

    # Note: .docx and .pdf files with specific content (text, images, metadata) are harder to create programmatically
    # in a simple fixture. For robust testing of these, pre-existing sample files should be placed in
    # the TEST_FILES_DIR manually or using a more complex setup script.
    # For now, tests for docx/pdf might assume these files exist or will skip if not found.

@pytest.fixture
def tool() -> FileContentExtractorTool:
    """Pytest fixture to provide an instance of the tool."""
    return FileContentExtractorTool()

# --- Test Cases --- #

# 1. TXT File Processing (TS-AI-4.2 V1.2, Step 2.c)
def test_parse_txt_file_utf8(tool: FileContentExtractorTool):
    """Test successful parsing of a UTF-8 encoded .txt file."""
    file_path = os.path.join(TEST_FILES_DIR, "sample.txt")
    filename = "sample.txt"
    mime_type = "text/plain"
    
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    result = tool.run(file_content=file_bytes, filename=filename, mime_type=mime_type)

    assert result.status == "success"
    assert result.original_filename == filename
    assert "This is a sample text file." in result.extracted_text
    assert "äöüß €uro" in result.extracted_text
    assert result.images is None
    assert result.linked_markdown_images is None
    assert result.error_message is None
    assert result.page_title is None # TXT files don't have titles in this context

# TODO: Test TXT with other encodings if _parse_txt has specific fallback logic to verify.

# 2. MD File Processing (TS-AI-4.2 V1.2, Step 2.e) - Test linked_markdown_images
def test_parse_md_file_with_image_links(tool: FileContentExtractorTool):
    """Test parsing of a .md file and extraction of linked web image URLs and alt text."""
    file_path = os.path.join(TEST_FILES_DIR, "sample.md")
    filename = "sample.md"
    mime_type = "text/markdown"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    result = tool.run(file_content=file_bytes, filename=filename, mime_type=mime_type)

    assert result.status == "success"
    assert result.original_filename == filename
    assert "# Markdown Test" in result.extracted_text
    assert "This is a test paragraph." in result.extracted_text
    assert result.images is None # No embedded images expected from this MD parsing logic
    
    assert result.linked_markdown_images is not None
    assert len(result.linked_markdown_images) == 2 # Only valid, absolute HTTP(S) URLs

    expected_images = [
        {"url": "http://example.com/image1.png", "alt_text": "Alt text for image 1"},
        {"url": "https://another.example.com/image2.jpg", "alt_text": "Alt 2"}
    ]

    # Check if the extracted images match the expected ones, order might not be guaranteed by re.finditer
    # so convert to a list of frozensets for comparison if needed, or check presence.
    extracted_image_tuples = sorted([(img['url'], img.get('alt_text')) for img in result.linked_markdown_images])
    expected_image_tuples = sorted([(img['url'], img.get('alt_text')) for img in expected_images])

    assert extracted_image_tuples == expected_image_tuples
    
    assert result.error_message is None
    assert result.page_title is None # MD files don't have titles in this tool's context

# Test python-magic MIME inference (TS-AI-4.2 V1.2, Step 2.a)
def test_mime_inference_with_python_magic(tool: FileContentExtractorTool):
    """Test that python-magic is used to infer MIME type if an unreliable one is provided."""
    file_path = os.path.join(TEST_FILES_DIR, "sample.txt")
    filename = "sample.txt"
    # Provide an unreliable MIME type, forcing the tool to use python-magic
    unreliable_mime_type = "application/octet-stream"
    
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    # We expect python-magic to identify sample.txt as text/plain
    # and thus the _parse_txt method should be effectively called.
    result = tool.run(file_content=file_bytes, filename=filename, mime_type=unreliable_mime_type)

    assert result.status == "success" # Indicates _parse_txt was likely used
    assert "This is a sample text file." in result.extracted_text # Confirm txt content parsed
    assert result.error_message is None

    # Test with an empty string MIME type
    empty_mime_type = ""
    result_empty_mime = tool.run(file_content=file_bytes, filename=filename, mime_type=empty_mime_type)
    assert result_empty_mime.status == "success"
    assert "This is a sample text file." in result_empty_mime.extracted_text

    # Test with a completely unknown MIME type not in unreliable_mime_types set by default,
    # but also not a specifically supported one. This tests the fallback to extension if magic fails
    # or if the specific MIME isn't handled. The tool's dispatcher relies on extension if normalized_mime_type is empty OR not recognized.
    # If python-magic *does* return something specific for .txt like 'text/plain', this test path is covered by above.
    # If python-magic fails or returns octet-stream, then extension logic should kick in.
    unknown_mime_for_txt_extension_fallback = "application/x-custom-unknown"
    # To ensure we test the extension fallback, let's assume magic.from_buffer might return the same unknown type or fail.
    # We can mock magic.from_buffer to simulate it returning something still unreliable or failing.
    # For simplicity now, we'll rely on the dispatcher's `(not normalized_mime_type and file_extension == 'txt')`
    
    # This call implicitly tests if the dispatcher correctly uses the file_extension 
    # when the (potentially magic-inferred) mime_type isn't directly matched.
    # If python-magic correctly infers text/plain from sample.txt bytes, it will be handled by the text/plain branch.
    # If python-magic fails or returns octet-stream, normalized_mime_type might remain octet-stream or become empty,
    # then `(not normalized_mime_type and file_extension == 'txt')` should allow it to be parsed as txt.
    result_unknown_mime = tool.run(file_content=file_bytes, filename=filename, mime_type=unknown_mime_for_txt_extension_fallback)
    assert result_unknown_mime.status == "success" # Should still succeed due to .txt extension fallback
    assert "This is a sample text file." in result_unknown_mime.extracted_text

# TODO: Add tests for DOCX (TS-AI-4.2 V1.2, Step 2.d) - requires sample.docx

# TODO: Add tests for unsupported file types

# TODO: Add tests for corrupted files (if simulatable) 