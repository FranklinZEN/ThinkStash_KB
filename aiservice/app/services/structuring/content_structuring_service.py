import time
from typing import Optional, List, Dict, Union, Any
import logging
import uuid # Added for generating new block_ids
import json # Added for robust JSON handling

from pydantic import BaseModel, Field

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.orchestration_models import ContentBlock, InlineContent, BlockProps
from aiservice.app.models.content_structuring_models import ContentStructuringServiceInput
from aiservice.app.models.pipeline_models import PreliminaryBlock, EnrichedImageMetadata, DocumentMetadata, RawImageInput
# from ..tools.content_processing_tools import TextToBlocksTool # Assuming this will be correctly structured
from aiservice.app.config.settings import Settings

class ContentStructuringService(BaseService):
    """
    Transforms PreliminaryBlocks into a list of BlockNote-compliant ContentBlocks.
    """
    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        self.logger = logging.getLogger(__name__)

    async def execute(self, service_input: ContentStructuringServiceInput) -> ServiceResult[List[ContentBlock]]:
        start_time = time.time()
        final_content_blocks: List[ContentBlock] = []
        
        try:
            # 1. --- Input Validation ---
            if not service_input or not service_input.preliminary_blocks:
                self.logger.warning("ContentStructuringService received no preliminary blocks to process.")
                return ServiceResult.success(data=[])

            # 2. --- Prepare Image Maps ---
            enriched_images_map: Dict[str, EnrichedImageMetadata] = {
                img.image_id: img 
                for img in service_input.enriched_images or [] 
                if hasattr(img, 'image_id')
            }
            raw_images_map: Dict[str, RawImageInput] = {
                img.image_id: img
                for img in service_input.raw_images or []
                if hasattr(img, 'image_id')
            }

            # 3. --- Main Transformation Loop ---
            for p_block in sorted(service_input.preliminary_blocks, key=lambda b: b.order):
                block_id = str(uuid.uuid4())
                
                if p_block.type == 'heading':
                    final_content_blocks.append(ContentBlock(
                        id=block_id,
                        type='heading',
                        props=BlockProps(level=p_block.heading_level or 1),
                        content=[InlineContent(type='text', text=p_block.text_content or '')]
                    ))
                
                elif p_block.type == 'text':
                    final_content_blocks.append(ContentBlock(
                        id=block_id,
                        type='paragraph',
                        content=[InlineContent(type='text', text=p_block.text_content or '')]
                    ))

                elif p_block.type == 'code_snippet':
                     final_content_blocks.append(ContentBlock(
                        id=block_id,
                        type='codeBlock',
                        props=BlockProps(language=p_block.code_language or 'plaintext'),
                        content=[InlineContent(type='text', text=p_block.code_content or '')]
                    ))
                
                elif p_block.type == 'list_item':
                    item_text = p_block.list_item_data if isinstance(p_block.list_item_data, str) else p_block.text_content or ''
                    final_content_blocks.append(ContentBlock(
                        id=block_id,
                        type='bulletListItem' if not p_block.list_ordered else 'numberListItem',
                        content=[InlineContent(type='text', text=item_text)],
                        children=[] # For potential nesting in future
                    ))
                
                elif p_block.type == 'image_placeholder':
                    img_ref = p_block.image_id_ref
                    if not img_ref:
                        continue

                    final_url = None
                    caption = ""

                    if img_ref in enriched_images_map:
                        enriched_data = enriched_images_map[img_ref]
                        final_url = enriched_data.gcs_url
                        caption = enriched_data.caption or enriched_data.alt_text or ""
                    
                    # Fallback to raw image URL if GCS processing failed
                    if not final_url and img_ref in raw_images_map:
                        raw_data = raw_images_map[img_ref]
                        final_url = raw_data.source_url
                        self.logger.warning(f"Using fallback raw URL for image '{img_ref}': {final_url}")

                    if final_url:
                        final_content_blocks.append(ContentBlock(
                            id=str(uuid.uuid4()),
                            type='image',
                            props=BlockProps(
                                url=final_url,
                                caption=caption
                            ),
                            content=[] # Image blocks have no inline content
                        ))
                    else:
                        self.logger.warning(f"Could not find a valid URL for image placeholder '{img_ref}' in enriched or raw maps.")
                
                elif p_block.type == 'table_placeholder':
                    final_content_blocks.append(ContentBlock(
                        id=block_id,
                        type='paragraph',
                        content=[InlineContent(type='text', text="[A table was present in the original document.]")]
                    ))
                
                else:
                    self.logger.warning(f"Unsupported PreliminaryBlock Type: {p_block.type}. Skipping.")

            duration = time.time() - start_time
            self.logger.info(f"ContentStructuringService finished successfully in {duration:.2f}s. Blocks created: {len(final_content_blocks)}.")
            return ServiceResult.success(data=final_content_blocks)

        except Exception as e:
            self.logger.critical(f"FATAL ERROR in ContentStructuringService: {e}", exc_info=True)
            return ServiceResult.failure(data=[], error_message=str(e))

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