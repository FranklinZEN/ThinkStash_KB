#!/usr/bin/env python
# coding: utf-8
"""
Tools for AI insight generation crews, including optimized LLM interaction
and fast content block processing.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
# import openai # No longer using direct openai client here for default
import uuid # Added for generating block_ids

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
            print(f"OptimizedLLMInteractionTool: Invoking LLM. Model: {self.llm_client.model_name if hasattr(self.llm_client, 'model_name') else 'N/A'}")
            
            response = self.llm_client.invoke(
                lc_messages,
                # model_kwargs={'max_tokens': max_tokens} # Example if endpoint supports it this way
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
    content_blocks: List[ContentBlock] = Field(..., description="List of ContentBlock objects to process. Not used by 'reconstruct_content_from_summary' operation if 'summarized_text' is provided.")
    operation: str = Field(default="concatenate_text", description="The processing operation to perform.")
    summarized_text: Optional[str] = Field(None, description="The summarized text string, used by 'reconstruct_content_from_summary'.")
    image_metadata_list: Optional[List[Dict[str, Any]]] = Field(None, description="List of essential image metadata dictionaries, used by 'reconstruct_content_from_summary'.")

class FastContentBlockProcessorTool(BaseTool):
    name: str = "Fast Content Block Processor"
    description: str = (
        "Provides utility functions for rapidly processing lists of ContentBlock objects. "
        "Designed for efficient data extraction and transformation without LLM calls."
    )
    args_schema: type[BaseModel] = FastContentBlockProcessorToolInput

    def _run(self, operation: str, content_blocks: Optional[List[ContentBlock]] = None, summarized_text: Optional[str] = None, image_metadata_list: Optional[List[Dict[str, Any]]] = None) -> Any: # Added new optional args
        """Processes content blocks based on the specified operation."""
        
        # --- REVERTED DEBUG/SAFEGUARD ---
        # The tool should expect content_blocks to be List[ContentBlock] as per its args_schema.
        # If it receives dicts, it's an issue with how the agent/CrewAI passes arguments.
        # --- END REVERTED DEBUG/SAFEGUARD ---

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
            if not summarized_text or image_metadata_list is None: # image_metadata_list can be an empty list
                return "Error: 'summarized_text' and 'image_metadata_list' are required for 'reconstruct_content_from_summary'."

            reconstructed_blocks: List[ContentBlock] = []
            
            # Create a quick lookup for image metadata by gcs_url or image_id_ref
            image_meta_lookup_gcs = {meta.get('gcs_url'): meta for meta in image_metadata_list if meta.get('gcs_url')}
            image_meta_lookup_id = {meta.get('image_id_ref'): meta for meta in image_metadata_list if meta.get('image_id_ref')}

            # Simple placeholder strategy: [IMAGE: <identifier>] where identifier can be gcs_url or image_id_ref
            # This regex will find placeholders and capture the identifier.
            # It also captures text before and after placeholders.
            import re
            # Pattern to find [IMAGE: identifier] and capture text segments around it
            # This will split the text by image placeholders, keeping the placeholders.
            # For example: "Text before [IMAGE: id1] text after"
            # A more robust parser might be needed for complex cases.
            
            # For now, let's do a simpler split. If summary is not expected to have placeholders,
            # we just create a text block and then append all images.
            # According to the plan: "The LLM prompt will guide you to refer to images by their identifiers 
            # if they are contextually important for the summary." - so placeholders are expected.

            current_text_segment = ""
            last_idx = 0
            
            # Regex to find [IMAGE: <identifier>]
            # The identifier can be an image_id_ref (alphanumeric, hyphens, underscores)
            # or a GCS URL (starts with gs://, can contain various characters)
            placeholder_pattern = r'\[IMAGE:\s*([^\s\]]+)\s*\]'

            for match in re.finditer(placeholder_pattern, summarized_text):
                start_match, end_match = match.span()
                placeholder_identifier = match.group(1)

                # Add preceding text segment if any
                text_before_placeholder = summarized_text[last_idx:start_match].strip()
                if text_before_placeholder:
                    reconstructed_blocks.append(ContentBlock(
                        block_id=uuid.uuid4().hex,
                        type="text",
                        content=text_before_placeholder
                    ))
                
                # Find and add image block
                img_meta_to_use = None
                if placeholder_identifier in image_meta_lookup_id:
                    img_meta_to_use = image_meta_lookup_id[placeholder_identifier]
                elif placeholder_identifier in image_meta_lookup_gcs:
                    img_meta_to_use = image_meta_lookup_gcs[placeholder_identifier]
                
                if img_meta_to_use:
                    reconstructed_blocks.append(ContentBlock(
                        block_id=uuid.uuid4().hex,
                        type="image",
                        image_id_ref=img_meta_to_use.get("image_id_ref"),
                        gcs_url=img_meta_to_use.get("gcs_url"),
                        alt_text=img_meta_to_use.get("alt_text"),
                        caption=img_meta_to_use.get("caption"),
                        llm_description=img_meta_to_use.get("llm_description"),
                        width=img_meta_to_use.get("width"),
                        height=img_meta_to_use.get("height")
                        # page_number and bbox might not be relevant for new blocks or might need to be derived
                    ))
                else:
                    # If placeholder image not found, could insert a warning text block or skip
                    print(f"Warning: Image for placeholder '{placeholder_identifier}' not found in provided metadata.")
                    # Optionally, add a text block indicating missing image.
                    # reconstructed_blocks.append(ContentBlock(
                    #     block_id=uuid.uuid4().hex,
                    #     type="text",
                    #     content=f"[Warning: Image '{placeholder_identifier}' not found]"
                    # ))

                last_idx = end_match

            # Add any remaining text after the last placeholder
            remaining_text = summarized_text[last_idx:].strip()
            if remaining_text:
                reconstructed_blocks.append(ContentBlock(
                    block_id=uuid.uuid4().hex,
                    type="text",
                    content=remaining_text
                ))
            
            # If no placeholders were found at all, the whole summarized_text is one block
            if not reconstructed_blocks and summarized_text:
                 reconstructed_blocks.append(ContentBlock(
                    block_id=uuid.uuid4().hex,
                    type="text",
                    content=summarized_text
                ))
            
            # Fallback: if summary had no placeholders, and we're supposed to add images,
            # we might append them here if the design requires it.
            # However, the current logic relies on placeholders. If no placeholders, no images are interspersed.
            # If essential_image_metadata was meant to be included regardless of placeholders, that logic would be different (e.g. append all at end)
            # For now, sticking to placeholder-driven insertion.

            return [block.model_dump(mode='json') for block in reconstructed_blocks]

        else:
            return f"Error: Unknown operation '{operation}'."

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
        image_metadata_list=essential_images_for_reconstruction
    )
    print(f"Reconstructed (with placeholders): {reconstructed_with_placeholders}")

    reconstructed_no_placeholders = processor_tool._run(
        operation='reconstruct_content_from_summary',
        summarized_text=sample_summary_text_no_placeholders,
        image_metadata_list=essential_images_for_reconstruction 
    )
    print(f"Reconstructed (no placeholders, images not directly added unless policy changes): {reconstructed_no_placeholders}") 