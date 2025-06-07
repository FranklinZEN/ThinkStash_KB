import pytest
import uuid
from typing import List, Dict, Any
import sys
import os

# Adjust sys.path to include the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from aiservice.app.tools.content_processing_tools import FullTextContentExtractorTool

# Helper function to create content block DICTIONARIES for tests
def create_content_block_dict(block_type: str, content: str = None, items: List = None) -> Dict[str, Any]:
    return {
        "block_id": str(uuid.uuid4()),
        "user_id": "test_user",
        "document_id": "doc_test",
        "type": block_type,
        "content": content,
        "items": items,
        "order_index": 0
    }

@pytest.fixture
def text_extractor_tool() -> FullTextContentExtractorTool:
    return FullTextContentExtractorTool()

def test_extract_text_from_various_blocks(text_extractor_tool: FullTextContentExtractorTool):
    """Tests extraction from a mix of supported text-containing block types."""
    content_block_dicts = [
        create_content_block_dict(block_type="heading", content="Main Title"),
        create_content_block_dict(block_type="text", content="This is a paragraph."),
        create_content_block_dict(block_type="list", items=["Item 1", "Item 2", {"content": "Item 3 complex"}]),
        create_content_block_dict(block_type="code_snippet", content="print('Hello')"),
        create_content_block_dict(block_type="math_text", content="E = mc^2"),
        create_content_block_dict(block_type="table", content="<table><tr><td>Data</td></tr></table>"),
        create_content_block_dict(block_type="image", content=None) # Should be ignored
    ]
    expected_text = "Main Title\n\nThis is a paragraph.\n\nItem 1\n\nItem 2\n\nItem 3 complex\n\nprint('Hello')\n\nE = mc^2\n\n<table><tr><td>Data</td></tr></table>"
    result = text_extractor_tool._run(content_block_dicts=content_block_dicts)
    assert result == expected_text

def test_extract_text_empty_list(text_extractor_tool: FullTextContentExtractorTool):
    """Tests behavior with an empty list of content blocks."""
    content_block_dicts = []
    expected_text = ""
    result = text_extractor_tool._run(content_block_dicts=content_block_dicts)
    assert result == expected_text

def test_extract_text_no_textual_blocks(text_extractor_tool: FullTextContentExtractorTool):
    """Tests behavior with blocks that don't contain direct text."""
    content_block_dicts = [
        create_content_block_dict(block_type="image"),
        create_content_block_dict(block_type="image")
    ]
    expected_text = ""
    result = text_extractor_tool._run(content_block_dicts=content_block_dicts)
    assert result == expected_text

def test_extract_text_blocks_with_none_content(text_extractor_tool: FullTextContentExtractorTool):
    """Tests blocks where 'content' or 'items' are None for text-like types."""
    content_block_dicts = [
        create_content_block_dict(block_type="heading", content=None),
        create_content_block_dict(block_type="text", content=None),
        create_content_block_dict(block_type="list", items=["Valid item", "", {"no_content_key": "val"}]),
    ]
    expected_text = "Valid item"
    assert text_extractor_tool._run(content_block_dicts=content_block_dicts) == expected_text

def test_extract_text_list_items_various_formats(text_extractor_tool: FullTextContentExtractorTool):
    """Tests list items including strings, dicts with 'content', and dicts without 'content'."""
    content_block_dicts = [
        create_content_block_dict(block_type="list", items=[
            "Simple string item.",
            {"content": "Dictionary item with content."},
            {"other_key": "Dictionary item without content key."},
            "Another simple string."
        ])
    ]
    expected_text = "Simple string item.\n\nDictionary item with content.\n\nAnother simple string."
    result = text_extractor_tool._run(content_block_dicts=content_block_dicts)
    assert result == expected_text

def test_extract_text_only_list_block(text_extractor_tool: FullTextContentExtractorTool):
    """Tests extraction when only a list block is present."""
    content_block_dicts = [
        create_content_block_dict(block_type="list", items=["First item", "Second item"])
    ]
    expected_text = "First item\n\nSecond item"
    result = text_extractor_tool._run(content_block_dicts=content_block_dicts)
    assert result == expected_text 