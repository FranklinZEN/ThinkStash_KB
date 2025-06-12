import time
from typing import Optional, List, Dict, Union, Any
import logging
import uuid # Added for generating new block_ids
import json # Added for robust JSON handling

from pydantic import BaseModel, Field

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.orchestration_models import ContentBlock
from aiservice.app.models.content_structuring_models import ContentStructuringServiceInput
from aiservice.app.models.pipeline_models import PreliminaryBlock, EnrichedImageMetadata, DocumentMetadata
# from ..tools.content_processing_tools import TextToBlocksTool # Assuming this will be correctly structured
from aiservice.app.config.settings import Settings

class ContentStructuringService(BaseService):
    """
    Transforms PreliminaryBlocks and EnrichedImageMetadata into a list of ContentBlocks
    using deterministic Python logic.
    """
    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        if self.settings and hasattr(self.settings, 'debug_mode') and self.settings.debug_mode:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

    # _map_structured_block_to_content_block is removed as it was LLM-specific.
    # Transformation logic will be directly in execute.

    async def execute(self, service_input: ContentStructuringServiceInput) -> ServiceResult[List[ContentBlock]]:
        start_time = time.time()
        final_content_blocks: List[ContentBlock] = []
        try: 
            if not service_input:
                self.logger.error("Service input is None.")
                return ServiceResult.failure(data=[], error_message="Service input is None.")

            current_user_id = service_input.user_id
            current_document_id = service_input.document_metadata.document_id if service_input.document_metadata else None
            if not current_document_id and service_input.job_id:
                 self.logger.warning(f"document_metadata.document_id not found, using job_id {service_input.job_id} as document_id.")
                 current_document_id = service_input.job_id

            # Added Debug Logging
            self.logger.debug(f"CSS Execute: Determined current_user_id: '{current_user_id}'")
            self.logger.debug(f"CSS Execute: Determined current_document_id: '{current_document_id}'")

            if service_input.preliminary_blocks is None:
                self.logger.error("service_input.preliminary_blocks is None.")
                return ServiceResult.failure(data=[], error_message="Preliminary blocks list is None.")

            enriched_images_map: Dict[str, EnrichedImageMetadata] = {}
            if service_input.enriched_images:
                self.logger.debug(f"Received {len(service_input.enriched_images)} enriched images. Converting list to map.")
                for img in service_input.enriched_images:
                    if hasattr(img, 'image_id'):
                        enriched_images_map[img.image_id] = img
                    else:
                        self.logger.warning(f"Skipping an item in enriched_images because it lacks an 'image_id': {img}")
            else:
                self.logger.warning("Enriched images list is None or empty.")
                

            if not service_input.preliminary_blocks:
                return ServiceResult.success(data=[])

            active_lists_stack: List[Dict[str, Any]] = []
            
            def get_common_block_args(p_block: PreliminaryBlock) -> Dict[str, Any]:
                return {
                    "tmp_id": p_block.block_id,
                    "user_id": current_user_id,
                    "document_id": current_document_id,
                    "order_index": p_block.order,
                    "page_number": p_block.page_number,
                    "bbox": p_block.bbox
                }

            def create_list_content_block(list_data: Dict[str, Any], first_list_item_p_block: PreliminaryBlock) -> ContentBlock:
                common_args = get_common_block_args(first_list_item_p_block)
                # For list block, tmp_id can reference the p_block.block_id of the first item that started the list
                common_args["tmp_id"] = list_data['block_id_prefix'] # p_block.block_id of the first list item

                return ContentBlock(
                    block_id=str(uuid.uuid4()),
                    type='list',
                    items=list_data['items'],
                    ordered=list_data['ordered'],
                    **common_args 
                )

            try:
                for p_block in sorted(service_input.preliminary_blocks, key=lambda b: b.order):
                    common_args = get_common_block_args(p_block)

                    # This is the start of the corrected logic.
                    # It's a single if/elif/else chain to prevent duplication.
                    if p_block.type in ['text', 'heading', 'code_snippet', 'math_text', 'image_placeholder', 'table_placeholder']:
                        # This logic now correctly runs *inside* the check for non-list items.
                        # It closes any open lists before adding a new block.
                        while active_lists_stack:
                            final_list_data = active_lists_stack.pop()
                            p_block_ref_for_list = final_list_data.get('p_block_ref')
                            if not p_block_ref_for_list:
                                self.logger.critical(f"Could not find p_block_ref for list. Skipping list construction.")
                                continue
                            
                            list_cb = create_list_content_block(final_list_data, p_block_ref_for_list)
                            if active_lists_stack:
                                active_lists_stack[-1]['items'].append(list_cb.model_dump(exclude_none=True))
                            else:
                                final_content_blocks.append(list_cb)

                        # Now, process the specific block type.
                        if p_block.type == 'text':
                            final_content_blocks.append(ContentBlock(block_id=str(uuid.uuid4()), type='text', content=p_block.text_content, **common_args))
                        elif p_block.type == 'heading':
                            final_content_blocks.append(ContentBlock(block_id=str(uuid.uuid4()), type='heading', content=p_block.text_content, level=p_block.heading_level, **common_args))
                        elif p_block.type == 'code_snippet':
                            final_content_blocks.append(ContentBlock(block_id=str(uuid.uuid4()), type='code_snippet', content=p_block.code_content, language=p_block.code_language, **common_args))
                        elif p_block.type == 'math_text': 
                            final_content_blocks.append(ContentBlock(block_id=str(uuid.uuid4()), type='math', content=p_block.text_content, **common_args))
                        elif p_block.type == 'image_placeholder':
                            if p_block.image_id_ref and p_block.image_id_ref in enriched_images_map:
                                enriched_img = enriched_images_map[p_block.image_id_ref]
                                final_content_blocks.append(ContentBlock(
                                    block_id=str(uuid.uuid4()), 
                                    type='image',
                                    image_id_ref=enriched_img.image_id, 
                                    gcs_url=enriched_img.gcs_url,
                                    alt_text=enriched_img.alt_text,
                                    caption=enriched_img.caption,
                                    llm_description=enriched_img.llm_description,
                                    width=enriched_img.width,
                                    height=enriched_img.height,
                                    **common_args
                                ))
                            else:
                                self.logger.warning(f"CSS: Skipping image_placeholder for ID '{p_block.image_id_ref}' as it was not found in enriched_images_map.")
                        elif p_block.type == 'table_placeholder':
                            table_html = p_block.custom_attributes.get('html_content') if p_block.custom_attributes else None
                            final_content_blocks.append(ContentBlock(block_id=str(uuid.uuid4()), type='table', content=table_html, **common_args))

                    elif p_block.type == 'list_item':
                        item_content = p_block.list_item_data if p_block.list_item_data is not None else p_block.text_content
                        if item_content is None: item_content = ""

                        current_item_level = p_block.list_level if p_block.list_level is not None else 0
                        
                        while active_lists_stack and active_lists_stack[-1]['level'] > current_item_level:
                            final_list_data = active_lists_stack.pop()
                            p_block_ref_for_list = final_list_data.get('p_block_ref')
                            if not p_block_ref_for_list: 
                                self.logger.critical(f"(Inner loop) Could not find p_block_ref for list. Skipping list construction.")
                                continue
                            list_cb = create_list_content_block(final_list_data, p_block_ref_for_list)
                            if active_lists_stack:
                                active_lists_stack[-1]['items'].append(list_cb.model_dump(exclude_none=True))
                            else:
                                final_content_blocks.append(list_cb)

                        if not active_lists_stack or \
                           active_lists_stack[-1]['level'] != current_item_level or \
                           active_lists_stack[-1]['ordered'] != p_block.list_ordered:
                            
                            if active_lists_stack and active_lists_stack[-1]['level'] == current_item_level:
                                final_list_data = active_lists_stack.pop()
                                p_block_ref_for_list = final_list_data.get('p_block_ref')
                                if not p_block_ref_for_list:
                                    self.logger.critical(f"(After type check) Could not find p_block_ref for list. Skipping list construction.")
                                    continue
                                list_cb = create_list_content_block(final_list_data, p_block_ref_for_list)
                                if active_lists_stack:
                                     active_lists_stack[-1]['items'].append(list_cb.model_dump(exclude_none=True))
                                else:
                                    final_content_blocks.append(list_cb)
                            
                            new_list_data = {
                                'level': current_item_level,
                                'ordered': p_block.list_ordered,
                                'items': [],
                                'block_id_prefix': p_block.block_id.rsplit('_li', 1)[0] if '_li' in p_block.block_id else p_block.block_id,
                                'p_block_ref': p_block
                            }
                            active_lists_stack.append(new_list_data)
                        
                        active_lists_stack[-1]['items'].append(str(item_content))
                    
                    else:
                        self.logger.warning(f"Unsupported PreliminaryBlock Type: {p_block.type}. Treating as plain text.")
                        final_content_blocks.append(ContentBlock(block_id=str(uuid.uuid4()), type='text', content=f"{p_block.text_content or p_block.code_content or ''}".strip(), **common_args))

                # After the loop, close any remaining open lists.
                while active_lists_stack:
                    final_list_data = active_lists_stack.pop()
                    p_block_ref_for_list = final_list_data.get('p_block_ref')
                    if not p_block_ref_for_list:
                        self.logger.critical(f"(Final loop) Could not find p_block_ref for list. Skipping list construction.")
                        continue
                    list_cb = create_list_content_block(final_list_data, p_block_ref_for_list)
                    if active_lists_stack: 
                        active_lists_stack[-1]['items'].append(list_cb.model_dump(exclude_none=True))
                    else: 
                        final_content_blocks.append(list_cb)

            except Exception as e_structuring_loop:
                problematic_block_details = "Unknown (error before first iteration)"
                if 'p_block' in locals() and p_block:
                    try:
                        problematic_block_details = p_block.model_dump_json()
                    except Exception:
                        problematic_block_details = f"Could not serialize p_block: {str(p_block)}"
                
                error_msg = f"Error during content structuring loop. Last p_block (approx): {problematic_block_details}. Exception: {type(e_structuring_loop).__name__}: {str(e_structuring_loop)}"
                self.logger.critical(f"{error_msg}", exc_info=True)
                return ServiceResult.failure(data=final_content_blocks, error_message=error_msg)
            
            duration = time.time() - start_time
            self.logger.info(f"ContentStructuringService finished successfully in {duration:.2f}s. Blocks created: {len(final_content_blocks)}.")
            return ServiceResult.success(data=final_content_blocks)

        except Exception as e_outer_execute:
            error_message = f"Outer exception in ContentStructuringService.execute: {type(e_outer_execute).__name__}: {str(e_outer_execute)}"
            input_summary = "service_input was None or unavailable for summary"
            if 'service_input' in locals() and service_input:
                try:
                    input_summary = f"Preliminary Blocks Count: {len(service_input.preliminary_blocks) if service_input.preliminary_blocks else 'None/0'}, Enriched Images Count: {len(service_input.enriched_images) if service_input.enriched_images else 'None/0'}"
                except:
                    input_summary = "Error summarizing service_input fields."
            
            full_error_message = f"{error_message if error_message else 'Outer exception with no specific message'}. Input summary: {input_summary}"
            self.logger.critical(f"FATAL ERROR in ContentStructuringService: {full_error_message}", exc_info=True)
            return ServiceResult.failure(data=final_content_blocks, error_message=full_error_message if full_error_message else "Outer unknown error in CSS")

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