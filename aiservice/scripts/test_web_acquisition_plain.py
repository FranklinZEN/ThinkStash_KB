import asyncio
import os
import sys
import uuid
from typing import Tuple, List, cast

# Add project root to sys.path to allow aiservice imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# PROJECT_ROOT is the parent directory of 'aiservice' package, which is parent of 'scripts'
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR)) 
sys.path.insert(0, PROJECT_ROOT)

from aiservice.app.services.acquisition.web_service import WebAcquisitionService, WebAcquisitionServiceInput
from aiservice.app.services.base import ServiceResult
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput

async def run_web_acquisition_test(url: str, job_id: str, processing_level: str ="full_content"):
    print(f"\n--- Testing WebAcquisitionService with URL: {url} ---")
    
    service = WebAcquisitionService()
    service_input = WebAcquisitionServiceInput(
        url=url,
        job_id=job_id,
        processing_level=processing_level
    )

    service_result: ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]] = await service.execute(service_input)

    # --- DEBUG PRINTS START ---
    # print(f"  DEBUG: Raw service_result object: {service_result!r}")
    if service_result:
        print(f"  DEBUG: service_result.success: {service_result.success}")
        if service_result.data and isinstance(service_result.data, tuple) and len(service_result.data) == 3:
            prelim_blocks, doc_meta, raw_imgs = service_result.data
            print(f"  DEBUG: service_result.data: (")
            print(f"    PreliminaryBlocks (count: {len(prelim_blocks) if prelim_blocks else 0}),")
            print(f"    DocumentMetadata: {doc_meta!r},")
            print(f"    RawImageInputs (count: {len(raw_imgs) if raw_imgs else 0}): [")
            if raw_imgs:
                for idx, img_input in enumerate(raw_imgs):
                    print(f"      Image {idx}: id={img_input.image_id}, filename={img_input.original_filename}, image_bytes_present={'Yes' if img_input.image_bytes else 'No'}")
            print(f"    ]")
            print(f"  )")
        else:
            print(f"  DEBUG: service_result.data: {service_result.data!r}")
        print(f"  DEBUG: service_result.error_message: {service_result.error_message}")
        # print(f"  DEBUG: service_result.error_details: {service_result.error_details!r}") # Can be verbose
    # --- DEBUG PRINTS END ---

    actual_success_status = service_result.is_success()
    print(f"  DEBUG: service_result.is_success() returned: {actual_success_status!r} (type: {type(actual_success_status)})")

    if actual_success_status == True and service_result.data and len(service_result.data) == 3:
        preliminary_blocks, doc_metadata, raw_images = service_result.data

        print(f"  Status: Success")
        if doc_metadata:
            print(f"  Final URL: {doc_metadata.final_url}")
            print(f"  Title: {doc_metadata.title}")
            print(f"  Source Type: {doc_metadata.source_type}")
            print(f"  Extracted At: {doc_metadata.extracted_at}")
            print(f"  Custom Fields: {doc_metadata.custom_fields}")
        
        print(f"\n  --- PreliminaryBlocks ({len(preliminary_blocks)}) ---")
        text_block_count = 0
        heading_block_count = 0
        list_item_block_count = 0
        image_placeholder_count = 0
        code_snippet_count = 0
        table_placeholder_count = 0

        for i, block in enumerate(preliminary_blocks):
            text_preview = (block.text_content[:75] + '...') if block.text_content and len(block.text_content) > 75 else block.text_content
            code_preview = (block.code_content[:150] + '...') if block.code_content and len(block.code_content) > 150 else block.code_content
            
            print(f"    Block {i}: ID={block.block_id}, Type='{block.type}', Order={block.order}")
            if block.type == "text":
                text_block_count += 1
                print(f"      Text: '{text_preview}'")
            elif block.type == "heading":
                heading_block_count +=1
                print(f"      Heading (L{block.heading_level}): '{text_preview}'")
            elif block.type == "list_item":
                list_item_block_count +=1
                # Ensure list_item_data (if used) or text_content is displayed appropriately
                print(f"      List Item (L{block.list_level}, Ordered={block.list_ordered}): '{text_preview}'")
            elif block.type == "image_placeholder":
                image_placeholder_count +=1
                print(f"      Image ID Ref: {block.image_id_ref}")
            elif block.type == "code_snippet":
                code_snippet_count += 1
                print(f"      Code ({block.code_language or 'unknown'}):\n        '''{code_preview}'''")
            elif block.type == "table_placeholder":
                table_placeholder_count += 1
                has_html = "Yes" if block.custom_attributes and block.custom_attributes.get('html_content') else "No"
                print(f"      Table HTML stored in custom_attributes: {has_html}")
        
        print(f"    Total Text Blocks: {text_block_count}")
        print(f"    Total Heading Blocks: {heading_block_count}")
        print(f"    Total List Item Blocks: {list_item_block_count}")
        print(f"    Total Image Placeholders: {image_placeholder_count}")
        print(f"    Total Code Snippet Blocks: {code_snippet_count}")
        print(f"    Total Table Placeholders: {table_placeholder_count}")

        is_order_sequential = all(preliminary_blocks[i].order == i for i in range(len(preliminary_blocks)))
        print(f"    PreliminaryBlock.order assignment is sequential and correct: {is_order_sequential}")


        print(f"\n  --- RawImageInputs ({len(raw_images)}) ---")
        for i, img_input in enumerate(raw_images):
            print(f"    Image {i}: ID={img_input.image_id}")
            print(f"      Source URL: {img_input.source_url}")
            print(f"      Alt Text: {img_input.alt_text}")
            print(f"      Caption: {img_input.caption}")
            # print(f"      GCS Path Components: job_id='{img_input.job_id_for_gcs_path}', source_type='{img_input.source_type_for_gcs_path}', original_source='{img_input.original_source_identifier_for_gcs_path}/{img_input.original_filename}'")

    elif actual_success_status == False: # Explicitly check for False
        print(f"  Status: Failed")
        print(f"  Error Message: {service_result.error_message}")
        if service_result.error_details and isinstance(service_result.error_details, dict):
            original_data = service_result.error_details.get("original_data")
            if isinstance(original_data, tuple) and len(original_data) == 3:
                _, meta_on_fail, _ = original_data # Unpack tuple
                if meta_on_fail and isinstance(meta_on_fail, DocumentMetadata):
                    print(f"  Source Identifier (on fail): {meta_on_fail.source_identifier}")
                    print(f"  Final URL (on fail): {meta_on_fail.final_url}")
                    print(f"  Custom Fields (on fail): {meta_on_fail.custom_fields}")
            else:
                print(f"  Error Details: {service_result.error_details}")
        elif service_result.error_details: # Print if not the expected dict/tuple structure
            print(f"  Error Details: {service_result.error_details}")

    else: # Handle cases where result.success is True but data is not as expected
            print(f"  Status: Success but data is unexpected or None.")
            print(f"  Result data: {service_result.data}")


    print("\n--- Test Complete ---")


async def main():
    test_urls = [

        # Medium article (check for paywall/content extraction)
        "https://arxiv.org/pdf/1501.05039",
        # Another Medium article - was malformed in previous list, now corrected
    
    ]

    for url in test_urls:
        test_job_id = f"test_web_{uuid.uuid4().hex[:6]}"
        await run_web_acquisition_test(url=url, job_id=test_job_id)
        print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main()) 