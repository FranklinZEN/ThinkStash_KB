import asyncio
import os
import sys
import uuid
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

# Add project root to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

from aiservice.app.models.pipeline_models import (
    PreliminaryBlock, DocumentMetadata, EnrichedImageMetadata
)
from aiservice.app.models.orchestration_models import ContentBlock
from aiservice.app.models.content_structuring_models import ContentStructuringServiceInput
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService
from aiservice.app.services.base import ServiceResult

# --- Mock Data Creation Helpers ---
def create_mock_preliminary_block(
    block_id: str, type: str, order: int, text_content: Optional[str] = None,
    image_id_ref: Optional[str] = None, code_content: Optional[str] = None,
    code_language: Optional[str] = None, heading_level: Optional[int] = None,
    list_item_data: Optional[Any] = None, list_level: Optional[int] = 0,
    list_ordered: Optional[bool] = None, page_number: Optional[int] = 1,
    bbox: Optional[List[float]] = None, custom_attributes: Optional[Dict[str, Any]] = None
) -> PreliminaryBlock:
    return PreliminaryBlock(
        block_id=block_id, type=type, order=order, text_content=text_content,
        image_id_ref=image_id_ref, code_content=code_content, code_language=code_language,
        heading_level=heading_level, list_item_data=list_item_data, list_level=list_level,
        list_ordered=list_ordered, page_number=page_number, bbox=bbox or [0,0,100,100],
        custom_attributes=custom_attributes or {}
    )

def create_mock_enriched_image(
    image_id: str, original_source_identifier: str, gcs_url: Optional[str] = "gcs://fake/image.jpg",
    alt_text: Optional[str] = "alt text", caption: Optional[str] = "caption",
    llm_description: Optional[str] = "llm description", width: Optional[int] = 100, height: Optional[int] = 100
) -> EnrichedImageMetadata:
    return EnrichedImageMetadata(
        image_id=image_id, original_source_identifier=original_source_identifier,
        gcs_url=gcs_url, alt_text=alt_text, caption=caption, llm_description=llm_description,
        width=width, height=height
    )

def create_mock_document_metadata(doc_id: str, source_id: str, source_type: str) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=doc_id, source_identifier=source_id, source_type=source_type,
        extracted_at=datetime.utcnow()
    )

async def run_structuring_test(test_name: str, prelim_blocks: List[PreliminaryBlock], 
                               enriched_images: List[EnrichedImageMetadata], 
                               doc_meta: DocumentMetadata, job_id: str):
    print(f"\n--- Running Test: {test_name} ---")
    service = ContentStructuringService()
    service_input = ContentStructuringServiceInput(
        preliminary_blocks=prelim_blocks,
        enriched_images=enriched_images,
        document_metadata=doc_meta,
        job_id=job_id
    )

    result: ServiceResult[List[ContentBlock]] = await service.execute(service_input)

    if result.is_success():
        print(f"  Status: Success. Produced {len(result.data) if result.data else 0} ContentBlocks.")
        if result.data:
            for i, cb in enumerate(result.data):
                print(f"    Block {i}: ID={cb.block_id}, Type='{cb.type}'")
                if cb.type == 'text':
                    print(f"      Content: '{cb.content[:100]}...'")
                elif cb.type == 'heading':
                    print(f"      Level {cb.level}: '{cb.content}'")
                elif cb.type == 'list':
                    print(f"      Ordered: {cb.ordered}, Items ({len(cb.items)}):")
                    for item_idx, item in enumerate(cb.items or []):
                        print(f"        {item_idx + 1}. {str(item)[:100]}")
                elif cb.type == 'image':
                    print(f"      Image ID Ref: {cb.image_id_ref}, GCS: {cb.gcs_url}, Alt: {cb.alt_text}")
                elif cb.type == 'code_snippet':
                    print(f"      Language: {cb.language}, Content: '{cb.content[:100]}...'")
                elif cb.type == 'table':
                    print(f"      Table HTML Content: '{str(cb.content)[:100]}...'")
                elif cb.type == 'math':
                    print(f"      Math Content: '{cb.content[:100]}...'")
    else:
        print(f"  Status: Failed. Error: {result.error_message}")
        if result.error_details:
            print(f"    Details: {result.error_details}")
    print("--- Test Complete ---")
    return result

async def main():
    job_id_base = f"css_test_{uuid.uuid4().hex[:6]}"

    # --- Test Case 1: Basic text, heading, image ---
    case1_doc_meta = create_mock_document_metadata(f"{job_id_base}_doc1", "source1", "test_source")
    case1_enriched_images = [
        create_mock_enriched_image("img1", "orig_img1_src_id"),
        create_mock_enriched_image("img2", "orig_img2_src_id", caption="Image 2 specific caption")
    ]
    case1_prelim_blocks = [
        create_mock_preliminary_block("b1", "heading", 0, text_content="Main Title", heading_level=1),
        create_mock_preliminary_block("b2", "text", 1, text_content="This is the first paragraph."),
        create_mock_preliminary_block("b3", "image_placeholder", 2, image_id_ref="img1"),
        create_mock_preliminary_block("b4", "text", 3, text_content="Another paragraph after image."),
        create_mock_preliminary_block("b5", "image_placeholder", 4, image_id_ref="img_not_found"), # Test missing image
    ]
    await run_structuring_test("Basic Text, Heading, Image", case1_prelim_blocks, case1_enriched_images, case1_doc_meta, f"{job_id_base}_c1")

    print("\n" + "="*70 + "\n")

    # --- Test Case 2: List aggregation (simple and mixed levels/types) ---
    case2_doc_meta = create_mock_document_metadata(f"{job_id_base}_doc2", "source2", "test_source")
    case2_prelim_blocks = [
        create_mock_preliminary_block("l_intro", "text", 0, text_content="Here is a list:"),
        create_mock_preliminary_block("l1_i1", "list_item", 1, text_content="Item 1 (UL)", list_level=0, list_ordered=False),
        create_mock_preliminary_block("l1_i2", "list_item", 2, text_content="Item 2 (UL)", list_level=0, list_ordered=False),
        create_mock_preliminary_block("l1_i2_s1", "list_item", 3, text_content="Sub Item 2.1 (UL)", list_level=1, list_ordered=False),
        create_mock_preliminary_block("l1_i3", "list_item", 4, text_content="Item 3 (UL) - after sublist", list_level=0, list_ordered=False),
        create_mock_preliminary_block("l_sep", "text", 5, text_content="An ordered list:"),
        create_mock_preliminary_block("l2_i1", "list_item", 6, text_content="First (OL)", list_level=0, list_ordered=True),
        create_mock_preliminary_block("l2_i2", "list_item", 7, text_content="Second (OL)", list_level=0, list_ordered=True),
        create_mock_preliminary_block("l_outro", "text", 8, text_content="End of lists."),
    ]
    await run_structuring_test("List Aggregation", case2_prelim_blocks, [], case2_doc_meta, f"{job_id_base}_c2")

    print("\n" + "="*70 + "\n")

    # --- Test Case 3: Code, Table, Math ---
    case3_doc_meta = create_mock_document_metadata(f"{job_id_base}_doc3", "source3", "test_source")
    case3_prelim_blocks = [
        create_mock_preliminary_block("c1", "code_snippet", 0, code_content="print('Hello')", code_language="python"),
        create_mock_preliminary_block("t1", "table_placeholder", 1, custom_attributes={"html_content": "<table><tr><td>Data</td></tr></table>"}),
        create_mock_preliminary_block("m1", "math_text", 2, text_content="e = mc^2"),
        create_mock_preliminary_block("c2_un", "code_snippet", 3, code_content="no language specified"),
    ]
    await run_structuring_test("Code, Table, Math", case3_prelim_blocks, [], case3_doc_meta, f"{job_id_base}_c3")
    
    print("\n" + "="*70 + "\n")
    
    # --- Test Case 4: Empty input ---
    case4_doc_meta = create_mock_document_metadata(f"{job_id_base}_doc4", "source4", "empty_source")
    await run_structuring_test("Empty Input", [], [], case4_doc_meta, f"{job_id_base}_c4")

    print("\n" + "="*70 + "\n")

    # --- Test Case 5: List items only ---
    case5_doc_meta = create_mock_document_metadata(f"{job_id_base}_doc5", "source5", "list_only_source")
    case5_prelim_blocks = [
        create_mock_preliminary_block("only_l1_i1", "list_item", 0, text_content="Only Item 1 (UL)", list_level=0, list_ordered=False),
        create_mock_preliminary_block("only_l1_i2", "list_item", 1, text_content="Only Item 2 (UL)", list_level=0, list_ordered=False),
    ]
    await run_structuring_test("List Items Only", case5_prelim_blocks, [], case5_doc_meta, f"{job_id_base}_c5")

asyncio.run(main()) 