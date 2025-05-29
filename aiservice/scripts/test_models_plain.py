# aiservice/tests/scripts/test_models_plain.py
import sys
import os

# Add the project root directory (E:\ThinkStash) to sys.path
# This allows Python to find the 'aiservice' package when the script is run from within aiservice/scripts
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime

# Adjust relative imports based on where you run this script from.
# If running from 'aiservice/tests/scripts/', and your app code is in 'aiservice/app/'
# you might need to adjust sys.path or use more robust import methods for larger projects.
# For simplicity, assuming PYTHONPATH is set or you run from a place where imports work.
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
        "type": "list",
        "items": ["item 1", {"type": "nested_item", "content": "item 2"}],
        "ordered": False,
        "page_number": 1
    }
    instance = ContentBlock(**data)
    assert instance.type == "list"
    assert len(instance.items) == 2
    print("ContentBlock (list) OK.")

if __name__ == "__main__":
    print("--- Running Model Sanity Checks (Plain Python) ---")
    try:
        test_raw_image_input_instantiation()
        test_enriched_image_metadata_instantiation()
        test_content_block_list_instantiation()
        # ... call other test functions ...
        print("--- All Model Sanity Checks Passed ---")
    except AssertionError as e:
        print(f"!!! Assertion Failed: {e} !!!")
    except Exception as e:
        print(f"!!! An unexpected error occurred: {e} !!!")
