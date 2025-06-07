import sys
import os
from typing import List, Optional, Union, Dict, Any
from pydantic import ValidationError
from datetime import datetime, timezone

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from aiservice.app.models.pipeline_models import RawImageInput, EnrichedImageMetadata, PreliminaryBlock, DocumentMetadata
from aiservice.app.models.orchestration_models import ContentBlock

def test_raw_image_input_instantiation():
    print("Testing RawImageInput Instantiation...")
    data = {
        "image_id": "img_001",
        "source_document_id": "doc_001",
        "original_source_identifier_for_gcs_path": "source_id_gcs",
        "source_type_for_gcs_path": "pdf",
        "job_id_for_gcs_path": "job_123",
        "image_bytes": b"test",
    }
    instance = RawImageInput(**data)
    assert instance.image_id == "img_001"
    assert instance.image_bytes == b"test"
    print("RawImageInput OK.")

def test_enriched_image_metadata_instantiation():
    print("Testing EnrichedImageMetadata Instantiation...")
    data = {
        "image_id": "img_001",
        "original_source_identifier": "source_id_gcs",
        "gcs_url": "gs://bucket/image.png",
    }
    instance = EnrichedImageMetadata(**data)
    assert instance.image_id == "img_001"
    print("EnrichedImageMetadata OK.")

# ... (add other model tests similarly) ...

def test_content_block_list_instantiation():
    print("Testing ContentBlock (list) Instantiation...")
    data = {
        "block_id": "list_block_01",
        "user_id": "test_user_id",
        "document_id": "test_doc_id",
        "type": "list",
        "items": ["item 1", {"type": "nested_item", "content": "item 2"}],
        "ordered": False,
        "page_number": 1
    }
    instance = ContentBlock(**data)
    assert instance.type == "list"
    assert len(instance.items) == 2
    print("ContentBlock (list) OK.") 