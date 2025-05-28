# Placeholder for TS-AI-Reconstruct-5: Content Consolidation & Structuring Agent 

from crewai import Agent, Task
from typing import List, Type, Dict, Any, Optional
from pydantic import BaseModel
import json # For loading data from DataStore and for LLM tool output

# Tool Imports
from app.tools.utility_tools import DataStoreAccessTool
from app.tools.llm_interaction_tools import AdvancedLLMStructuringTool

# Model Imports
from app.models.content_structuring_models import ContentStructuringInput, ContentStructuringOutput
# ContentBlock for output, ProcessedImageData for input image list items
from app.models.orchestration_models import ContentBlock, ProcessedImageData 

class ContentConsolidationStructuringAgent:
    """Final content assembly: LLM-based text/math/code segmentation, image placeholder insertion, and gallery appending (V2.4)."""

    def __init__(self, 
                 advanced_llm_structuring_tool: AdvancedLLMStructuringTool, 
                 data_store_tool: DataStoreAccessTool):
        
        self.advanced_llm_structuring_tool = advanced_llm_structuring_tool
        self.data_store_tool = data_store_tool
        
        agent_tools = [self.advanced_llm_structuring_tool, self.data_store_tool]
        self.agent_instance = self._create_agent_instance(agent_tools)

    def _create_agent_instance(self, configured_tools: List[BaseModel]) -> Agent:
        return Agent(
            role='Content Consolidation and Structuring Agent for V2.4',
            goal=('Retrieve processed text and image data. Use an LLM (AdvancedLLMStructuringTool) to segment text into text/math/code blocks ' 
                  'and insert image placeholders like [Image Reference: ORIGINAL_SOURCE_IDENTIFIER]. ' 
                  'Append a gallery of image blocks. Detect if content is a long article. Return final structured content blocks and flags.'),
            backstory=(
                "You are the final assembler in the CoreReconstructionCrew. You receive references to the main textual content and a list of fully processed image data (with GCS URLs and original IDs). "
                "First, you retrieve this data using the DataStoreAccessTool. Then, you employ the AdvancedLLMStructuringTool, providing it with the text content and hints from the image data (IDs, captions). "
                "The LLM's task is to segment the text into logical 'text', 'math', and 'code' blocks, and strategically insert textual placeholders (e.g., [Image Reference: PDF_PAGE1_IMG1]) where images belong. "
                "After the LLM processing, you take the list of ProcessedImageData, convert each into a standard 'image' block (including gcs_url, original_source_identifier, caption, etc.), and append these to the end of the blocks received from the LLM, forming an image gallery. "
                "You also determine if the article is long. Your output is the complete list of content blocks ready for API response and an is_long_article flag."
            ),
            tools=configured_tools,
            verbose=True,
            allow_delegation=False # Uses its tools directly for specific structuring tasks
        )

    def get_agent(self) -> Agent:
        return self.agent_instance

    # --- Agent's Core Logic Method ---
    def execute_content_structuring(self, input_data: ContentStructuringInput) -> ContentStructuringOutput:
        print(f"ContentStructuringAgent: Starting for text_ref: {input_data.extracted_text_content_ref}, image_list_ref: {input_data.processed_image_data_list_ref}")
        
        llm_processed_blocks_dicts: List[Dict[str, Any]] = [] 
        final_gallery_image_blocks_dicts: List[Dict[str, Any]] = []
        is_long_article = False
        status = "success"
        error_message: Optional[str] = None

        text_content: Optional[str] = None
        processed_images_data_list: List[ProcessedImageData] = []
        try:
            if input_data.extracted_text_content_ref: # Only try to get text if ref exists
                text_content = self.data_store_tool._run(action="get", key=input_data.extracted_text_content_ref)
            
            if not text_content and not input_data.processed_image_data_list_ref:
                 # No text and no images at all, this might be an upstream issue or empty source
                print(f"ContentStructuringAgent: No text content at ref {input_data.extracted_text_content_ref} and no image ref provided.")
                status = "error_retrieving_data" # Or a more specific status like "empty_source_input"
                error_message = "No text or image data references provided to structure."
                return ContentStructuringOutput(status=status, error_message=error_message, final_original_content_blocks=[])
            elif not text_content:
                 print(f"ContentStructuringAgent: No text content found. Will proceed with gallery only if images exist.")

            if input_data.processed_image_data_list_ref:
                image_data_stored = self.data_store_tool._run(action="get", key=input_data.processed_image_data_list_ref)
                if image_data_stored:
                    loaded_images_raw = json.loads(image_data_stored) if isinstance(image_data_stored, str) else image_data_stored
                    if isinstance(loaded_images_raw, list):
                        for img_dict in loaded_images_raw:
                            if isinstance(img_dict, dict):
                                processed_images_data_list.append(ProcessedImageData(**img_dict))
                            else:
                                print(f"Warning: Skipping non-dict item in image_data_list: {img_dict}")
                    else:
                        print(f"Warning: Expected list from processed_image_data_list_ref, got {type(loaded_images_raw)}.")
        except Exception as e_retrieve:
            print(f"ContentStructuringAgent: Error retrieving data: {e_retrieve}")
            return ContentStructuringOutput(status="error_retrieving_data", error_message=str(e_retrieve), final_original_content_blocks=[])

        if text_content: # Proceed with LLM structuring only if there is text
            image_reference_hints = []
            if processed_images_data_list:
                for img_data in processed_images_data_list:
                    hint = {"original_source_identifier": img_data.original_source_identifier,
                            "caption": img_data.caption, "description": img_data.llm_description, 
                            "alt_text": img_data.alt_text}
                    image_reference_hints.append({k: v for k, v in hint.items() if v is not None}) # Add only if value exists
            try:
                print(f"ContentStructuringAgent: Calling AdvancedLLMStructuringTool with {len(image_reference_hints)} image hints.")
                llm_output_json_str = self.advanced_llm_structuring_tool._run(
                    source_document_text=text_content,
                    image_details_list=image_reference_hints,
                    source_content_type_hint=input_data.source_content_type_hint,
                    page_title=input_data.page_title_from_acquisition
                )
                if llm_output_json_str:
                    parsed_blocks = json.loads(llm_output_json_str)
                    if isinstance(parsed_blocks, list):
                        llm_processed_blocks_dicts.extend(parsed_blocks)
                    else:
                        # LLM tool should always return a list (even if empty or error block)
                        raise ValueError(f"AdvancedLLMStructuringTool returned non-list JSON: {type(parsed_blocks)}")
                else:
                    raise ValueError("AdvancedLLMStructuringTool returned empty or None output.")

            except Exception as e_llm:
                print(f"ContentStructuringAgent: Error during LLM structuring or parsing its output: {e_llm}")
                # Fallback: use raw text as a single text block
                llm_processed_blocks_dicts.append(ContentBlock(type="text", content=text_content).model_dump())
                status = "error_llm_structuring"
                error_message = f"LLM structuring/parsing failed: {str(e_llm)}. Using raw text block."
        
        elif not text_content and processed_images_data_list: # No text, but images exist, create placeholder text
            llm_processed_blocks_dicts.append(ContentBlock(type="text", content="(This content consists primarily of images presented in the gallery below.)").model_dump())
        elif not text_content and not processed_images_data_list: # Should have been caught by earlier check
            llm_processed_blocks_dicts.append(ContentBlock(type="text", content="(No textual content or images to display.)").model_dump())
            if status == "success": status = "success_empty_content" 

        # 3. Append Image Gallery
        try:
            if processed_images_data_list:
                for img_data in processed_images_data_list:
                    gallery_image_block_dict = ContentBlock(
                        type="image",
                        original_source_identifier=img_data.original_source_identifier,
                        gcs_url=img_data.gcs_url,
                        alt_text=img_data.alt_text,
                        caption=img_data.caption,
                        llm_description=img_data.llm_description,
                        # Assuming ContentBlock model might have fields for dimensions/mime_type or an 'attributes' dict
                        # Example: attributes={"dimensions": img_data.dimensions, "mime_type": img_data.mime_type} if ContentBlock supports it
                    ).model_dump()
                    final_gallery_image_blocks_dicts.append(gallery_image_block_dict)
        except Exception as e_gallery:
            print(f"ContentStructuringAgent: Error appending image gallery: {e_gallery}")
            if status == "success": status = "error_gallery_append"
            error_message = (error_message + "; " if error_message else "") + f"Gallery appending error: {str(e_gallery)}"

        final_combined_blocks_dicts = llm_processed_blocks_dicts + final_gallery_image_blocks_dicts

        if not final_combined_blocks_dicts and status == "success": # If somehow ended up with no blocks but no error yet
            final_combined_blocks_dicts.append(ContentBlock(type="text", content="(Processed content is empty.)").model_dump())
            status = "success_empty_content" # More specific than generic success if blocks are empty

        # 4. Detect Long Article
        if text_content and len(text_content) > 3000: 
            is_long_article = True 

        return ContentStructuringOutput(
            final_original_content_blocks=final_combined_blocks_dicts,
            is_long_article_flag=is_long_article,
            status=status,
            error_message=error_message
        )

    # --- Task Definition for Agent (Conceptual) ---
    def task_structure_and_finalize_content(self, agent_to_use: Agent, input_data: ContentStructuringInput) -> Task:
        return Task(
            description=(
                f"Structure and finalize content using text_ref: {input_data.extracted_text_content_ref} and image_list_ref: {input_data.processed_image_data_list_ref}. "
                f"Retrieve data, use AdvancedLLMStructuringTool for text segmentation and image placeholder insertion. Append image gallery. Detect long article."
            ),
            expected_output=(
                "A ContentStructuringOutput model as a dictionary, containing the final_original_content_blocks list and is_long_article_flag, status, and error_message."
            ),
            agent=agent_to_use,
            # arguments=input_data.model_dump()
        )

# Agent-specific methods for preparing inputs for the LLM, post-processing LLM output,
# or handling complex structuring logic can be added here.
# def structure_document(self, source_text_with_markers, image_data_list, source_hint):
#     # 1. Prepare prompt for LLM based on inputs
#     # 2. Call LLM (via tool or directly)
#     # 3. Validate and parse LLM JSON output
#     # 4. Return structured content blocks
#     pass

# Methods for input handling, marker replacement, LLM-driven structuring, and output formatting will be added. 