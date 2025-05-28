import asyncio
import time
from typing import Optional, Any, List, Dict
import json # Added, as crew.run() might return a string that needs parsing

from pydantic import BaseModel, Field

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.orchestration_models import ProcessedImageData, ContentBlock # Final output block model
from aiservice.app.crews.minimal_crew import MinimalLLMCrew # Import MinimalLLMCrew and its expected output type (StructuredContentBlock from llm_tools)
from aiservice.app.tools.llm_tools import StructuredContentBlock # This is what MinimalLLMCrew.run() should yield

# --- Input Model for ContentStructuringService ---
class ContentStructuringServiceInput(BaseModel):
    raw_text_content: Optional[str] = None
    processed_images: List[ProcessedImageData] = Field(default_factory=list)
    job_id: Optional[str] = Field(None)
    # Potentially add target_schema or specific structuring instructions from orchestrator settings

# Service output is List[ContentBlock], returned via ServiceResult.data

class ContentStructuringService(BaseService):
    """
    Uses MinimalLLMCrew to perform content structuring.
    Handles image placeholder logic by mapping crew output.
    """
    def __init__(self, minimal_llm_crew: MinimalLLMCrew, settings: Optional[Any] = None):
        super().__init__(settings)
        self.minimal_llm_crew = minimal_llm_crew

    def _map_structured_block_to_content_block(self, llm_block: StructuredContentBlock, images_data_map: Dict[str, ProcessedImageData]) -> ContentBlock:
        """Maps the generic StructuredContentBlock from LLM tool to the app's ContentBlock model."""
        if llm_block.type == "image_reference" and llm_block.image_id:
            image_data = images_data_map.get(llm_block.image_id)
            if image_data:
                return ContentBlock(
                    type="image", # V2.4 OrchestrationOutput uses "image" for image blocks
                    original_source_identifier=image_data.original_source_identifier,
                    gcs_url=image_data.gcs_url,
                    alt_text=image_data.alt_text,
                    caption=llm_block.caption or image_data.caption, # Prefer caption from structuring if available
                    llm_description=image_data.llm_description
                )
            else:
                # Image ID from LLM not found in processed images, return as text placeholder
                return ContentBlock(type="text", content=f"[Image Reference (ID Not Found): {llm_block.image_id}]")
        elif llm_block.type == "text":
            return ContentBlock(type="text", content=llm_block.content)
        elif llm_block.type == "code":
            # Assuming code blocks from LLM tool might have language specified in content, e.g. ```python\ncode```
            # Or the tool might return a specific structure. For now, simple text content.
            return ContentBlock(type="code", content=llm_block.content)
        elif llm_block.type == "math":
            return ContentBlock(type="math", content=llm_block.content)
        else:
            # Fallback for unknown types from LLM tool
            return ContentBlock(type="text", content=f"[Unsupported Structured Block Type: {llm_block.type}] {llm_block.content or ''}".strip())

    async def execute(self, service_input: ContentStructuringServiceInput) -> ServiceResult[List[ContentBlock]]:
        start_time = time.time()
        final_content_blocks: List[ContentBlock] = []

        if not service_input.raw_text_content and not service_input.processed_images:
            return ServiceResult.success(data=[]) # Nothing to structure

        # Prepare image metadata for the LLM tool
        image_metadata_for_crew: List[Dict[str, Any]] = []
        images_data_map: Dict[str, ProcessedImageData] = {img.original_source_identifier: img for img in service_input.processed_images}

        for img_data in service_input.processed_images:
            image_metadata_for_crew.append({
                "image_id": img_data.original_source_identifier,
                "caption": img_data.caption, # Caption might come from ImageProcessingService (LLM) or source
                "alt_text": img_data.alt_text,
                "llm_description": img_data.llm_description # Description from ImageProcessingService
            })
        
        # Call the MinimalLLMCrew.run() method
        # CrewAI's kickoff is synchronous. We need to run it in an executor.
        loop = asyncio.get_event_loop()
        try:
            # The MinimalLLMCrew.run method itself should return List[StructuredContentBlock]
            # It handles the parsing of the crew's raw output.
            crew_output_blocks: List[StructuredContentBlock] = await loop.run_in_executor(
                None, 
                self.minimal_llm_crew.run, 
                service_input.raw_text_content or "", 
                image_metadata_for_crew
            )
        except Exception as e_crew_run: # Catch exceptions from running the crew itself
            fallback_content = service_input.raw_text_content or "Error during content structuring crew execution."
            final_content_blocks.append(ContentBlock(type="text", content=fallback_content))
            duration = time.time() - start_time
            return ServiceResult.failure(
                error_message=f"Content structuring crew execution failed: {str(e_crew_run)}",
                error_details={"processing_duration_seconds": duration, "final_blocks": [b.model_dump() for b in final_content_blocks]}
            )

        if not crew_output_blocks:
            log_message = "Content structuring crew returned no blocks."
            if service_input.raw_text_content:
                final_content_blocks.append(ContentBlock(type="text", content=service_input.raw_text_content))
                print(f"ContentStructuringService: WARNING - {log_message} Using raw text as fallback.")
            else: 
                log_message = "Content structuring crew returned no blocks and no initial text was provided."
                final_content_blocks.append(ContentBlock(type="text", content=f"[{log_message}]"))
                print(f"ContentStructuringService: INFO - {log_message}")
            # If returning an empty list is acceptable for "no content", this is success.
            # If it implies an error that the crew should have produced something, this might need to be a failure.
            # For now, consider it success with potentially empty data, logging provides context.
            return ServiceResult.success(data=final_content_blocks)

        for llm_structured_block in crew_output_blocks:
            app_content_block = self._map_structured_block_to_content_block(llm_structured_block, images_data_map)
            final_content_blocks.append(app_content_block)
        
        duration = time.time() - start_time
        print(f"ContentStructuringService: Completed in {duration:.2f}s. Produced {len(final_content_blocks)} blocks using MinimalLLMCrew.")
        return ServiceResult.success(data=final_content_blocks) 