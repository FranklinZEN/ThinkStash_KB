from crewai.tools import BaseTool
import base64
import requests # For illustration if calling a separate LLM service, or use OpenAI client
import os
import json # For constructing and parsing LLM I/O
from aiservice.app.config import get_openai_api_key # Import the accessor
from typing import Any, Optional # Added Optional
from openai import OpenAI # Keep the import for type hinting and potential direct use

# Global client is removed from here.
# It will be initialized in CrewFactory and passed to tools.

class MultimodalLLMImageMarkerTool(BaseTool):
    """Analyzes PDF page images using a multimodal LLM for image understanding.

    This tool takes an image of a PDF page, sends it to a multimodal LLM
    (like GPT-4 Vision/GPT-4o), and processes the LLM's response to extract
    structured information about visual elements (images/figures) on the page.
    This includes generating unique markers, descriptions, captions, and contextual
    information for each identified visual element.

    Attributes:
        name (str): The name of the tool.
        description (str): A detailed description of what the tool does, its inputs, and outputs.
        client: An instance of an LLM client (e.g., OpenAI client) if direct API calls are made.
                    Alternatively, this tool might rely on the agent's default LLM if configured for vision.
    """
    name: str = "Multimodal LLM Image Analyzer for PDF Pages"
    description: str = (
        "Analyzes an image of a PDF page using a powerful multimodal LLM (like GPT-4 Turbo or GPT-4o). "
        "Identifies distinct images/figures (excluding rendered math if handled separately). "
        "For each identified visual element, it extracts/generates: a unique marker ID, a visual description, "
        "any associated caption text, text snippets immediately preceding and succeeding the image, and its ordinal position. "
        "Input: 'image_base64_data' (string: base64 encoded image), 'page_number' (int), 'text_context' (string: text from the page or around potential images)."
        "Returns a JSON string with a list of identified image details or an error message."
    )
    client: Optional[OpenAI] = None

    def __init__(self, client: Optional[OpenAI] = None, **kwargs):
        """Initializes the tool, optionally with a pre-configured LLM client."""
        super().__init__(**kwargs)
        self.client = client
        if self.client:
            print(f"MultimodalLLMImageMarkerTool: Initialized with provided OpenAI client.")
        else:
            print(f"MultimodalLLMImageMarkerTool: Initialized WITHOUT an OpenAI client. Placeholder logic will be used.")

    def _run(self, image_base64_data: str, page_number: int, text_context: str = "") -> str:
        print(f"MultimodalLLMImageMarkerTool: Running for page {page_number}. Context length: {len(text_context)}")
        if not self.client:
            print("MultimodalLLMImageMarkerTool: No OpenAI client available. Returning placeholder error.")
            return json.dumps({"error": "OpenAI client not configured for MultimodalLLMImageMarkerTool"})
        if not image_base64_data:
            return json.dumps({"error": "No image data provided to MultimodalLLMImageMarkerTool"})

        # Placeholder for actual LLM call
        print("MultimodalLLMImageMarkerTool: Placeholder - LLM call would happen here.")
        # In a real scenario, image_base64_data would be used to send to the LLM.
        # For the GCS upload task, we need to pass the original path.
        # Assuming image_base64_data IS the path for now, as per test logs.
        page_image_path = image_base64_data 

        simulated_output = [
            {
                "marker_id": f"[IMAGE_MARKER_PAGE{page_number}_INDEX1]",
                "description": "A simulated description of an image.",
                "caption": "Simulated caption.",
                "context_before": text_context[:50],
                "context_after": text_context[-50:],
                "ordinal_position": 1,
                "local_path": page_image_path # Changed key to local_path
            }
        ]
        return json.dumps(simulated_output)

class AdvancedLLMStructuringTool(BaseTool):
    name: str = "Advanced LLM Document Structurer"
    description: str = (
        "Uses a powerful LLM (like GPT-4 Turbo or GPT-4o) to reconstruct a document into a clean, ordered sequence of blocks: 'text', 'image', 'math', and 'code'. "
        "Input requires: 'source_document_text' (string: the primary textual content, may contain image markers, LaTeX, or pre-formatted code), "
        "'image_details_list' (list of dicts: image objects with metadata like 'original_source_identifier' matching markers, 'gcs_url', 'alt_text', 'caption', 'llm_description', 'context_before_text', 'context_after_text'), "
        "and 'source_content_type_hint' (string: e.g., 'pdf_with_markers', 'docx_with_placeholders', 'html_with_context', 'docx_raw_no_placeholders' to guide image placement strategy)."
        "Returns a string containing a single JSON list of these blocks in the correct sequential order, or an error JSON object."
    )
    client: Optional[OpenAI] = None

    def __init__(self, client: Optional[OpenAI] = None, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        if self.client:
            print(f"AdvancedLLMStructuringTool: Initialized with provided OpenAI client.")
        else:
            print(f"AdvancedLLMStructuringTool: Initialized WITHOUT an OpenAI client. Placeholder logic will be used.")

    def _run(self, source_document_text: str, image_details_list: list[dict], source_content_type_hint: str) -> str:
        print(f"AdvancedLLMStructuringTool: Running. Text length: {len(source_document_text)}, Images: {len(image_details_list)}, Hint: {source_content_type_hint}")
        if not self.client:
            print("AdvancedLLMStructuringTool: No OpenAI client available. Returning placeholder error.")
            return json.dumps({"error": "OpenAI client not configured for AdvancedLLMStructuringTool"})

        # Placeholder for actual LLM call
        print("AdvancedLLMStructuringTool: Placeholder - LLM structuring call would happen here.")
        # Simulate LLM output for structuring
        simulated_blocks = [
            {"type": "text", "content": source_document_text[:100] + "... (structured snippet)"},
        ]
        if image_details_list:
            simulated_blocks.append({"type": "image", "data": image_details_list[0]})
        
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
    # print(marker_tool_no_client._run(image_base64_data="dummydata", page_number=1, text_context="Some text"))

    # if openai_client_instance:
    #     print("\n--- MultimodalLLMImageMarkerTool Example (With Client) ---")
    #     marker_tool_with_client = MultimodalLLMImageMarkerTool(client=openai_client_instance)
    #     print(marker_tool_with_client._run(image_base64_data="base64encodedimagedata", page_number=1, text_context="Some text context for the image."))
    
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