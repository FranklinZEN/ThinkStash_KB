from crewai.tools import BaseTool
import base64
import requests # For illustration if calling a separate LLM service, or use OpenAI client
import os
import json # For constructing and parsing LLM I/O
from aiservice.app.config import get_openai_api_key # Import the accessor
from typing import Any, Optional, List, Dict, Type # Added Optional, List, Dict, Type
from openai import OpenAI # Keep the import for type hinting and potential direct use
from pydantic import BaseModel, Field

# Global client is removed from here.
# It will be initialized in CrewFactory and passed to tools.

class MultimodalLLMImageMarkerToolInput(BaseModel):
    image_path_or_base64: str = Field(description="File path to the image or a base64 encoded image string.")
    page_number: int = Field(description="The page number from which the image was extracted.")
    text_context: Optional[str] = Field(default=None, description="Optional text surrounding the image for context.")

class MultimodalLLMImageMarkerTool(BaseTool):
    name: str = "Multimodal LLM Image Analyzer"
    description: str = "Analyzes an image (from path or base64) to identify markers, descriptions, captions, etc., for a given page number and text context."
    args_schema: Type[BaseModel] = MultimodalLLMImageMarkerToolInput
    client: Optional[OpenAI] = None

    def __init__(self, client: Optional[OpenAI] = None, **kwargs):
        """Initializes the tool, optionally with a pre-configured LLM client."""
        super().__init__(**kwargs)
        self.client = client if client else openai_client_instance
        if self.client:
            print(f"{self.name}: Initialized with OpenAI client.")
        else:
            print(f"{self.name}: Initialized WITHOUT OpenAI client. Placeholder logic will be used.")

    def _run(self, image_path_or_base64: str, page_number: int, text_context: Optional[str] = None) -> str:
        print(f"{self.name}: Called with image (len: {len(image_path_or_base64)}), page: {page_number}, context: {bool(text_context)}")
        if not self.client:
            return json.dumps({"error": f"{self.name}: OpenAI client not configured."})
        if not image_path_or_base64:
            return json.dumps({"error": f"{self.name}: No image data provided."})

        # Placeholder for actual LLM call
        print("MultimodalLLMImageMarkerTool: Placeholder - LLM call would happen here.")
        # In a real scenario, image_path_or_base64 would be used to send to the LLM.
        # For the GCS upload task, we need to pass the original path.
        # Assuming image_path_or_base64 IS the path for now, as per test logs.
        page_image_path = image_path_or_base64 

        simulated_output = [{
            "marker_id": f"[IMAGE_MARKER_PAGE{page_number}_INDEX1]", 
            "description": "Simulated image desc.", 
            "local_path": image_path_or_base64 if len(image_path_or_base64) < 300 else "ref_to_image_data_too_long_for_log"
        }]
        return json.dumps(simulated_output)

class AdvancedLLMStructuringToolInput(BaseModel):
    source_document_text: Optional[str] = Field(description="The primary textual content.")
    image_details_list: List[Dict[str, Any]] = Field(default_factory=list, description="List of image objects with metadata.")
    source_content_type_hint: str = Field(description="Hint about the original content type.")
    page_title: Optional[str] = Field(default=None, description="Optional page title to help structure.")

class AdvancedLLMStructuringTool(BaseTool):
    name: str = "Advanced LLM Document Structurer"
    description: str = (
        "Uses an LLM to reconstruct a document into an ordered sequence of blocks: 'text', 'image', 'math', 'code'."
    )
    args_schema: Type[BaseModel] = AdvancedLLMStructuringToolInput
    client: Optional[OpenAI] = None # Allow client to be passed if needed

    def __init__(self, client: Optional[OpenAI] = None, **kwargs):
        super().__init__(**kwargs)
        self.client = client if client else openai_client_instance # Fallback to global if not provided
        if self.client:
            print(f"AdvancedLLMStructuringTool: Initialized with OpenAI client.")
        else:
            print(f"AdvancedLLMStructuringTool: Initialized WITHOUT an OpenAI client. Placeholder logic will be used.")

    def _run(self, 
             source_document_text: Optional[str],
             image_details_list: List[Dict[str, Any]], 
             source_content_type_hint: str,
             page_title: Optional[str] = None) -> str:
        print(f"AdvancedLLMStructuringTool: Running. Text length: {len(source_document_text) if source_document_text else 0}, Images: {len(image_details_list)}, Hint: {source_content_type_hint}, Title: {page_title}")
        
        simulated_blocks = []
        if page_title:
            simulated_blocks.append({"type": "text", "content": f"Title: {page_title}"})
        
        # Simple placeholder: interleave text chunks and images
        # A real implementation would use an LLM for semantic chunking and placement.
        if source_document_text:
            # Crude split by paragraphs for placeholder, LLM would be smarter
            text_paragraphs = [p.strip() for p in source_document_text.split('\n') if p.strip()]
            img_idx = 0
            for i, para in enumerate(text_paragraphs):
                simulated_blocks.append({"type": "text", "content": para})
                # Intersperse images (very naively)
                if i < len(image_details_list):
                    img_data = image_details_list[img_idx]
                    simulated_blocks.append({
                        "type": "image", 
                        "gcs_url": img_data.get('image_url'), # This is still image_url, not gcs_url yet
                        "alt_text": img_data.get('alt_text'),
                        "caption": img_data.get('caption')
                    })
                    img_idx += 1
            # Add any remaining images
            while img_idx < len(image_details_list):
                img_data = image_details_list[img_idx]
                simulated_blocks.append({
                    "type": "image", 
                    "gcs_url": img_data.get('image_url'),
                    "alt_text": img_data.get('alt_text'),
                    "caption": img_data.get('caption')
                })
                img_idx += 1

        elif image_details_list: # If no text but images exist
             for img_data in image_details_list:
                    simulated_blocks.append({
                        "type": "image", 
                        "gcs_url": img_data.get('image_url'),
                        "alt_text": img_data.get('alt_text'),
                        "caption": img_data.get('caption')
                    })
        
        if not simulated_blocks:
             simulated_blocks.append({"type": "text", "content": "No content processed by AdvancedLLMStructuringTool placeholder."})

        return json.dumps(simulated_blocks)

# It's good practice to have an explicit way to initialize the client if needed by tools.
# This can be done in the CrewFactory or a similar central place.
openai_client_instance: Optional[OpenAI] = None
try:
    api_key = get_openai_api_key()
    if api_key:
        openai_client_instance = OpenAI(api_key=api_key)
        print("llm_interaction_tools.py: OpenAI client initialized successfully.")
    else:
        print("llm_interaction_tools.py: OPENAI_API_KEY not found. LLM tools requiring it will use placeholders if no client is passed to them.")
except ImportError:
    print("llm_interaction_tools.py: OpenAI Python library not installed. LLM tools requiring it will use placeholders if no client is passed to them.")
except Exception as e:
    print(f"llm_interaction_tools.py: Error initializing OpenAI client: {e}. LLM tools will use placeholders if no client is passed to them.")

# Example Usage (illustrative, for testing the tool's structure and prompt generation):
if __name__ == '__main__':
    # print("\n--- MultimodalLLMImageMarkerTool Example (Direct Instantiate) ---")
    # marker_tool_no_client = MultimodalLLMImageMarkerTool()
    # print(marker_tool_no_client._run(image_path_or_base64="dummydata", page_number=1, text_context="Some text"))

    # if openai_client_instance:
    #     print("\n--- MultimodalLLMImageMarkerTool Example (With Client) ---")
    #     marker_tool_with_client = MultimodalLLMImageMarkerTool(client=openai_client_instance)
    #     print(marker_tool_with_client._run(image_path_or_base64="base64encodedimagedata", page_number=1, text_context="Some text context for the image."))
    
    # print("\n--- AdvancedLLMStructuringTool Example (Direct Instantiate) ---")
    # structuring_tool_no_client = AdvancedLLMStructuringTool()
    # sample_text_struct = "This is the first part of a document that needs structuring."
    # sample_images_struct = [
    #     {
    #         "original_source_identifier": "[IMAGE_MARKER_PAGE1_INDEX1]",
    #         "gcs_url": "gs://my-bucket/image_one.jpg",
    #         "alt_text": "A beautiful landscape."
    #     }
    # ]
    # print(structuring_tool_no_client._run(source_document_text=sample_text_struct, image_details_list=sample_images_struct, source_content_type_hint="pdf_with_markers"))

    # if openai_client_instance:
    #     print("\n--- AdvancedLLMStructuringTool Example (With Client) ---")
    #     structuring_tool_with_client = AdvancedLLMStructuringTool(client=openai_client_instance)
    #     print(structuring_tool_with_client._run(source_document_text=sample_text_struct, image_details_list=sample_images_struct, source_content_type_hint="pdf_with_markers"))

    # print("\n\n--- AdvancedLLMStructuringTool Example (Placeholder) ---")
    # structuring_tool = AdvancedLLMStructuringTool()
    # sample_text = "This is the first part. [IMAGE_MARKER_PAGE1_INDEX1] This is after the first image. Then some math: $$x^2$$"
    # sample_images = [
    #     {
    #         "original_source_identifier": "[IMAGE_MARKER_PAGE1_INDEX1]",
    #         "gcs_url": "gs://my-bucket/image_one.jpg",
    #         "alt_text": "A beautiful landscape.",
    #         "caption": "Photo by AI.",
    #         "llm_description": "A scenic view of mountains and a lake.",
    #         "context_before_text": "This is the first part.",
    #         "context_after_text": "This is after the first image."
    #     }
    # ]
    # hint = "pdf_with_markers"

    # structuring_result_json_str = structuring_tool._run(sample_text, sample_images, hint)
    # try:
    #     structuring_result_data = json.loads(structuring_result_json_str)
    #     print(json.dumps(structuring_result_data, indent=2))
    # except json.JSONDecodeError:
    #     print(f"Error: Structuring tool returned non-JSON string: {structuring_result_json_str}")
    # print("------------------------------------------------------") 
    pass # Keep the file non-empty and the __main__ block valid syntax 