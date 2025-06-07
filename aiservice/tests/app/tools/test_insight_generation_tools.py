import pytest
import json
import uuid
from typing import List, Dict, Any, Optional

from aiservice.app.tools.insight_generation_tools import FastContentBlockProcessorTool
from aiservice.app.models.task_output_models import StructuredSummary, Segment
from aiservice.app.models.orchestration_models import ContentBlock

# --- Test Fixtures ---

@pytest.fixture
def default_user_id() -> str:
    return "test_user_tool"

@pytest.fixture
def default_document_id() -> str:
    return "test_doc_tool_reconstruction"

@pytest.fixture
def processor_tool(default_user_id, default_document_id) -> FastContentBlockProcessorTool:
    """Fixture to create an instance of FastContentBlockProcessorTool."""
    return FastContentBlockProcessorTool(user_id=default_user_id, document_id=default_document_id)

@pytest.fixture
def sample_image_meta_list() -> List[Dict[str, Any]]:
    return [
        {"image_id_ref": "img_ref_1", "gcs_url": "gs://bucket/image1.jpg", "alt_text": "Image 1", "caption": "Caption 1"},
        {"image_id_ref": "img_ref_2", "gcs_url": "gs://bucket/image2.png", "alt_text": "Image 2"},
        # Image only identifiable by gcs_url for fallback testing
        {"gcs_url": "gs://bucket/image3_fallback.gif", "alt_text": "Image 3 Fallback"},
    ]

@pytest.fixture
def sample_image_meta_json(sample_image_meta_list) -> str:
    return json.dumps(sample_image_meta_list)

# --- Test Cases for reconstruct_content_from_summary ---

def test_reconstruct_text_only(processor_tool: FastContentBlockProcessorTool, sample_image_meta_json: str, default_user_id: str, default_document_id: str):
    segments = [
        Segment(type="text", content="Hello world."),
        Segment(type="text", content="This is a test.")
    ]
    structured_summary = StructuredSummary(segments=segments)
    
    result = processor_tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=structured_summary,
        image_metadata_list_json=sample_image_meta_json
    )

    assert isinstance(result, list)
    assert len(result) == 2
    for i, block_dict in enumerate(result):
        assert block_dict["type"] == "text"
        assert block_dict["content"] == segments[i].content
        assert uuid.UUID(block_dict["block_id"]) # Check if it's a valid UUID string
        assert block_dict["user_id"] == default_user_id
        assert block_dict["document_id"] == default_document_id
        assert block_dict["order_index"] == i

def test_reconstruct_with_text_and_images_found(processor_tool: FastContentBlockProcessorTool, sample_image_meta_list: List[Dict[str,Any]], sample_image_meta_json: str, default_user_id: str, default_document_id: str):
    segments = [
        Segment(type="text", content="Summary part 1."),
        Segment(type="image_reference", image_id_ref="img_ref_1"),
        Segment(type="text", content="Summary part 2."),
        Segment(type="image_reference", image_id_ref="img_ref_2"),
        Segment(type="image_reference", image_id_ref="gs://bucket/image3_fallback.gif") # Test GCS URL fallback
    ]
    structured_summary = StructuredSummary(segments=segments)

    result = processor_tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=structured_summary,
        image_metadata_list_json=sample_image_meta_json
    )

    assert isinstance(result, list)
    assert len(result) == 5
    
    # Block 0 (text)
    assert result[0]["type"] == "text"
    assert result[0]["content"] == "Summary part 1."
    assert result[0]["user_id"] == default_user_id
    assert result[0]["document_id"] == default_document_id
    assert result[0]["order_index"] == 0

    # Block 1 (image - img_ref_1)
    assert result[1]["type"] == "image"
    assert result[1]["image_id_ref"] == "img_ref_1"
    assert result[1]["gcs_url"] == sample_image_meta_list[0]["gcs_url"]
    assert result[1]["alt_text"] == sample_image_meta_list[0]["alt_text"]
    assert result[1]["caption"] == sample_image_meta_list[0]["caption"]
    assert result[1]["user_id"] == default_user_id
    assert result[1]["document_id"] == default_document_id
    assert result[1]["order_index"] == 1
    
    # Block 2 (text)
    assert result[2]["type"] == "text"
    assert result[2]["content"] == "Summary part 2."
    assert result[2]["order_index"] == 2

    # Block 3 (image - img_ref_2)
    assert result[3]["type"] == "image"
    assert result[3]["image_id_ref"] == "img_ref_2"
    assert result[3]["gcs_url"] == sample_image_meta_list[1]["gcs_url"]
    assert result[3]["alt_text"] == sample_image_meta_list[1]["alt_text"]
    assert result[3]["order_index"] == 3

    # Block 4 (image - gs://bucket/image3_fallback.gif)
    assert result[4]["type"] == "image"
    assert result[4]["image_id_ref"] == None # No image_id_ref in original meta for this one
    assert result[4]["gcs_url"] == sample_image_meta_list[2]["gcs_url"]
    assert result[4]["alt_text"] == sample_image_meta_list[2]["alt_text"]
    assert result[4]["order_index"] == 4


def test_reconstruct_image_not_found(processor_tool: FastContentBlockProcessorTool, sample_image_meta_json: str):
    segments = [
        Segment(type="text", content="Text before missing image."),
        Segment(type="image_reference", image_id_ref="non_existent_img_ref"),
        Segment(type="text", content="Text after missing image.")
    ]
    structured_summary = StructuredSummary(segments=segments)
    
    result = processor_tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=structured_summary,
        image_metadata_list_json=sample_image_meta_json
    )
    assert isinstance(result, list)
    assert len(result) == 2 # Image block should be skipped
    assert result[0]["content"] == "Text before missing image."
    assert result[1]["content"] == "Text after missing image."

def test_reconstruct_empty_segments(processor_tool: FastContentBlockProcessorTool, sample_image_meta_json: str):
    structured_summary = StructuredSummary(segments=[])
    result = processor_tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=structured_summary,
        image_metadata_list_json=sample_image_meta_json
    )
    assert isinstance(result, list)
    assert len(result) == 0

def test_reconstruct_none_structured_summary_input(processor_tool: FastContentBlockProcessorTool, sample_image_meta_json: str):
    result = processor_tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=None,
        image_metadata_list_json=sample_image_meta_json
    )
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["error"] is not None
    assert "structured_summary_input" in result[0]["error"]

def test_reconstruct_none_image_metadata_json(processor_tool: FastContentBlockProcessorTool):
    segments = [Segment(type="text", content="Test")]
    structured_summary = StructuredSummary(segments=segments)
    result = processor_tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=structured_summary,
        image_metadata_list_json=None
    )
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["error"] is not None
    assert "image_metadata_list_json" in result[0]["error"]
    
def test_reconstruct_invalid_image_metadata_json(processor_tool: FastContentBlockProcessorTool):
    segments = [Segment(type="text", content="Test")]
    structured_summary = StructuredSummary(segments=segments)
    result = processor_tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=structured_summary,
        image_metadata_list_json="this is not json"
    )
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["error"] is not None
    assert "Invalid JSON" in result[0]["error"]

def test_reconstruct_unknown_segment_type(processor_tool: FastContentBlockProcessorTool, sample_image_meta_json: str):
    segments = [
        Segment(type="text", content="First part."),
        Segment(type="custom_unknown_type", content="This should be skipped."),
        Segment(type="text", content="Second part.")
    ]
    # For testing, we are intentionally passing a segment with an invalid type.
    # Pydantic might raise an error if Segment model strictly validates 'type' against an Enum.
    # Assuming Segment.type is a simple string for this test to pass through to the tool's logic.
    structured_summary = StructuredSummary(segments=segments) 
    
    result = processor_tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=structured_summary,
        image_metadata_list_json=sample_image_meta_json
    )
    assert isinstance(result, list)
    assert len(result) == 2 # Unknown segment should be skipped
    assert result[0]["content"] == "First part."
    assert result[1]["content"] == "Second part."

def test_reconstruct_uses_tool_init_ids(default_user_id, default_document_id):
    """Test that user_id and document_id from tool's init are used."""
    # Create a tool instance directly to control its init params for this test
    tool = FastContentBlockProcessorTool(user_id="init_user", document_id="init_doc")
    
    segments = [Segment(type="text", content="Content from init_ids test")]
    structured_summary = StructuredSummary(segments=segments)
    image_meta_json = json.dumps([]) # Empty image meta

    result = tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=structured_summary,
        image_metadata_list_json=image_meta_json
        # Not passing document_id or user_id as _run args
    )
    assert len(result) == 1
    assert result[0]["user_id"] == "init_user"
    assert result[0]["document_id"] == "init_doc"
    assert result[0]["content"] == "Content from init_ids test"

def test_reconstruct_run_method_document_id_override(default_user_id, default_document_id):
    """Test that document_id passed to _run overrides the one from tool's init."""
    init_doc_id = "doc_id_from_init"
    run_arg_doc_id = "doc_id_from_run_arg"

    # Create a tool instance with a specific initial document_id
    tool = FastContentBlockProcessorTool(user_id=default_user_id, document_id=init_doc_id)
    
    segments = [Segment(type="text", content="Content for doc_id override test")]
    structured_summary = StructuredSummary(segments=segments)
    image_meta_json = json.dumps([]) # Empty image meta

    result = tool._run(
        operation="reconstruct_content_from_summary",
        structured_summary_input=structured_summary,
        image_metadata_list_json=image_meta_json,
        document_id=run_arg_doc_id # Pass a different document_id here
    )
    assert len(result) == 1
    assert result[0]["user_id"] == default_user_id # User ID should still be from init
    assert result[0]["document_id"] == run_arg_doc_id # Document ID should be from the _run argument
    assert result[0]["content"] == "Content for doc_id override test"

# More tests can be added for other operations if FastContentBlockProcessorTool
# has them, e.g., 'concatenate_text', 'extract_image_metadata'.
# For now, focusing on the refactored 'reconstruct_content_from_summary'. 