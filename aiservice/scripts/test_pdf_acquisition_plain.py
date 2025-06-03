import asyncio
import logging
import os
import sys
from typing import List, Tuple

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput
from aiservice.app.services.base import ServiceResult

# --- Configuration ---
# IMPORTANT: Replace this with an actual path to a PDF file for testing
TEST_PDF_PATH = r"E:\ThinkStash\documentation\AI Agents Testing File\technical-guide-to-scaling-gen-ai.pdf" # <<< REPLACE THIS
# TEST_PDF_PATH = "path/to/your/test.pdf" # Example

async def run_pdf_acquisition_test(pdf_path: str):
    print(f"--- Testing PDFAcquisitionService with: {pdf_path} ---")

    if not os.path.exists(pdf_path):
        print(f"ERROR: Test PDF file not found at {pdf_path}")
        print("Please update TEST_PDF_PATH in the script with a valid PDF file path.")
        return

    service_input = PDFAcquisitionServiceInput(
        file_path=pdf_path,
        processing_level="full_content", # or "text_only"
        job_id="test_pdf_job_001"
    )

    # Instantiate the service (no special settings or tools needed for this iteration)
    pdf_service = PDFAcquisitionService(settings=None)

    service_result: ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]] = await pdf_service.execute(service_input)

    if service_result.success:
        preliminary_blocks, doc_metadata, raw_images = service_result.data
        
        print("\\n--- DocumentMetadata ---")
        if doc_metadata:
            print(f"  Document ID: {doc_metadata.document_id}")
            print(f"  Title: {doc_metadata.title}")
            print(f"  Source: {doc_metadata.source_identifier}")
            print(f"  Total Pages: {doc_metadata.total_pages}")
            print(f"  Author: {doc_metadata.author}")
            print(f"  Creation Date: {doc_metadata.creation_date}")
            print(f"  Modification Date: {doc_metadata.modification_date}")
            print(f"  Extracted At: {doc_metadata.extracted_at}")
        else:
            print("  DocumentMetadata not found.")

        print(f"\\n--- PreliminaryBlocks ({len(preliminary_blocks)}) ---")
        text_block_count = 0
        image_placeholder_count = 0
        heading_count = 0
        list_item_count = 0
        ordered_blocks_ok = True

        for i, block in enumerate(preliminary_blocks):
            print(f"  Block {i}: ID={block.block_id}, Type='{block.type}', Page={block.page_number}, Order={block.order}")
            if block.type == "text":
                text_block_count += 1
                display_text = block.text_content[:60].replace('\n', ' ')
                print(f"    Text: '{display_text}' ...")
            elif block.type == "heading":
                heading_count += 1
                display_text = block.text_content[:60].replace('\n', ' ')
                print(f"    Heading (L{block.heading_level}): '{display_text}' ...")
            elif block.type == "list_item":
                list_item_count += 1
                display_text = str(block.list_item_data)[:60].replace('\n', ' ')
                print(f"    ListItem (Ordered: {block.list_ordered}, Level: {block.list_level}): '{display_text}' ...")
            elif block.type == "image_placeholder":
                image_placeholder_count += 1
                print(f"    Image ID Ref: {block.image_id_ref}")
            
            if block.order != i:
                ordered_blocks_ok = False
        
        print(f"  Total Text Blocks: {text_block_count}")
        print(f"  Total Heading Blocks: {heading_count}")
        print(f"  Total List Item Blocks: {list_item_count}")
        print(f"  Total Image Placeholders: {image_placeholder_count}")
        
        if ordered_blocks_ok:
            print("  PreliminaryBlock.order assignment is sequential and correct.")
        else:
            print("  ERROR: PreliminaryBlock.order assignment is NOT sequential or incorrect.")

        print(f"\\n--- RawImageInputs ({len(raw_images)}) ---")
        raw_image_ids = set()
        for i, raw_image in enumerate(raw_images):
            raw_image_ids.add(raw_image.image_id)
            print(f"  Image {i}: ID={raw_image.image_id}, Page={raw_image.page_number}, MIME={raw_image.mime_type}, Size={len(raw_image.image_bytes or b'')} bytes")
            print(f"    Original Filename: {raw_image.original_filename}")
            print(f"    GCS Path Components: job_id='{raw_image.job_id_for_gcs_path}', source_type='{raw_image.source_type_for_gcs_path}', original_source='{raw_image.original_source_identifier_for_gcs_path}'")
            if raw_image.bbox:
                 print(f"    BBox: {raw_image.bbox}")

        print("\\n--- Verifications ---")
        all_refs_found = True
        for block in preliminary_blocks:
            if block.type == "image_placeholder":
                if block.image_id_ref not in raw_image_ids:
                    print(f"  ERROR: image_id_ref '{block.image_id_ref}' in PreliminaryBlock '{block.block_id}' not found in RawImageInput IDs.")
                    all_refs_found = False
        if all_refs_found and image_placeholder_count > 0:
            print("  All image_id_refs in image_placeholders successfully match RawImageInput IDs.")
        elif image_placeholder_count == 0:
            print("  No image placeholders to verify against RawImageInput IDs.")
        else:
            print("  ERROR: Some image_id_refs in image_placeholders do NOT match RawImageInput IDs.")

    else:
        print("\\n--- Service Execution Failed ---")
        print(f"  Error: {service_result.error_message}")
        if service_result.error_details:
            print(f"  Details: {service_result.error_details}")

    print("\\n--- Test Complete ---")

if __name__ == "__main__":
    # IMPORTANT: Ensure TEST_PDF_PATH is correctly set above!
    if TEST_PDF_PATH == "path/to/your/test.pdf" or not os.path.exists(TEST_PDF_PATH):
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERROR: TEST_PDF_PATH is not set or the file does not exist.          !!!")
        print("!!! Please edit 'aiservice/scripts/test_pdf_acquisition_plain.py'        !!!")
        print("!!! and update the TEST_PDF_PATH variable with a valid PDF file.         !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        asyncio.run(run_pdf_acquisition_test(TEST_PDF_PATH)) 