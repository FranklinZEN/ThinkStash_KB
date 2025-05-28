import time
import json # Added for parsing LLM responses if they are JSON strings
import re # Moved to top
import base64 # For image encoding
import io # For BytesIO
from openai import OpenAI as OpenAIClient # Alias to avoid conflict if google.generativeai also has an OpenAI class
# import google.genai as genai # REMOVED Gemini import
# from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig, Part # REMOVED
from typing import Type, Dict, Optional, Any, List, Literal # Removed Annotated for now
from langchain_core.tools import BaseTool as LangchainCoreBaseTool, InjectedToolArg
from langchain_openai import ChatOpenAI
from pydantic import BaseModel as PydanticV2BaseModel, Field as PydanticV2Field # Keep this aliased import for clarity
from PIL import Image # To determine MIME type for base64 encoding
# Remove: from langchain_core.pydantic_v1 import BaseModel, Field, validator # This was for Pydantic v1

from aiservice.app.config.settings import settings, Settings as AppSettings # Import global settings and Settings class as AppSettings

# Placeholder for actual LLM client interaction (e.g., OpenAI, VertexAI)
# from app.core.llm_clients import get_llm_client

# --- LLM Client Initialization ---
# This client is for general text tasks, used by ContentStructuringLLMHelper if no specific one is passed
default_openai_text_client = None
if settings.openai_api_key:
    try:
        default_openai_text_client = ChatOpenAI(
            api_key=settings.openai_api_key,
            model_name=settings.default_llm_model 
        )
        print("LLM_TOOLS: Default ChatOpenAI client initialized for text tasks.")
    except Exception as e:
        print(f"LLM_TOOLS: ERROR - Failed to initialize default ChatOpenAI: {e}")
else:
    print("LLM_TOOLS: WARNING - OpenAI API key not found. LLM tools may fail.")

# --- Input/Output Schemas for ImageAnalysisLLMTool ---
class ImageAnalysisInput(PydanticV2BaseModel):
    image_bytes: Optional[bytes] = PydanticV2Field(None, description="Bytes of the image to analyze.")
    image_path: Optional[str] = PydanticV2Field(None, description="Path to the image file if bytes are not provided.")
    # Potentially add context like surrounding text, page number for better analysis
    text_context: Optional[str] = PydanticV2Field(None, description="Text surrounding or relevant to the image.")
    prompt_override: Optional[str] = PydanticV2Field(None, description="Alternative prompt for the vision model.")
    # filename_for_mime: Optional[str] = Field(None, description="Optional filename to help infer MIME type if bytes are directly provided.")

class ImageAnalysisOutput(PydanticV2BaseModel):
    description: Optional[str] = PydanticV2Field(None, description="Detailed LLM-generated description of the image.")
    caption: Optional[str] = PydanticV2Field(None, description="Concise LLM-generated caption for the image.")
    keywords: Optional[List[str]] = PydanticV2Field(default_factory=list, description="Keywords related to the image content.")
    # Add other structured fields as needed, e.g., detected objects, OCR text if applicable
    error_message: Optional[str] = PydanticV2Field(None)

# --- ImageAnalysisLLMTool: Reverted to pure OpenAI --- 
class ImageAnalysisLLMTool: # Not inheriting from Langchain BaseTool for this direct implementation
    name: str = "Image_Analysis_LLM_Tool"
    description: str = "Analyzes an image using OpenAI's vision model to generate a description, caption, and keywords."
    args_schema: Type[PydanticV2BaseModel] = ImageAnalysisInput
    openai_vision_client: Optional[OpenAIClient] = None

    def __init__(self, **kwargs):
        if settings.openai_api_key:
            try:
                self.openai_vision_client = OpenAIClient(api_key=settings.openai_api_key)
                print(f"ImageAnalysisLLMTool: OpenAI client initialized for vision model ({settings.default_multimodal_llm_model}).")
            except Exception as e:
                print(f"ImageAnalysisLLMTool: ERROR - Failed to initialize OpenAI client for vision: {e}")
        else:
             print("ImageAnalysisLLMTool: WARNING - OpenAI API key not found. Image analysis will fail.")

    def _get_image_mime_type(self, image_bytes: bytes) -> Optional[str]:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            format_upper = img.format
            if not format_upper:
                if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'): format_upper = 'PNG'
                elif image_bytes.startswith(b'\xff\xd8\xff'): format_upper = 'JPEG'
                elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'): format_upper = 'GIF'
                else: return None
            mime_type = Image.MIME.get(format_upper)
            if not mime_type:
                if format_upper == 'JPEG': mime_type = 'image/jpeg'
                elif format_upper == 'PNG': mime_type = 'image/png'
                elif format_upper == 'GIF': mime_type = 'image/gif'
                else: return None
            return mime_type
        except Exception: return None

    def _run(self, image_bytes: Optional[bytes] = None, image_path: Optional[str] = None, text_context: Optional[str] = None, prompt_override: Optional[str] = None) -> Dict[str, Any]:
        if not self.openai_vision_client: return ImageAnalysisOutput(error_message="OpenAI vision client not initialized.").model_dump()

        current_image_bytes = image_bytes
        if image_path and not current_image_bytes:
            try:
                with open(image_path, "rb") as f: current_image_bytes = f.read()
            except Exception as e:
                return ImageAnalysisOutput(error_message=f"Failed to read image from path {image_path}: {e}").model_dump()
        if not current_image_bytes: return ImageAnalysisOutput(error_message="No image bytes or valid image path provided.").model_dump()

        mime_type = self._get_image_mime_type(current_image_bytes)
        if not mime_type: return ImageAnalysisOutput(error_message="Could not determine image MIME type for OpenAI.").model_dump()
        
        base64_image_data = base64.b64encode(current_image_bytes).decode('utf-8')
        system_prompt = "You are an expert image analyst. Provide a detailed description, a concise caption, and 3-5 relevant keywords for the given image. Format your response as a JSON object with keys: \"description\", \"caption\", and \"keywords\" (which should be a list of strings)."
        user_messages_content = []
        main_prompt_text = prompt_override or f"Analyze this image. Optional context: {text_context if text_context else 'N/A'}"
        user_messages_content.append({"type": "text", "text": main_prompt_text})
        user_messages_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image_data}"}})

        try:
            print(f"ImageAnalysisLLMTool: Calling OpenAI vision model ({settings.default_multimodal_llm_model}) for image analysis...")
            response = self.openai_vision_client.chat.completions.create(
                model=settings.default_multimodal_llm_model or "gpt-4-vision-preview",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_messages_content}],
                max_tokens=450, response_format={"type": "json_object"})
            llm_response_str = response.choices[0].message.content
            cleaned_json_str = llm_response_str.strip()
            if cleaned_json_str.startswith("```json"): cleaned_json_str = cleaned_json_str[7:] 
            if cleaned_json_str.endswith("```"): cleaned_json_str = cleaned_json_str[:-3]
            elif cleaned_json_str.startswith("```"): cleaned_json_str = cleaned_json_str[3:]
            if cleaned_json_str.endswith("```"): cleaned_json_str = cleaned_json_str[:-3] # Ensure this is not elif
            cleaned_json_str = cleaned_json_str.strip()
            data = json.loads(cleaned_json_str)
            return ImageAnalysisOutput(description=data.get("description"), caption=data.get("caption"), keywords=data.get("keywords", [])).model_dump()
        except Exception as e:
            print(f"ImageAnalysisLLMTool: Error during OpenAI vision call: {e}")
            # import traceback; traceback.print_exc() # Keep commented
            return ImageAnalysisOutput(error_message=f"OpenAI vision call failed: {str(e)}").model_dump()

# Define allowed block types using Literal
BlockType = Literal["text", "image_reference", "code", "math"]

class StructuredContentBlock(PydanticV2BaseModel):
    type: BlockType = PydanticV2Field(description="Type of content block.")
    content: Optional[str] = PydanticV2Field(default=None, description="Text content for the block (verbatim from source for text, code, math).")
    image_id: Optional[str] = PydanticV2Field(default=None, description="ID of the image for 'image_reference' blocks.")
    caption: Optional[str] = PydanticV2Field(default=None, description="Caption for the image (from metadata or null for 'image_reference' blocks).")

class ContentStructuringOutput(PydanticV2BaseModel):
    blocks: List[StructuredContentBlock] = PydanticV2Field(default_factory=list)
    error_message: Optional[str] = PydanticV2Field(None)
    
# Global schema for OpenAI function calling
block_item_schema_for_llm_tool = {
    "parameters": {
        "type": "object",
        "properties": {
            "blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["text", "image_reference", "code", "math"]},
                        "content": {"type": "string", "description": "Textual content...", "nullable": True},
                        "image_id": {"type": "string", "description": "Unique identifier...", "nullable": True},
                        "caption": {"type": "string", "description": "Caption for an image...", "nullable": True}
                    },
                    "required": ["type"]
                },
                "description": "A list of content blocks..."
            }
        },
        "required": ["blocks"]
    }
}

class ContentStructuringLLMHelper:
    llm_instance: Optional[ChatOpenAI] = None # Reverted to ChatOpenAI type

    def __init__(self, llm_instance: Optional[ChatOpenAI] = None, settings_override: Optional[AppSettings] = None):
        self.current_settings = settings_override if settings_override else settings
        self.llm_instance = llm_instance if llm_instance is not None else default_openai_text_client
        if not self.llm_instance:
            print("ContentStructuringLLMHelper: WARNING - Initialized WITHOUT an OpenAI LLM instance. Calls will fail.")
        else:
            print(f"ContentStructuringLLMHelper: Initialized with OpenAI LLM: {self.llm_instance.model_name if hasattr(self.llm_instance, 'model_name') else 'unknown'}")

    def perform_direct_structuring(self, raw_text: str, image_metadata: List[Dict[str, Any]], prompt_override: Optional[str] = None) -> Dict[str, Any]:
        if not self.llm_instance:
            return ContentStructuringOutput(blocks=[], error_message="OpenAI LLM not configured for structuring.").model_dump()

        print(f"[ContentStructuringLLMHelper.perform_direct_structuring] Called with raw_text length: {len(raw_text)}, images: {len(image_metadata)}")
        image_refs_segment = ""
        if image_metadata:
            image_details_list = [f"- Image ID: {img.get('image_id')}, Provided Caption: {img.get('caption')}" for img in image_metadata if img.get('image_id')]
            if image_details_list:
                image_refs_segment = ("\n\nAvailable images for reference...\n" + "\n".join(image_details_list))
        
        # Using the refined system prompt for OpenAI (ensure it's complete and correct)
        system_prompt_content = (
            "You are an expert content structuring AI..." # (Ensure this is your full, refined OpenAI system prompt)
            # ... (The rest of the detailed OpenAI system prompt including image referencing and examples) ...
            "IMAGE CAPTIONS AND REFERENCING: You will be given a list of 'Available images for reference' with their 'Image ID' and 'Provided Caption'. When you encounter text in the 'Raw Text to Structure' that clearly refers to a figure (e.g., 'Figure 1', 'see Fig. 2', 'as shown in the diagram below Figure 3'), you MUST create an 'image_reference' block. Match the figure mentioned in the text to an image in the 'Available images for reference' list, often by matching the figure number or description in the 'Provided Caption'. Use the corresponding 'Image ID' for the 'image_id' field. For the 'caption' field in your output 'image_reference' block, if a 'Provided Caption' is available in the list for that Image ID, you MUST use that exact caption. If no 'Provided Caption' is available, the caption field MUST be null. DO NOT invent or generate new captions. "
            "Segment the provided text into logical 'text', 'code', or 'math' blocks. All text segments MUST have type 'text'. Insert 'image_reference' blocks for ALL figures mentioned in the text and available in the metadata, placing them in the correct sequence within the text flow. "
            "Your entire response MUST be a single, valid JSON object. This JSON object must have a key named 'blocks'. "
            "The value for the 'blocks' key must be a JSON list of content block objects..."
            # (Ensure full examples from previous working version are here)
        )
        user_prompt_content = prompt_override or (
            f"Using ONLY the provided 'Raw Text to Structure'...\n{image_refs_segment}\n\nRaw Text to Structure:\n'''\n{raw_text}\n'''"
        )
        messages = [{"role": "system", "content": system_prompt_content}, {"role": "user", "content": user_prompt_content}]
        
        llm_tool_schema_for_call = {
            "type": "function", 
            "function": {
                "name": "format_content_blocks",
                "description": "Formats content into structured blocks.", # Simplified description
                "parameters": block_item_schema_for_llm_tool["parameters"] # Use the global schema's parameters part
            }
        }

        try:
            print(f"ContentStructuringLLMHelper: Calling OpenAI LLM ({self.llm_instance.model_name}) for direct structuring...")
            response = self.llm_instance.invoke(messages, tools=[llm_tool_schema_for_call], tool_choice={"type": "function", "function": {"name": "format_content_blocks"}})
            
            if hasattr(response, 'tool_calls') and response.tool_calls and isinstance(response.tool_calls, list) and len(response.tool_calls) > 0:
                first_tool_call = response.tool_calls[0]
                tool_args_dict = None
                if isinstance(first_tool_call, dict): # Langchain can return dicts here
                    tool_args_str = first_tool_call.get('args')
                elif hasattr(first_tool_call, 'args'): # Or objects with .args
                    tool_args_str = first_tool_call.args
                else:
                    tool_args_str = None
                
                if isinstance(tool_args_str, str):
                    try: tool_args_dict = json.loads(tool_args_str)
                    except json.JSONDecodeError: pass
                elif isinstance(tool_args_str, dict):
                    tool_args_dict = tool_args_str

                if tool_args_dict and first_tool_call.name == "format_content_blocks":
                    validated_output = ContentStructuringOutput(**tool_args_dict)
                    print(f"ContentStructuringLLMHelper: OpenAI LLM function call successful, {len(validated_output.blocks)} blocks structured.")
                    return validated_output.model_dump()
            
            error_msg = "OpenAI LLM did not use 'format_content_blocks' as expected or parsing failed."
            print(f"ContentStructuringLLMHelper: {error_msg} Full Response: {response!r}")
            return ContentStructuringOutput(blocks=[], error_message=error_msg).model_dump()
        except Exception as e:
            print(f"ContentStructuringLLMHelper: Error during OpenAI LLM call: {e}")
            # import traceback; traceback.print_exc() # Keep commented
            return ContentStructuringOutput(blocks=[], error_message=str(e)).model_dump()

    class Config: 
        arbitrary_types_allowed = True