import time
from typing import Optional, List, Dict, Union, Any # Added Union
import sys

from pydantic import BaseModel, Field # BaseModel, Field might not be needed directly if service input is from another file

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.orchestration_models import ContentBlock # Final output block model
# Import the new input model
from aiservice.app.models.content_structuring_models import ContentStructuringServiceInput
# Import models needed for input processing
from aiservice.app.models.pipeline_models import PreliminaryBlock, EnrichedImageMetadata, DocumentMetadata # Added DocumentMetadata

from aiservice.app.config.settings import Settings # Settings might still be used for other configs
# Removed LLM related imports: MinimalLLMCrew, StructuredContentBlock, ContentStructuringInput (old), ContentStructuringOutput

class ContentStructuringService(BaseService):
    """
    Transforms PreliminaryBlocks and EnrichedImageMetadata into a list of ContentBlocks
    using deterministic Python logic.
    """
    def __init__(self, settings: Optional[Any] = None): # Removed minimal_llm_crew
        super().__init__(settings)
        # No crew initialization needed

    # _map_structured_block_to_content_block is removed as it was LLM-specific.
    # Transformation logic will be directly in execute.

    async def execute(self, service_input: ContentStructuringServiceInput) -> ServiceResult[List[ContentBlock]]:
        start_time = time.time()
        # Outer try-except to catch any unhandled error within execute
        try: 
            final_content_blocks: List[ContentBlock] = []
            
            if not service_input:
                print("ERROR ContentStructuringService: Service input is None.", file=sys.stderr)
                return ServiceResult.failure(data=[], error_message="Service input is None.")

            if service_input.preliminary_blocks is None:
                # This implies an issue upstream or incorrect input formation.
                print("ERROR ContentStructuringService: service_input.preliminary_blocks is None.", file=sys.stderr)
                return ServiceResult.failure(data=[], error_message="Preliminary blocks list is None.")

            if service_input.enriched_images is None:
                print("ERROR ContentStructuringService: Enriched images list is None. This might cause issues.", file=sys.stderr)
                # Depending on logic, this might be fatal or recoverable if no image_placeholders exist.
                # For now, proceeding but logging error. Downstream image linking will fail.
                enriched_images_map: Dict[str, EnrichedImageMetadata] = {}
            else:
                enriched_images_map: Dict[str, EnrichedImageMetadata] = \
                    {img.image_id: img for img in service_input.enriched_images}

            if not service_input.preliminary_blocks: # Check again after enriched_images_map init
                return ServiceResult.success(data=[])

            # Helper to handle list item aggregation
            current_list_items: List[Union[str, Dict[str, Any]]] = []
            current_list_level: Optional[int] = None
            current_list_ordered: Optional[bool] = None
            current_list_block_id_prefix: Optional[str] = None
            current_list_page_number: Optional[int] = None
            current_list_bbox: Optional[List[float]] = None # Bbox for the whole list can be complex; might take first item's

            def finalize_current_list():
                nonlocal current_list_items, current_list_level, current_list_ordered, final_content_blocks
                nonlocal current_list_block_id_prefix, current_list_page_number, current_list_bbox
                if current_list_items:
                    list_block = ContentBlock(
                        block_id=f"{current_list_block_id_prefix}_list", # Generate a new ID for the list block
                        type='list',
                        items=current_list_items,
                        ordered=current_list_ordered,
                        page_number=current_list_page_number, # Page of the first item
                        bbox=current_list_bbox # Bbox of the first item, or combined
                        # level for the list block itself is not typical in ContentBlock; levels are per item.
                        # list_start_number might be derived if needed based on item content
                    )
                    final_content_blocks.append(list_block)
                    current_list_items = []
                    current_list_level = None
                    current_list_ordered = None
                    current_list_block_id_prefix = None
                    current_list_page_number = None
                    current_list_bbox = None
            
            try:
                for p_block in sorted(service_input.preliminary_blocks, key=lambda b: b.order):
                    # If we encounter a non-list item, finalize any ongoing list
                    if p_block.type != 'list_item':
                        finalize_current_list()

                    if p_block.type == 'text':
                        final_content_blocks.append(ContentBlock(
                            block_id=p_block.block_id, type='text', content=p_block.text_content,
                            page_number=p_block.page_number, bbox=p_block.bbox
                        ))
                    elif p_block.type == 'heading':
                        final_content_blocks.append(ContentBlock(
                            block_id=p_block.block_id, type='heading', content=p_block.text_content,
                            level=p_block.heading_level, page_number=p_block.page_number, bbox=p_block.bbox
                        ))
                    elif p_block.type == 'code_snippet':
                        final_content_blocks.append(ContentBlock(
                            block_id=p_block.block_id, type='code_snippet', content=p_block.code_content,
                            language=p_block.code_language, page_number=p_block.page_number, bbox=p_block.bbox
                        ))
                    elif p_block.type == 'math_text': # Assuming 'math_text' in PreliminaryBlock maps to 'math' in ContentBlock
                        final_content_blocks.append(ContentBlock(
                            block_id=p_block.block_id, type='math', content=p_block.text_content, # ContentBlock calls it 'math'
                            page_number=p_block.page_number, bbox=p_block.bbox
                        ))
                    elif p_block.type == 'image_placeholder':
                        if p_block.image_id_ref and p_block.image_id_ref in enriched_images_map:
                            enriched_img = enriched_images_map[p_block.image_id_ref]
                            final_content_blocks.append(ContentBlock(
                                block_id=p_block.block_id, # Use prelim block's ID for the image block
                                type='image',
                                image_id_ref=enriched_img.image_id, # Corresponds to EnrichedImageMetadata.image_id
                                gcs_url=enriched_img.gcs_url,
                                alt_text=enriched_img.alt_text,
                                caption=enriched_img.caption,
                                llm_description=enriched_img.llm_description,
                                width=enriched_img.width,
                                height=enriched_img.height,
                                page_number=p_block.page_number, # From placeholder
                                bbox=p_block.bbox              # From placeholder
                            ))
                        else:
                            # Placeholder for an image whose metadata wasn't found
                            final_content_blocks.append(ContentBlock(
                                block_id=p_block.block_id, type='text', 
                                content=f"[Image Placeholder: ID {p_block.image_id_ref} not found in enriched_images]",
                                page_number=p_block.page_number, bbox=p_block.bbox
                            ))
                    elif p_block.type == 'table_placeholder':
                        table_html = p_block.custom_attributes.get('html_content') if p_block.custom_attributes else None
                        final_content_blocks.append(ContentBlock(
                            block_id=p_block.block_id, type='table', content=table_html, # Store HTML content
                            page_number=p_block.page_number, bbox=p_block.bbox
                        ))
                    elif p_block.type == 'list_item':
                        item_content = p_block.list_item_data if p_block.list_item_data is not None else p_block.text_content
                        
                        if item_content is None: item_content = ""

                        if not current_list_items or \
                           current_list_level != p_block.list_level or \
                           current_list_ordered != p_block.list_ordered:
                            finalize_current_list() 
                            current_list_level = p_block.list_level
                            current_list_ordered = p_block.list_ordered
                            current_list_block_id_prefix = p_block.block_id.rsplit('_li', 1)[0] if '_li' in p_block.block_id else p_block.block_id
                            current_list_page_number = p_block.page_number
                            current_list_bbox = p_block.bbox 
                        
                        current_list_items.append(str(item_content)) 

                    else:
                        final_content_blocks.append(ContentBlock(
                            block_id=p_block.block_id, type='text',
                            content=f"[Unsupported PreliminaryBlock Type: {p_block.type}] {p_block.text_content or p_block.code_content or ''}".strip(),
                            page_number=p_block.page_number, bbox=p_block.bbox
                        ))

                finalize_current_list() # Finalize any remaining list at the end

            except Exception as e_structuring_loop:
                # Log the problematic block and the exception
                problematic_block_details = "Unknown (p_block not available or error before first iteration)"
                if 'p_block' in locals() and p_block:
                    try:
                        problematic_block_details = p_block.model_dump_json() # Or just str(p_block)
                    except Exception as e_dump_block:
                        problematic_block_details = f"Could not serialize p_block: {str(p_block)}, dump error: {e_dump_block}"
                
                error_msg = f"Error during content structuring loop. Last processed/problematic p_block (approx): {problematic_block_details}. Exception: {type(e_structuring_loop).__name__}: {e_structuring_loop}"
                print(f"CRITICAL ContentStructuringService: {error_msg}", file=sys.stderr) # Keep this detailed critical error log
                return ServiceResult.failure(data=final_content_blocks, error_message=error_msg) # Return partial if any
            
            duration = time.time() - start_time
            return ServiceResult.success(data=final_content_blocks)

        except Exception as e_outer_execute: # Catch-all for the entire method
            error_message = f"Outer exception in ContentStructuringService.execute: {type(e_outer_execute).__name__}: {str(e_outer_execute)}"
            # Attempt to get service_input details if available
            input_summary = "service_input was None or unavailable for summary"
            if 'service_input' in locals() and service_input:
                try:
                    input_summary = f"Preliminary Blocks Count: {len(service_input.preliminary_blocks) if service_input.preliminary_blocks else 'None/0'}, Enriched Images Count: {len(service_input.enriched_images) if service_input.enriched_images else 'None/0'}"
                except:
                    input_summary = "Error summarizing service_input fields."
            
            full_error_message = f"{error_message}. Input summary: {input_summary}"
            print(f"FATAL ERROR ContentStructuringService: {full_error_message}", file=sys.stderr)
            # Return a failure, ensure data is an empty list as per ServiceResult generic type for data field if failure.
            return ServiceResult.failure(data=[], error_message=full_error_message) 

# Example usage (conceptual, not run as part of the service file)
# if __name__ == '__main__':
#     # This would require mock objects for PreliminaryBlock, EnrichedImageMetadata, DocumentMetadata
#     # and setting up the service_input.
#     # Example:
#     # service = ContentStructuringService()
#     # mock_prelim_blocks = [ ... create some PreliminaryBlock instances ... ]
#     # mock_enriched_images = [ ... create some EnrichedImageMetadata instances ... ]
#     # mock_doc_metadata = DocumentMetadata(document_id="test_doc", source_identifier="test_source", source_type="test")
    
#     # input_data = ContentStructuringServiceInput(
#     #     preliminary_blocks=mock_prelim_blocks,
#     #     enriched_images=mock_enriched_images,
#     #     document_metadata=mock_doc_metadata,
#     #     job_id="test_job_css"
#     # )
#     # result = asyncio.run(service.execute(input_data))
#     # if result.is_success():
#     #     for cb_idx, cb in enumerate(result.data):
#     #         print(f"ContentBlock {cb_idx}: {cb.model_dump_json(indent=2)}")
#     # else:
#     #     print(f"Error: {result.error_message}") 