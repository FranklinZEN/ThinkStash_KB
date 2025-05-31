#!/usr/bin/env python
# coding: utf-8
"""
Tools for AI insight generation crews, including optimized LLM interaction
and fast content block processing.
"""

import json # Added import
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
# import openai # No longer using direct openai client here for default
import uuid # Added for generating block_ids
import json # Add json import

from crewai.tools import BaseTool # Fourth attempt - trying from crewai.tools

# Actual ContentBlock import from its definitive location
from aiservice.app.models.orchestration_models import ContentBlock 

# Corrected import for the settings object
from aiservice.app.config.settings import settings

# Corrected import for ChatGoogleGenerativeAI
from langchain_google_genai import ChatGoogleGenerativeAI # Corrected import location

# Corrected import for ChatOpenAI
from langchain_openai import ChatOpenAI # More direct import path

# --- Optimized LLM Interaction Tool ---

class OptimizedLLMInteractionToolInput(BaseModel):
    """Input for OptimizedLLMInteractionTool."""
    prompt: str = Field(..., description="The prompt to send to the LLM.")
    system_message: Optional[str] = Field(None, description="Optional system message to guide the LLM's behavior.")
    temperature: float = Field(default=0.5, description="Sampling temperature for the LLM.")
    max_tokens: int = Field(default=1024, description="Maximum number of tokens to generate.")
    # Add other relevant LLM parameters as needed (e.g., top_p, frequency_penalty)

class OptimizedLLMInteractionTool(BaseTool):
    name: str = "Optimized LLM Interaction Tool"
    description: str = (
        "Interacts with a configured LLM (e.g., Gemini via OpenAI compatibility) "
        "to get completions for a given prompt. Optimized for speed and directness."
    )
    args_schema: type[BaseModel] = OptimizedLLMInteractionToolInput
    
    llm_client: Optional[Any] = None 
    model_name: Optional[str] = None 

    def __init__(self, llm_client: Optional[Any] = None, **kwargs):
        super().__init__(**kwargs)
        if llm_client: # If an LLM client is passed, use it
            self.llm_client = llm_client
            # Attempt to get model_name from the passed client (ChatOpenAI uses model_name)
            if hasattr(llm_client, 'model_name') and llm_client.model_name:
                self.model_name = llm_client.model_name
            elif hasattr(llm_client, 'model') and llm_client.model: # Fallback for other potential clients
                self.model_name = llm_client.model
            else:
                # If not determinable from client, use the one from settings meant for compatibility layer
                self.model_name = settings.gemini_text_model_compat 
        else: # Default initialization if no client is passed (should ideally not happen if agents get LLM from factory)
            print("OptimizedLLMInteractionTool: Initializing default LLM client. This should ideally be passed from agent.")
            if settings.use_gemini_via_openai_compatibility and \
               settings.gemini_api_key and \
               settings.gemini_text_model_compat and \
               settings.gemini_compatibility_base_url:
                self.llm_client = ChatOpenAI(
                    model_name=settings.gemini_text_model_compat,
                    openai_api_key=settings.gemini_api_key,
                    openai_api_base=settings.gemini_compatibility_base_url,
                    temperature=0.5
                )
                self.model_name = settings.gemini_text_model_compat
            else:
                raise ValueError("OptimizedLLMInteractionTool: Default LLM client init failed. Missing Gemini compatibility settings.")
        
        if not self.model_name:
            print("Warning: OptimizedLLMInteractionTool model_name could not be determined, using compatibility model from settings.")
            self.model_name = settings.gemini_text_model_compat

    def _run(self, prompt: str, system_message: Optional[str] = None, temperature: float = 0.5, max_tokens: int = 1024) -> str:
        """Executes the LLM call using LangChain's .invoke() method."""
        
        # LangChain expects a list of BaseMessage objects or a simple string for user prompt
        # For ChatOpenAI, we construct BaseMessages
        from langchain_core.messages import SystemMessage, HumanMessage

        lc_messages = []
        if system_message:
            lc_messages.append(SystemMessage(content=system_message))
        lc_messages.append(HumanMessage(content=prompt))

        try:
            # Note: temperature and max_tokens for ChatOpenAI are typically set at initialization
            # or can be passed in the .invoke() call if the underlying model/API supports them via passthrough.
            # For ChatOpenAI, these are usually init-time params.
            # We are relying on the temperature set during ChatOpenAI initialization in llm_config.py.
            # If you need per-call temperature/max_tokens with ChatOpenAI, you might need to re-initialize
            # or check if invoke() has passthrough options for these specific params for your endpoint.
            # For now, we will use the client's configured temperature.
            # The `max_tokens` can sometimes be passed in `generation_kwargs` or `model_kwargs` in invoke.
            
            # If the llm_client is ChatOpenAI, it should have a model_name attribute.
            # The self.model_name is used for consistency if we were to switch clients, but ChatOpenAI uses its own model_name.
            print(f"OptimizedLLMInteractionTool: Invoking LLM. Model: {self.llm_client.model_name if hasattr(self.llm_client, 'model_name') else 'N/A'}. Requested max_tokens: {max_tokens}, temperature: {temperature}")
            
            response = self.llm_client.invoke(
                lc_messages,
                max_tokens=max_tokens, # Pass max_tokens here
                temperature=temperature # Pass temperature here
            )
            
            if hasattr(response, 'content'):
                return response.content
            return "Error: No content in LLM response (LangChain)."
        except Exception as e:
            # Log the exception for debugging
            print(f"Error during LLM call: {e}")
            return f"Error interacting with LLM: {str(e)}"

# --- Fast Content Block Processor Tool ---

class FastContentBlockProcessorToolInput(BaseModel):
    """Input for FastContentBlockProcessorTool."""
    content_blocks: Optional[List[ContentBlock]] = Field(default=None, description="Optional list of ContentBlock objects to process. Primarily used by operations like 'concatenate_text' or 'extract_image_metadata'. Not used by 'reconstruct_content_from_summary' if 'summarized_text' is provided.")
    operation: str = Field(description="The processing operation to perform.")
    summarized_text: Optional[str] = Field(None, description="The summarized text string, used by 'reconstruct_content_from_summary'.")
    image_metadata_list_json: Optional[str] = Field(None, description="JSON string representation of the list of essential image metadata dictionaries, used by 'reconstruct_content_from_summary'.")
    document_id: Optional[str] = Field(None, description="Document ID to associate with newly created blocks during reconstruction.")

class FastContentBlockProcessorTool(BaseTool):
    name: str = "Fast Content Block Processor"
    description: str = (
        "Provides utility functions for rapidly processing lists of ContentBlock objects. "
        "Designed for efficient data extraction and transformation without LLM calls."
    )
    args_schema: type[BaseModel] = FastContentBlockProcessorToolInput
    user_id: Optional[str] = None # Added to store user_id

    def __init__(self, user_id: Optional[str] = "default_user_id_tool", **kwargs):
        super().__init__(**kwargs)
        self.user_id = user_id
        print(f"FastContentBlockProcessorTool initialized with user_id: {self.user_id}") # For debugging

    def _run(self, operation: str, content_blocks: Optional[List[ContentBlock]] = None, summarized_text: Optional[str] = None, image_metadata_list_json: Optional[str] = None, document_id: Optional[str] = None) -> Any:
        """Processes content blocks based on the specified operation."""
        
        current_document_id_for_run = document_id # Capture for the run, especially for reconstruction

        if operation == "concatenate_text":
            all_text = []
            for block in content_blocks:
                if block.type == "text" and block.content: # Changed from text_content to content
                    all_text.append(block.content)
                elif block.type == "list" and block.items: # Kept 'items' as per ContentBlock definition
                    for item in block.items:
                        if isinstance(item, str):
                            all_text.append(item)
                        # Add more sophisticated list item text extraction if needed
            return "\n\n".join(all_text)
        
        elif operation == "extract_image_metadata":
            image_metadata = []
            for block in content_blocks:
                if block.type == "image":
                    # Directly access fields from ContentBlock for images
                    img_meta = {
                        "image_id_ref": block.image_id_ref,
                        "gcs_url": block.gcs_url,
                        "alt_text": block.alt_text,
                        "llm_description": block.llm_description,
                        "caption": block.caption,
                        "width": block.width,
                        "height": block.height
                    }
                    image_metadata.append(img_meta)
            return image_metadata

        # Add more operations as needed by the agents (e.g., create_content_block, parse_llm_output_to_blocks)
        # For example, an operation to prepare content for the SummarizationAgent:
        elif operation == "prepare_for_summarization":
            text_for_summarization = []
            essential_image_info = [] # URLs or IDs of images to be referenced
            for block in content_blocks:
                if block.type == "text" and block.content: # Changed from text_content to content
                    text_for_summarization.append(block.content)
                elif block.type == "image" and block.gcs_url:
                    essential_image_info.append({
                        "image_id_ref": block.image_id_ref if block.image_id_ref else "unknown_image",
                        "gcs_url": block.gcs_url,
                        "alt_text": block.alt_text,
                        "caption": block.caption,
                        "llm_description": block.llm_description
                    })
            return {
                "concatenated_text": "\n\n".join(text_for_summarization),
                "essential_image_metadata": essential_image_info
            }

        elif operation == "reconstruct_content_from_summary":
            if summarized_text is None or image_metadata_list_json is None:
                return "Error: 'summarized_text' and 'image_metadata_list_json' (JSON string) are required for 'reconstruct_content_from_summary'."

            try:
                image_metadata_list: List[Dict[str, Any]] = json.loads(image_metadata_list_json)
            except json.JSONDecodeError as e:
                return f"Error: Failed to parse 'image_metadata_list_json'. Invalid JSON: {e}"

            reconstructed_blocks_dicts: List[Dict[str, Any]] = []
            order_idx_counter = 0
            processed_image_ids = set() 

            image_meta_lookup_gcs = {meta.get('gcs_url'): meta for meta in image_metadata_list if meta.get('gcs_url')}
            image_meta_lookup_id = {meta.get('image_id_ref'): meta for meta in image_metadata_list if meta.get('image_id_ref')}

            current_user_id_for_tool = self.user_id
            if not current_user_id_for_tool:
                print("Warning: user_id not set in FastContentBlockProcessorTool. Using placeholder.")
                current_user_id_for_tool = "tool_reconstruct_fallback_user"
            
            if not current_document_id_for_run:
                print("Warning: document_id not provided to FastContentBlockProcessorTool for reconstruction. New blocks will lack it.")
                # It's crucial for the calling Agent/Crew to provide document_id for reconstruction.

            last_idx = 0
            placeholder_pattern = r'\[IMAGE:\s*([^\s\]]+)\s*\]'
            import re

            for match in re.finditer(placeholder_pattern, summarized_text):
                start_match, end_match = match.span()
                placeholder_identifier = match.group(1)

                text_before_placeholder = summarized_text[last_idx:start_match].strip()
                if text_before_placeholder:
                    text_block = ContentBlock(
                        block_id=uuid.uuid4().hex,
                        tmp_id=None, # New text block
                        user_id=current_user_id_for_tool,
                        document_id=current_document_id_for_run, # Use run-specific document_id
                        type='text',
                        content=text_before_placeholder,
                        order_index=order_idx_counter
                    )
                    reconstructed_blocks_dicts.append(text_block.model_dump(mode='json'))
                    order_idx_counter += 1
                
                img_meta_to_use = None
                # Lookup in the definitive pool
                if placeholder_identifier in image_meta_lookup_id:
                    img_meta_to_use = image_meta_lookup_id[placeholder_identifier]
                elif placeholder_identifier in image_meta_lookup_gcs:
                    img_meta_to_use = image_meta_lookup_gcs[placeholder_identifier]
                
                if img_meta_to_use:
                    # If img_meta_to_use is already a rich ContentBlock-like dict from a previous run,
                    # preserve its original block_id, tmp_id. User_id and document_id can be from original or current run.
                    # For simplicity here, we prioritize current_user_id_for_tool and current_document_id_for_run
                    # if creating a *new* block structure, but if img_meta_to_use has them, it implies it's a pre-existing block.
                    
                    final_block_id = img_meta_to_use.get('block_id', uuid.uuid4().hex)
                    final_tmp_id = img_meta_to_use.get('tmp_id', img_meta_to_use.get('image_id_ref'))
                    final_user_id = img_meta_to_use.get('user_id', current_user_id_for_tool)
                    final_document_id = img_meta_to_use.get('document_id', current_document_id_for_run)

                    image_block = ContentBlock(
                        block_id=final_block_id,
                        tmp_id=final_tmp_id,
                        user_id=final_user_id,
                        document_id=final_document_id,
                        type='image',
                        image_id_ref=img_meta_to_use.get('image_id_ref'),
                        gcs_url=img_meta_to_use.get('gcs_url'),
                        alt_text=img_meta_to_use.get('alt_text'),
                        caption=img_meta_to_use.get('caption'),
                        llm_description=img_meta_to_use.get('llm_description'),
                        width=img_meta_to_use.get('width'),
                        height=img_meta_to_use.get('height'),
                        order_index=order_idx_counter
                    )
                    reconstructed_blocks_dicts.append(image_block.model_dump(mode='json'))
                    order_idx_counter += 1
                    processed_image_ids.add(img_meta_to_use.get('image_id_ref'))
                    processed_image_ids.add(img_meta_to_use.get('gcs_url'))
                else:
                    # Placeholder was in text, but no matching image metadata found
                    # Create a text block indicating the missing image reference
                    missing_ref_text_block = ContentBlock(
                        block_id=uuid.uuid4().hex,
                        tmp_id=None,
                        user_id=current_user_id_for_tool,
                        document_id=current_document_id_for_run,
                        type='text',
                        content=f"[IMAGE: {placeholder_identifier} - Referenced but not found in provided image metadata]",
                        order_index=order_idx_counter
                    )
                    reconstructed_blocks_dicts.append(missing_ref_text_block.model_dump(mode='json'))
                    order_idx_counter += 1

                last_idx = end_match

            remaining_text = summarized_text[last_idx:].strip()
            if remaining_text:
                text_block = ContentBlock(
                    block_id=uuid.uuid4().hex,
                    tmp_id=None, 
                    user_id=current_user_id_for_tool,
                    document_id=current_document_id_for_run,
                    type='text',
                    content=remaining_text,
                    order_index=order_idx_counter
                )
                reconstructed_blocks_dicts.append(text_block.model_dump(mode='json'))
                order_idx_counter += 1

            # Append any images from image_metadata_list not referenced by placeholders
            for img_meta in image_metadata_list:
                identifier_ref = img_meta.get('image_id_ref')
                identifier_gcs = img_meta.get('gcs_url')
                if not (identifier_ref in processed_image_ids or identifier_gcs in processed_image_ids):
                    
                    final_block_id = img_meta.get('block_id', uuid.uuid4().hex)
                    final_tmp_id = img_meta.get('tmp_id', img_meta.get('image_id_ref'))
                    final_user_id = img_meta.get('user_id', current_user_id_for_tool)
                    final_document_id = img_meta.get('document_id', current_document_id_for_run)
                    
                    appended_image_block = ContentBlock(
                        block_id=final_block_id,
                        tmp_id=final_tmp_id,
                        user_id=final_user_id,
                        document_id=final_document_id,
                        type='image',
                        image_id_ref=img_meta.get('image_id_ref'),
                        gcs_url=img_meta.get('gcs_url'),
                        alt_text=img_meta.get('alt_text'),
                        caption=img_meta.get('caption'),
                        llm_description=img_meta.get('llm_description'),
                        width=img_meta.get('width'),
                        height=img_meta.get('height'),
                        order_index=order_idx_counter
                    )
                    reconstructed_blocks_dicts.append(appended_image_block.model_dump(mode='json'))
                    order_idx_counter += 1
                    # Optional: Log that an image was appended because it wasn't referenced
                    # print(f"DEBUG: Appended unreferenced image: {identifier_ref or identifier_gcs}")
            
            return reconstructed_blocks_dicts

        else:
            return f"Error: Operation '{operation}' not supported by FastContentBlockProcessorTool."

# Example of how you might instantiate and use the tools (for testing or in crew setup)
if __name__ == '__main__':
    # This section is for illustrative purposes and won't run directly when imported
    
    # Test OptimizedLLMInteractionTool
    llm_tool = OptimizedLLMInteractionTool()
    # print("Testing LLM Tool:")
    # llm_response = llm_tool._run(prompt="Hello, what is the weather like today?")
    # print(f"LLM Response: {llm_response}")

    # Test FastContentBlockProcessorTool
    # Sample blocks should now conform to the actual ContentBlock structure
    sample_blocks_data = [
        {"block_id": "1", "type": "text", "content": "This is the first paragraph."},
        {"block_id": "2", "type": "image", "image_id_ref": "img1", "gcs_url": "gs://bucket/img1.jpg", "alt_text": "A cat"},
        {"block_id": "3", "type": "text", "content": "This is the second paragraph, following an image."},
        {"block_id": "4", "type": "list", "items": ["item 1", "item 2"], "ordered": False}
    ]
    sample_blocks = [ContentBlock(**data) for data in sample_blocks_data]

    processor_tool = FastContentBlockProcessorTool()
    
    print("\nTesting Content Processor Tool (concatenate_text):")
    concatenated_text = processor_tool._run(content_blocks=sample_blocks, operation='concatenate_text')
    print(f"Concatenated Text: {concatenated_text}")

    print("\nTesting Content Processor Tool (extract_image_metadata):")
    image_meta = processor_tool._run(content_blocks=sample_blocks, operation='extract_image_metadata')
    print(f"Image Metadata: {image_meta}")

    print("\nTesting Content Processor Tool (prepare_for_summarization):")
    summarization_input = processor_tool._run(content_blocks=sample_blocks, operation='prepare_for_summarization')
    print(f"Input for Summarization: {summarization_input}")

    # Test reconstruct_content_from_summary
    print("\nTesting Content Processor Tool (reconstruct_content_from_summary):")
    sample_summary_text_with_placeholders = "This is the summarized intro. [IMAGE: img1] Then, more summary. [IMAGE: gs://bucket/img_missing.jpg] And a final bit of text."
    sample_summary_text_no_placeholders = "This is a summary with no image references in it directly."
    
    # image_meta was fetched earlier via 'extract_image_metadata'
    # For 'prepare_for_summarization', the structure is {'image_id_ref': ..., 'gcs_url': ...}
    # Let's use the output from 'prepare_for_summarization' directly
    essential_images_for_reconstruction = summarization_input.get("essential_image_metadata", [])

    reconstructed_with_placeholders = processor_tool._run(
        operation='reconstruct_content_from_summary',
        summarized_text=sample_summary_text_with_placeholders,
        image_metadata_list_json=json.dumps(essential_images_for_reconstruction)
    )
    print(f"Reconstructed (with placeholders): {reconstructed_with_placeholders}")

    reconstructed_no_placeholders = processor_tool._run(
        operation='reconstruct_content_from_summary',
        summarized_text=sample_summary_text_no_placeholders,
        image_metadata_list_json=json.dumps(essential_images_for_reconstruction) 
    )
    print(f"Reconstructed (no placeholders, images not directly added unless policy changes): {reconstructed_no_placeholders}") 