import time
import json # Added for parsing LLM responses if they are JSON strings
import re # Moved to top
import base64 # For image encoding
import io # For BytesIO
from openai import OpenAI # Import OpenAI client
from pydantic import BaseModel, Field # Changed from pydantic.v1
from typing import Type, Dict, Optional, Any, List # Removed Annotated for now
from langchain_core.tools import BaseTool as LangchainCoreBaseTool, InjectedToolArg
from langchain_openai import ChatOpenAI
from pydantic import BaseModel as PydanticV2BaseModel, Field as PydanticV2Field
from PIL import Image # To determine MIME type for base64 encoding
from langchain_core.pydantic_v1 import BaseModel, Field, validator # For ContentStructuringOutput

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
    args_schema: Type[BaseModel] = ImageAnalysisInput
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

# Refers to aiservice.app.models.content_structuring_models.ContentBlock (or orchestration_models.ContentBlock)
# For now, let's use a generic structure that can be mapped.
class StructuredContentBlock(PydanticV2BaseModel):
    """Represents a single block of structured content, matching LLM function call schema."""
    type: str = PydanticV2Field(description="Type of content block (e.g., 'text', 'image_reference', 'code', 'math').")
    content: Optional[str] = PydanticV2Field(default=None, description="Text content for the block.")
    image_id: Optional[str] = PydanticV2Field(default=None, description="ID of the image for image blocks.")
    caption: Optional[str] = PydanticV2Field(default=None, description="Caption for the image.")
    # Removed alt_text from here to align with schema for now

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
                if img.get('caption'): details += f", Caption: {img.get('caption')}" # Use actual caption from metadata
                # No need to pass llm_description to this prompt, image_id and caption are enough for placement by LLM
                image_details_list.append(details)
            if image_details_list:
                image_refs_segment = "\n\nAvailable images for reference (use their Image ID and provided caption to create image_reference blocks):\n" + "\n".join(image_details_list)

        # This system_prompt_content is what the agent's LLM should use when it internally
        # makes the call to the LLM API with the format_content_blocks function.
        system_prompt_content = (
    "You are an expert content structuring AI. Your task is to accurately segment the provided 'Raw Text to Structure' (found in the user prompt) "
    "into a sequence of content blocks and integrate image references, outputting a JSON object for the 'format_content_blocks' function. "
    "ABSOLUTE REQUIREMENT FOR 'content' FIELDS: You MUST ONLY use the exact text provided in the 'Raw Text to Structure' section of the user prompt. "
    "Do NOT add, invent, paraphrase, or synthesize ANY new textual content, introductory/concluding sentences, or transitional phrases for the 'content' fields of 'text', 'math', or 'code' blocks. "
    "Every single word in a 'text', 'math', or 'code' block's 'content' field MUST be a direct, verbatim subsequence copied EXACTLY from the 'Raw Text to Structure'. "
    "You are an extractor and segmenter, NOT a creative writer or summarizer for these fields. "
    "If a segment from the 'Raw Text to Structure' is suitable as is, use it. If a segment implies a different type (e.g. an image placeholder that you convert to image_reference), handle that. "
    "Do not invent captions for image_reference blocks; use provided metadata or null. "
    "Segment the provided text into logical 'text', 'code', or 'math' blocks. Insert 'image_reference' blocks where appropriate based on image metadata. "
    "Your entire response MUST be a single, valid JSON object. This JSON object must have a key named 'blocks'. "
    "The value for the 'blocks' key must be a JSON list of content block objects, adhering strictly to the schema: "
    "'type' (enum: ['text', 'image_reference', 'code', 'math']), and conditional 'content', 'image_id', 'caption' fields."
    "\nExample of the root JSON object format you must produce (this is the argument to the 'format_content_blocks' function):\n"
    "{\n"
    "  \"blocks\": [\n"
    "    {\"type\": \"text\", \"content\": \"Exact sentence from source text.\"},\n"
    "    {\"type\": \"image_reference\", \"image_id\": \"IMG_XYZ\", \"caption\": \"Caption from metadata or null if none.\"},\n"
    "    {\"type\": \"code\", \"content\": \"verbatim_code_from_source();\"}\n"
    "  ]\n"
    "}\n\n"
    "DETAILED EXAMPLES OF VERBATIM EXTRACTION for the 'blocks' argument:\n\n"
    "Example 1:\n"
    "If User Prompt's 'Raw Text to Structure' is:\n'''\nThis is the first sentence. Some code: `val i = 10;`. This is math: $$E=mc^2$$. End of text.\n'''\n"
    "The 'blocks' argument you generate for 'format_content_blocks' MUST BE:\n"
    "{\n"
    "  \"blocks\": [\n"
    "    {\"type\": \"text\", \"content\": \"This is the first sentence.\"},\n"
    "    {\"type\": \"code\", \"content\": \"val i = 10;\"},\n"
    "    {\"type\": \"math\", \"content\": \"E=mc^2\"},\n"
    "    {\"type\": \"text\", \"content\": \"End of text.\"}\n"
    "  ]\n"
    "}\n\n"
    "Example 2:\n"
    "If User Prompt's 'Raw Text to Structure' is:\n'''\nOnly one sentence here.\n'''\n"
    "The 'blocks' argument you generate for 'format_content_blocks' MUST BE:\n"
    "{\n"
    "  \"blocks\": [\n"
    "    {\"type\": \"text\", \"content\": \"Only one sentence here.\"}\n"
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
                    "properties": {"blocks": {"type": "array", "items": block_item_schema_for_llm_tool, "description": "An array of content block objects."}},
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
            if response.tool_calls and response.tool_calls[0].name == "format_content_blocks":
                tool_call_args_dict = response.tool_calls[0]['args']
                try:
                    validated_output = ContentStructuringOutput(**tool_call_args_dict)
                    print(f"ContentStructuringLLMHelper: LLM function call successful, {len(validated_output.blocks)} blocks structured.")
                    return validated_output.model_dump()
                except Exception as e_pydantic_val:
                    error_msg = f"LLM function call output failed Pydantic validation: {e_pydantic_val}. Args: {tool_call_args_dict}"
                    print(f"ContentStructuringLLMHelper: {error_msg}")
                    return ContentStructuringOutput(blocks=[], error_message=error_msg).model_dump()
            else:
                error_msg = "LLM did not use the 'format_content_blocks' function as expected."
                print(f"ContentStructuringLLMHelper: {error_msg} Response: {response}")
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