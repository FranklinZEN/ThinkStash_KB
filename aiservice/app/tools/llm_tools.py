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
if settings.use_gemini_via_openai_compatibility and settings.gemini_api_key and settings.gemini_text_model_compat and settings.gemini_compatibility_base_url:
    try:
        default_openai_text_client = ChatOpenAI(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_text_model_compat,
            base_url=settings.gemini_compatibility_base_url,
            # Any other necessary params for Gemini via OpenAI lib, e.g., temperature if not set by model_name
        )
        print(f"LLM_TOOLS: Default ChatOpenAI client initialized for TEXT tasks using GEMINI compatibility (Model: {settings.gemini_text_model_compat}).")
    except Exception as e:
        print(f"LLM_TOOLS: ERROR - Failed to initialize ChatOpenAI client with GEMINI compatibility for TEXT: {e}")
elif settings.openai_api_key and settings.default_llm_model:
    try:
        default_openai_text_client = ChatOpenAI(
            api_key=settings.openai_api_key,
            model_name=settings.default_llm_model
        )
        print("LLM_TOOLS: Default ChatOpenAI client initialized for text tasks using OpenAI.")
    except Exception as e:
        print(f"LLM_TOOLS: ERROR - Failed to initialize default ChatOpenAI using OpenAI: {e}")
else:
    print("LLM_TOOLS: WARNING - Neither Gemini compatibility nor OpenAI API key found for TEXT tasks. LLM tools may fail.")

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
    vision_model_name: Optional[str] = None # To store the actual model name being used

    def __init__(self, **kwargs):
        self.vision_model_name = settings.default_multimodal_llm_model # Default to OpenAI model

        if settings.use_gemini_via_openai_compatibility and \
           settings.gemini_api_key and \
           settings.gemini_multimodal_model_compat and \
           settings.gemini_compatibility_base_url:
            try:
                self.openai_vision_client = OpenAIClient(
                    api_key=settings.gemini_api_key,
                    base_url=settings.gemini_compatibility_base_url
                    # model_name is not set here for the client, but in the create call later
                )
                self.vision_model_name = settings.gemini_multimodal_model_compat
                print(f"ImageAnalysisLLMTool: OpenAIClient initialized for VISION tasks using GEMINI compatibility (Model to be used: {self.vision_model_name}). Base URL: {settings.gemini_compatibility_base_url}")
            except Exception as e:
                print(f"ImageAnalysisLLMTool: ERROR - Failed to initialize OpenAIClient with GEMINI compatibility for VISION: {e}")
        elif settings.openai_api_key and settings.default_multimodal_llm_model:
            try:
                self.openai_vision_client = OpenAIClient(api_key=settings.openai_api_key)
                self.vision_model_name = settings.default_multimodal_llm_model
                print(f"ImageAnalysisLLMTool: OpenAIClient initialized for VISION tasks using OpenAI (Model: {self.vision_model_name}).")
            except Exception as e:
                print(f"ImageAnalysisLLMTool: ERROR - Failed to initialize OpenAIClient for VISION using OpenAI: {e}")
        else:
             print("ImageAnalysisLLMTool: WARNING - Neither Gemini compatibility nor OpenAI API key found for VISION tasks. Image analysis will fail.")

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
        if not self.vision_model_name: return ImageAnalysisOutput(error_message="Vision model name not set.").model_dump()

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
            print(f"ImageAnalysisLLMTool: Calling vision model ({self.vision_model_name}) for image analysis...")
            response = self.openai_vision_client.chat.completions.create(
                model=self.vision_model_name, # Use the determined model name
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_messages_content}],
                max_tokens=2048, # Increased max_tokens from 1024 to 2048
                response_format={"type": "json_object"})
            
            if not response.choices or not response.choices[0].message or response.choices[0].message.content is None:
                error_detail = f"LLM response content is None or not found. Finish reason: {response.choices[0].finish_reason if response.choices and response.choices[0] else 'Unknown'}. Full response: {response!r}"
                print(f"ImageAnalysisLLMTool: Error - {error_detail}")
                return ImageAnalysisOutput(error_message=error_detail).model_dump()
                
            llm_response_str = response.choices[0].message.content
            
            if llm_response_str is None: # Should have been caught above, but defensive
                error_detail = f"llm_response_str is unexpectedly None. Finish reason: {response.choices[0].finish_reason if response.choices and response.choices[0] else 'Unknown'}. Full response: {response!r}"
                print(f"ImageAnalysisLLMTool: Error - {error_detail}")
                return ImageAnalysisOutput(error_message=error_detail).model_dump()

            cleaned_json_str = llm_response_str.strip()
            # Ensure that even if strip results in an empty string, we don't proceed to json.loads
            if not cleaned_json_str:
                error_detail = f"LLM response content stripped to empty string. Original: {llm_response_str[:100]}... Finish reason: {response.choices[0].finish_reason if response.choices and response.choices[0] else 'Unknown'}. Full response: {response!r}"
                print(f"ImageAnalysisLLMTool: Error - {error_detail}")
                return ImageAnalysisOutput(error_message=error_detail).model_dump()

            # Attempt to clean common markdown code block fences if response_format wasn't fully respected
            if cleaned_json_str.startswith("```json"):
                cleaned_json_str = cleaned_json_str[7:]
                if cleaned_json_str.endswith("```"):
                    cleaned_json_str = cleaned_json_str[:-3]
            elif cleaned_json_str.startswith("```"):
                cleaned_json_str = cleaned_json_str[3:]
                if cleaned_json_str.endswith("```"):
                    cleaned_json_str = cleaned_json_str[:-3]
            cleaned_json_str = cleaned_json_str.strip()
            
            if not cleaned_json_str:
                error_detail = f"LLM response content became empty after attempting to strip markdown. Original: {llm_response_str[:100]}... Finish reason: {response.choices[0].finish_reason if response.choices and response.choices[0] else 'Unknown'}. Full response: {response!r}"
                print(f"ImageAnalysisLLMTool: Error - {error_detail}")
                return ImageAnalysisOutput(error_message=error_detail).model_dump()

            data = json.loads(cleaned_json_str) # This is where "Unterminated string" could happen if cleaned_json_str is not valid JSON
            return ImageAnalysisOutput(description=data.get("description"), caption=data.get("caption"), keywords=data.get("keywords", [])).model_dump()
        except json.JSONDecodeError as je:
            error_detail = f"JSONDecodeError: {je}. Problematic string: '{cleaned_json_str[:200]}...' Finish reason: {response.choices[0].finish_reason if response.choices and response.choices[0] else 'Unknown'}. Full response: {response!r}"
            print(f"ImageAnalysisLLMTool: Error during OpenAI vision call - {error_detail}")
            return ImageAnalysisOutput(error_message=error_detail).model_dump()
        except Exception as e:
            error_detail = f"OpenAI vision call failed: {str(e)}. Finish reason: {response.choices[0].finish_reason if response.choices and response.choices[0] else 'Unknown'}. Full response: {response!r}"
            print(f"ImageAnalysisLLMTool: Error during OpenAI vision call: {e}")
            # import traceback; traceback.print_exc() # Keep commented
            return ImageAnalysisOutput(error_message=error_detail).model_dump()

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
            print(f"ContentStructuringLLMHelper: DEBUG - Full LLM Response object: {response!r}") # DEBUG

            tool_args_dict = None
            function_name = None

            # Attempt to get tool calls from additional_kwargs first, as it seems more reliable from logs
            potential_tool_calls = None
            if hasattr(response, 'additional_kwargs') and isinstance(response.additional_kwargs, dict):
                potential_tool_calls = response.additional_kwargs.get('tool_calls')
            
            if not potential_tool_calls and hasattr(response, 'tool_calls'): # Fallback to response.tool_calls
                potential_tool_calls = response.tool_calls

            print(f"ContentStructuringLLMHelper: DEBUG - Potential tool_calls from LLM response (type {type(potential_tool_calls)}): {potential_tool_calls!r}")

            if isinstance(potential_tool_calls, list) and len(potential_tool_calls) > 0:
                # Iterate through tool calls to find the first valid format_content_blocks
                for tool_call_item in potential_tool_calls:
                    print(f"ContentStructuringLLMHelper: DEBUG - Processing tool_call_item: {tool_call_item!r}")
                    current_tool_args_str = None
                    current_function_name = None

                    if isinstance(tool_call_item, dict):
                        # This is the structure seen in additional_kwargs: {'id': '', 'function': {'arguments': '...', 'name': '...'}, 'type': 'function'}
                        function_call_details = tool_call_item.get('function')
                        if isinstance(function_call_details, dict):
                            current_function_name = function_call_details.get('name')
                            current_tool_args_str = function_call_details.get('arguments')
                            print(f"ContentStructuringLLMHelper: DEBUG - Extracted from tool_call_item (dict path): function_name='{current_function_name}', args_str_type={type(current_tool_args_str)}")
                    
                    # Fallback if not the dict structure above, try attribute access (less likely for additional_kwargs)
                    elif hasattr(tool_call_item, 'name') and hasattr(tool_call_item, 'args'):
                        current_function_name = tool_call_item.name
                        current_tool_args_str = tool_call_item.args # This might be a dict or str
                        print(f"ContentStructuringLLMHelper: DEBUG - Extracted from tool_call_item (attr path): function_name='{current_function_name}', args_type={type(current_tool_args_str)}")

                    if current_function_name == "format_content_blocks" and current_tool_args_str:
                        temp_tool_args_dict = None
                        if isinstance(current_tool_args_str, str):
                            try: 
                                temp_tool_args_dict = json.loads(current_tool_args_str)
                                print(f"ContentStructuringLLMHelper: DEBUG - Successfully parsed current_tool_args_str to dict for '{current_function_name}'.")
                            except json.JSONDecodeError as e_json:
                                print(f"ContentStructuringLLMHelper: WARNING - Failed to JSON decode current_tool_args_str for '{current_function_name}': {current_tool_args_str[:200]}... Error: {e_json}")
                                continue # Try next tool call if parsing fails
                        elif isinstance(current_tool_args_str, dict):
                            temp_tool_args_dict = current_tool_args_str
                            print(f"ContentStructuringLLMHelper: DEBUG - current_tool_args was already a dict for '{current_function_name}'.")
                        
                        if temp_tool_args_dict: # If we successfully got a dictionary
                            function_name = current_function_name
                            tool_args_dict = temp_tool_args_dict
                            print(f"ContentStructuringLLMHelper: DEBUG - Successfully processed tool call for function: {function_name}")
                            break # Found and processed the first valid format_content_blocks call
            
            print(f"ContentStructuringLLMHelper: DEBUG - Final check after loop: function_name='{function_name}', tool_args_dict is None: {tool_args_dict is None}")
            if tool_args_dict and function_name == "format_content_blocks":
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