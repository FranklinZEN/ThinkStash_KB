import time
import json # Added for parsing LLM responses if they are JSON strings
import re # Moved to top
import base64 # For image encoding
import io # For BytesIO
from openai import OpenAI # Import OpenAI client
# from pydantic import BaseModel, Field # Changed from pydantic.v1 # This line was commented or duplicated, ensure one clear import
from typing import Type, Dict, Optional, Any, List, Literal # Removed Annotated for now
from langchain_core.tools import BaseTool as LangchainCoreBaseTool, InjectedToolArg
from langchain_openai import ChatOpenAI
from pydantic import BaseModel as PydanticV2BaseModel, Field as PydanticV2Field # Keep this aliased import for clarity
from PIL import Image # To determine MIME type for base64 encoding
# Remove: from langchain_core.pydantic_v1 import BaseModel, Field, validator # This was for Pydantic v1

from aiservice.app.config.settings import settings # Import global settings

# Placeholder for actual LLM client interaction (e.g., OpenAI, VertexAI)
# from app.core.llm_clients import get_llm_client

# --- LLM Client Initialization ---
default_llm_client_for_tools = None # Renamed from configured_llm for clarity
if settings.openai_api_key:
    try:
        default_llm_client_for_tools = ChatOpenAI(
            api_key=settings.openai_api_key,
            model_name=settings.default_llm_model 
        )
        print("LLM_TOOLS: Default ChatOpenAI client initialized for tools.")
    except Exception as e:
        print(f"LLM_TOOLS: ERROR - Failed to initialize default ChatOpenAI for tools: {e}")
else:
    print("LLM_TOOLS: WARNING - OpenAI API key not found. Tools needing LLMs may fail if not provided one.")

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

# --- ImageAnalysisLLMTool: Now with Real Vision Call ---
class ImageAnalysisLLMTool(LangchainCoreBaseTool):
    name: str = "Image Analysis LLM Tool"
    description: str = "Analyzes an image using a multimodal LLM to generate a description, caption, and keywords."
    args_schema: Type[PydanticV2BaseModel] = ImageAnalysisInput
    # This tool will use its own OpenAI client instance for vision model, separate from the text LLM client
    vision_llm_client: Optional[OpenAI] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if settings.openai_api_key:
            self.vision_llm_client = OpenAI(api_key=settings.openai_api_key)
            print(f"ImageAnalysisLLMTool: OpenAI client initialized for vision model ({settings.default_multimodal_llm_model}).")
        else:
            print("ImageAnalysisLLMTool: WARNING - OpenAI API key not found. Real image analysis will fail.")

    def _get_image_mime_type_and_base64(self, image_bytes: bytes) -> Optional[tuple[str, str]]:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            format_upper = img.format
            if not format_upper: # Pillow might not detect format for some byte streams
                # Basic check for common types by magic numbers if format is None
                if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'): format_upper = 'PNG'
                elif image_bytes.startswith(b'\xff\xd8\xff'): format_upper = 'JPEG'
                elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'): format_upper = 'GIF'
                else: return None # Unknown format
            
            mime_type = Image.MIME.get(format_upper)
            if not mime_type:
                # Fallback for common formats if Pillow's MIME dict is sparse
                if format_upper == 'JPEG': mime_type = 'image/jpeg'
                elif format_upper == 'PNG': mime_type = 'image/png'
                elif format_upper == 'GIF': mime_type = 'image/gif'
                else: return None # Cannot determine MIME type

            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            return mime_type, base64_image
        except Exception as e:
            print(f"ImageAnalysisLLMTool: Error processing image bytes for base64/MIME: {e}")
            return None

    def _run(self, 
             image_bytes: Optional[bytes] = None, 
             image_path: Optional[str] = None, 
             text_context: Optional[str] = None, 
             prompt_override: Optional[str] = None) -> Dict[str, Any]:

        if not self.vision_llm_client:
            return ImageAnalysisOutput(error_message="OpenAI client for vision not initialized.").model_dump()

        current_image_bytes = image_bytes
        if image_path and not current_image_bytes:
            try:
                with open(image_path, "rb") as f:
                    current_image_bytes = f.read()
            except Exception as e:
                return ImageAnalysisOutput(error_message=f"Failed to read image from path {image_path}: {e}").model_dump()

        if not current_image_bytes:
            return ImageAnalysisOutput(error_message="No image bytes or valid image path provided.").model_dump()

        mime_and_base64 = self._get_image_mime_type_and_base64(current_image_bytes)
        if not mime_and_base64:
            return ImageAnalysisOutput(error_message="Failed to determine image MIME type or base64 encode.").model_dump()
        
        mime_type, base64_image_data = mime_and_base64

        system_prompt = "You are an expert image analyst. Provide a detailed description, a concise caption, and 3-5 relevant keywords for the given image. Format your response as a JSON object with keys: \"description\", \"caption\", and \"keywords\" (which should be a list of strings)."
        
        user_messages_content = []
        main_prompt_text = prompt_override if prompt_override else f"Analyze this image. Optional context: {text_context if text_context else 'N/A'}"
        user_messages_content.append({"type": "text", "text": main_prompt_text})
        user_messages_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{base64_image_data}"}
        })

        try:
            print(f"ImageAnalysisLLMTool: Calling vision model ({settings.default_multimodal_llm_model}) for image analysis...")
            response = self.vision_llm_client.chat.completions.create(
                model=settings.default_multimodal_llm_model or "gpt-4-vision-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_messages_content}
                ],
                max_tokens=450, # Adjusted for potentially detailed descriptions + caption + keywords
                # response_format={"type": "json_object"} # Enable if model version supports it well for this task
            )
            llm_response_str = response.choices[0].message.content
            print(f"ImageAnalysisLLMTool: Received response: {llm_response_str[:200]}...")

            try:
                # Attempt to parse the entire response as JSON
                # Remove markdown fences if present
                cleaned_json_str = llm_response_str.strip()
                if cleaned_json_str.startswith("```json"):
                    cleaned_json_str = cleaned_json_str[7:]
                    if cleaned_json_str.endswith("```"):
                        cleaned_json_str = cleaned_json_str[:-3]
                elif cleaned_json_str.startswith("```"):
                    cleaned_json_str = cleaned_json_str[3:]
                    if cleaned_json_str.endswith("```"):
                        cleaned_json_str = cleaned_json_str[:-3]
                cleaned_json_str = cleaned_json_str.strip()

                data = json.loads(cleaned_json_str)
                return ImageAnalysisOutput(
                    description=data.get("description"),
                    caption=data.get("caption"),
                    keywords=data.get("keywords", [])
                ).model_dump()
            except json.JSONDecodeError as e_json_load:
                print(f"ImageAnalysisLLMTool: Failed to parse LLM response as JSON: {e_json_load}. Response was: {llm_response_str}")
                # Fallback: Try to extract from text if JSON parsing fails (more brittle)
                desc_match = re.search(r"description\":\s*\"(.*?)\"", llm_response_str, re.IGNORECASE | re.DOTALL)
                cap_match = re.search(r"caption\":\s*\"(.*?)\"", llm_response_str, re.IGNORECASE | re.DOTALL)
                key_match = re.search(r"keywords\":\s*(\[.*?\])", llm_response_str, re.IGNORECASE | re.DOTALL)
                
                description = desc_match.group(1).strip() if desc_match else "LLM response for description not in expected JSON format."
                caption = cap_match.group(1).strip() if cap_match else None
                keywords = []
                if key_match:
                    try: keywords = json.loads(key_match.group(1).strip())
                    except: pass # Ignore if keyword parsing also fails
                return ImageAnalysisOutput(description=description, caption=caption, keywords=keywords, error_message="LLM response not valid JSON, fallback parsing attempted.").model_dump()

        except Exception as e:
            print(f"ImageAnalysisLLMTool: Error during vision LLM call: {e}")
            import traceback; traceback.print_exc()
            return ImageAnalysisOutput(error_message=f"Vision LLM call failed: {str(e)}").model_dump()

# --- Input/Output Schemas for ContentStructuringLLMTool ---
class ContentStructuringInput(PydanticV2BaseModel):
    raw_text: str = PydanticV2Field(description="Full raw text content to be structured.")
    image_metadata: List[Dict[str, Any]] = PydanticV2Field(default_factory=list, description="List of image metadata dictionaries.")
    prompt_override: Optional[str] = PydanticV2Field(None, description="Optional specific prompt for content structuring rules.")

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

# --- ContentStructuringLLMTool ---
class ContentStructuringLLMHelper:
    llm_instance: Optional[ChatOpenAI]

    def __init__(self, llm_instance: Optional[ChatOpenAI] = None, settings_override: Optional[Any] = None):
        self.current_settings = settings_override if settings_override else settings
        self.llm_instance = llm_instance if llm_instance is not None else default_llm_client_for_tools
        if not self.llm_instance:
            print("ContentStructuringLLMHelper: WARNING - Initialized WITHOUT an LLM instance. Calls will fail.")
        else:
            print(f"ContentStructuringLLMHelper: Initialized with LLM: {self.llm_instance.model_name if hasattr(self.llm_instance, 'model_name') else 'unknown'}")

    def perform_direct_structuring(self, raw_text: str, image_metadata: List[Dict[str, Any]], prompt_override: Optional[str] = None) -> Dict[str, Any]:
        if not self.llm_instance:
            return ContentStructuringOutput(blocks=[], error_message="LLM not configured.").model_dump()
        
        print(f"[ContentStructuringLLMHelper.perform_direct_structuring] Called with raw_text length: {len(raw_text)}, images: {len(image_metadata)}")
        image_refs_segment = ""
        if image_metadata:
            image_details_list = []
            for img in image_metadata:
                details = f"- Image ID: {img.get('image_id')}"
                if img.get('caption'): details += f", Provided Caption: {img.get('caption')}" # Use actual caption from metadata
                image_details_list.append(details)
            if image_details_list:
                image_refs_segment = ("\n\nAvailable images for reference (use their Image ID to create 'image_reference' blocks. "
                                    "If a 'Provided Caption' is listed, use that exact caption for the image block; otherwise, the caption field must be null.):\n" 
                                    + "\n".join(image_details_list))

        system_prompt_content = (
    "You are an expert content structuring AI. Your task is to accurately segment the provided 'Raw Text to Structure' (found in the user prompt) "
    "into a sequence of content blocks and integrate image references, outputting a JSON object for the 'format_content_blocks' function. "
    "ABSOLUTE REQUIREMENT FOR 'content' FIELDS OF 'text', 'code', and 'math' BLOCKS: You MUST ONLY use the exact text provided in the 'Raw Text to Structure' section of the user prompt. "
    "Do NOT add, invent, paraphrase, or synthesize ANY new textual content, introductory/concluding sentences, or transitional phrases for these blocks. "
    "Every single word in a 'text', 'math', or 'code' block's 'content' field MUST be a direct, verbatim subsequence copied EXACTLY from the 'Raw Text to Structure'. "
    "You are an extractor and segmenter, NOT a creative writer or summarizer for these text-based fields. "
    "If a segment from the 'Raw Text to Structure' is suitable as is, use it with type 'text'. If a segment is clearly code, use type 'code'. If it is clearly math, use type 'math'. "
    "IMAGE CAPTIONS: For 'image_reference' blocks, if a 'Provided Caption' is available in the 'Available images for reference' list for that Image ID, you MUST use that exact caption. If no 'Provided Caption' is available for an image, the caption field in the output JSON MUST be null. DO NOT invent or generate captions. "
    "Segment the provided text into logical 'text', 'code', or 'math' blocks. All text segments MUST have type 'text'. Insert 'image_reference' blocks where appropriate based on image metadata and context. "
    "Your entire response MUST be a single, valid JSON object. This JSON object must have a key named 'blocks'. "
    "The value for the 'blocks' key must be a JSON list of content block objects, adhering strictly to the schema: "
    "'type' (must be one of [\"text\", \"image_reference\", \"code\", \"math\"]), and conditional 'content', 'image_id', 'caption' fields based on the type."
    "\nExample of the root JSON object format you must produce (this is the argument to the 'format_content_blocks' function):\n"
    "{\n"
    "  \"blocks\": [\n"
    "    {\"type\": \"text\", \"content\": \"Exact sentence from source text.\"},\n"
    "    {\"type\": \"image_reference\", \"image_id\": \"IMG_XYZ\", \"caption\": \"Caption from metadata or null if none.\"},\n"
    "    {\"type\": \"code\", \"content\": \"verbatim_code_from_source();\"},\n"
    "    {\"type\": \"math\", \"content\": \"E=mc^2\"}\n"
    "  ]\n"
    "}\n\n"
    "DETAILED EXAMPLES OF VERBATIM EXTRACTION and CORRECT TYPING for the 'blocks' argument:\n\n"
    "Example 1:\n"
    "If User Prompt's 'Raw Text to Structure' is:\n'''\nThis is the first paragraph. It has multiple sentences.\n\n## Section Title\nFollowed by more text. Some code: `val i = 10;`. This is math: $$E=mc^2$$. End of text.\n'''\n"
    "And 'Available images for reference' includes: \n- Image ID: IMG_001, Provided Caption: Diagram of a cat\n"
    "The 'blocks' argument you generate for 'format_content_blocks' MUST BE:\n"
    "{\n"
    "  \"blocks\": [\n"
    "    {\"type\": \"text\", \"content\": \"This is the first paragraph. It has multiple sentences.\"},\n"
    "    {\"type\": \"text\", \"content\": \"## Section Title\nFollowed by more text.\"}, \n"
    "    {\"type\": \"image_reference\", \"image_id\": \"IMG_001\", \"caption\": \"Diagram of a cat\"}, \n"
    "    {\"type\": \"text\", \"content\": \"Some code:\"},\n"
    "    {\"type\": \"code\", \"content\": \"val i = 10;\"},\n"
    "    {\"type\": \"text\", \"content\": \"This is math:\"},\n"
    "    {\"type\": \"math\", \"content\": \"E=mc^2\"},\n"
    "    {\"type\": \"text\", \"content\": \"End of text.\"}\n"
    "  ]\n"
    "}\n\n"
    "Example 2 (No Images):\n"
    "If User Prompt's 'Raw Text to Structure' is:\n'''\nOnly one sentence here.\nAnd another on a new line.\n'''\n"
    "The 'blocks' argument you generate for 'format_content_blocks' MUST BE:\n"
    "{\n"
    "  \"blocks\": [\n"
    "    {\"type\": \"text\", \"content\": \"Only one sentence here.\nAnd another on a new line.\"}\n"
    "  ]\n"
    "}\n"
)
        user_prompt_content = prompt_override or (
            f"Using ONLY the provided 'Raw Text to Structure' below, and the 'Available images for reference' list, segment the text and integrate image references. Adhere strictly to the schema and instructions given in the system prompt."
            f"{image_refs_segment}\n\nRaw Text to Structure:\n'''\n{raw_text}\n'''"
        )
        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": user_prompt_content}
        ]
        llm_tool_schema_for_call = { 
            "type": "function",
            "function": {
                "name": "format_content_blocks",
                "description": "Formats text and image info into a structured list of content blocks based on verbatim input text and image metadata.",
                "parameters": {
                    "type": "object",
                    "properties": {"blocks": {"type": "array", "items": block_item_schema_for_llm_tool["parameters"]["properties"]["blocks"]["items"], "description": "An array of content block objects."}},
                    "required": ["blocks"]
                }
            }
        }
        try:
            print(f"ContentStructuringLLMHelper: Calling LLM ({self.llm_instance.model_name if hasattr(self.llm_instance, 'model_name') else 'default'}) with function call for direct structuring...")
            response = self.llm_instance.invoke(
                messages,
                tools=[llm_tool_schema_for_call],
                tool_choice={"type": "function", "function": {"name": "format_content_blocks"}}
            )
            print(f"ContentStructuringLLMHelper: LLM response type: {type(response)}")
            print(f"ContentStructuringLLMHelper: LLM response repr: {response!r}")

            # Defensive check if tool_calls is present and is a list
            if hasattr(response, 'tool_calls') and response.tool_calls and isinstance(response.tool_calls, list) and len(response.tool_calls) > 0:
                first_tool_call = response.tool_calls[0]
                print(f"ContentStructuringLLMHelper: First tool_call type: {type(first_tool_call)}")
                print(f"ContentStructuringLLMHelper: First tool_call repr: {first_tool_call!r}")

                # Try accessing as a dictionary first, as suggested by the AttributeError
                tool_name = None
                tool_args_dict = None

                if isinstance(first_tool_call, dict):
                    tool_name = first_tool_call.get('name')
                    tool_args_str = first_tool_call.get('args') # args might be a string needing json.loads
                    if isinstance(tool_args_str, str):
                        try:
                            tool_args_dict = json.loads(tool_args_str)
                        except json.JSONDecodeError as e_json_args:
                            print(f"ContentStructuringLLMHelper: JSONDecodeError parsing tool_args_str: {e_json_args}. Args string was: {tool_args_str!r}")
                            tool_args_dict = {} # or handle error appropriately
                    elif isinstance(tool_args_str, dict): # If args is already a dict
                        tool_args_dict = tool_args_str
                    else:
                        tool_args_dict = {}


                # Fallback or alternative: if it's an object with .name and .args (standard Langchain ToolCall)
                elif hasattr(first_tool_call, 'name') and hasattr(first_tool_call, 'args'):
                    tool_name = first_tool_call.name
                    # The 'args' from a ToolCall object might be a string or already a dict.
                    if isinstance(first_tool_call.args, str):
                        try:
                            tool_args_dict = json.loads(first_tool_call.args)
                        except json.JSONDecodeError as e_json_args_obj:
                            print(f"ContentStructuringLLMHelper: JSONDecodeError parsing first_tool_call.args: {e_json_args_obj}. Args string was: {first_tool_call.args!r}")
                            tool_args_dict = {}
                    elif isinstance(first_tool_call.args, dict):
                        tool_args_dict = first_tool_call.args
                    else: # Should not happen with standard ToolCall
                        tool_args_dict = {}


                if tool_name == "format_content_blocks" and tool_args_dict is not None:
                    try:
                        validated_output = ContentStructuringOutput(**tool_args_dict)
                        print(f"ContentStructuringLLMHelper: LLM function call successful, {len(validated_output.blocks)} blocks structured.")
                        return validated_output.model_dump()
                    except Exception as e_pydantic_val:
                        error_msg = f"LLM function call output failed Pydantic validation: {e_pydantic_val}. Args: {tool_args_dict}"
                        print(f"ContentStructuringLLMHelper: {error_msg}")
                        return ContentStructuringOutput(blocks=[], error_message=error_msg).model_dump()
                else:
                    error_msg = f"LLM did not use the 'format_content_blocks' function as expected or args parsing failed. Name: {tool_name}, Args: {tool_args_dict}"
                    print(f"ContentStructuringLLMHelper: {error_msg} Full Response: {response!r}")
                    return ContentStructuringOutput(blocks=[], error_message=error_msg).model_dump()
            elif hasattr(response, 'content') and isinstance(response.content, str) and not response.tool_calls : # If it's an AIMessage with no tool calls, but text content
                error_msg = "LLM responded with plain text content instead of a tool call."
                print(f"ContentStructuringLLMHelper: {error_msg} Response content: {response.content!r}")
                return ContentStructuringOutput(blocks=[], error_message=error_msg).model_dump()
            else:
                error_msg = "LLM response did not contain expected tool_calls attribute or it was empty."
                print(f"ContentStructuringLLMHelper: {error_msg} Full Response: {response!r}")
                return ContentStructuringOutput(blocks=[], error_message=error_msg).model_dump()
        except Exception as e:
            print(f"ContentStructuringLLMHelper: Error during LLM call: {e}")
            import traceback; traceback.print_exc()
            return ContentStructuringOutput(blocks=[], error_message=str(e)).model_dump()

    class Config: 
        arbitrary_types_allowed = True

# This is needed for the print statements and time.sleep simulations inside the tools' mock _run methods.
# It's better to manage imports at the top level of the module.
# import time # Removed redundant import 

# Need re import for the ImageAnalysisLLMTool mock parsing logic
# import re # Removed from here

# Moved to module level for importability
block_item_schema_for_llm_tool = {
    "name": "format_content_blocks",
    "description": "Formats the extracted web content into a structured list of blocks (text, image_reference, code, math).",
    "parameters": {
        "type": "object",
        "properties": {
            "blocks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["text", "image_reference", "code", "math"]
                        },
                        "content": {
                            "type": "string",
                            "description": "Textual content for 'text', 'code', or 'math' blocks. Verbatim from source."
                        },
                        "image_id": {
                            "type": "string",
                            "description": "Unique identifier for an image, used in 'image_reference' type blocks."
                        },
                        "caption": {
                            "type": "string",
                            "description": "Caption for an image, used in 'image_reference' type blocks. From metadata or null."
                        }
                    },
                    "required": ["type"]
                },
                "description": "A list of content blocks representing the structured article."
            }
        },
        "required": ["blocks"]
    }
}