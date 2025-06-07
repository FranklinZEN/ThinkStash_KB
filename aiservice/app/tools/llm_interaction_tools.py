from crewai.tools import BaseTool
import base64
import requests # For illustration if calling a separate LLM service, or use OpenAI client
import os
import json # For constructing and parsing LLM I/O
from aiservice.app.config.settings import settings # Corrected import
from typing import Any, Optional, List, Dict, Type # Added Optional, List, Dict, Type
from openai import OpenAI # Keep the import for type hinting and potential direct use
from pydantic import BaseModel, Field
from langchain_core.tools import tool

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
        print(f"{self.name}: Called with image path: {image_path_or_base64}, page: {page_number}, context: {bool(text_context)}")

        if not self.client:
            print(f"{self.name}: OpenAI client not configured. Returning placeholder/simulated output.")
            simulated_findings = []
            if page_number % 2 == 1: 
                simulated_findings.append({
                    "id": "figure_1", 
                    "type": "placeholder_chart",
                    "description": f"Placeholder description for page {page_number}."
                })
            return json.dumps(simulated_findings)

        if not os.path.exists(image_path_or_base64):
            return json.dumps([{"error": f"{self.name}: Image file not found at {image_path_or_base64}"}])

        try:
            with open(image_path_or_base64, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            return json.dumps([{"error": f"{self.name}: Could not read/encode image file {image_path_or_base64}: {e}"}])
        
        image_media_type = "image/png" 
        if image_path_or_base64.lower().endswith( (".jpg", ".jpeg")):
            image_media_type = "image/jpeg"

        # --- Stage 1: Get Natural Language Description from Vision LLM (gpt-4o) --- 
        vision_prompt_text = f"""
Analyze the provided image from page {page_number} of a document. 
Describe in detail all distinct visual elements such as figures, diagrams, charts, photographs, tables, etc. 
For each element, try to infer a natural identifier (e.g., 'Figure 1', 'Sales Chart Q2', 'Company Logo') and provide a comprehensive description of its content and purpose. If there is text within an element (like titles or labels), include it in your description. 
Consider the following text context from the page to help understand the visual elements: 
---TEXT CONTEXT BEGIN---
{text_context if text_context else 'No text context provided for this page image.'}
---TEXT CONTEXT END---
Your output should be a single block of natural language text covering all identified elements and their detailed descriptions.
"""
        user_vision_messages = [
            {"role": "user", "content": [
                {"type": "text", "text": vision_prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:{image_media_type};base64,{base64_image}"}}
            ]}
        ]

        natural_language_description_of_elements = ""
        try:
            print(f"{self.name}: Sending Stage 1 (Vision Analysis) request to LLM (gpt-4o) for page {page_number}...")
            vision_response = self.client.chat.completions.create(
                model="gpt-4o", 
                messages=user_vision_messages,
                max_tokens=1500, # Increased for potentially verbose descriptions
                temperature=0.3 
            )
            natural_language_description_of_elements = vision_response.choices[0].message.content
            print(f"{self.name}: Received Stage 1 (Vision Analysis) response for page {page_number}: {natural_language_description_of_elements[:400]}...")
            if not natural_language_description_of_elements or natural_language_description_of_elements.strip() == "":
                 print(f"{self.name}: Vision LLM returned empty description for page {page_number}. Returning empty findings.")
                 return json.dumps([]) 
        except Exception as e_vision:
            print(f"{self.name}: ERROR - Vision LLM call (Stage 1) failed for page {page_number}: {e_vision}")
            return json.dumps([{"error": f"Vision LLM call failed: {e_vision}"}])

        # --- Stage 2: Extract JSON from Natural Language Description using a Text LLM (gpt-4o-mini) --- 
        json_extraction_system_prompt = """
You will receive a detailed textual description of visual content from a PDF page. Your task is to precisely extract and structure key information into a JSON list.

### Instructions:
- Review the provided description carefully.
- Identify each visual element described (e.g., figures, diagrams, charts, graphs, tables, photographs).
- Assign a unique incremental ID to each element, starting from "figure_1", then "figure_2", and so on. This ID should be based on the order of appearance or logical flow if multiple elements are described.
- For each element, provide:
  - `id`: The unique incremental ID (e.g., "figure_1").
  - `type`: The type of the element (e.g., "chart", "diagram", "photograph", "table", "graph", "illustration", "unknown").
  - `description`: A concise description of the element (max. 1-2 sentences).
  - `caption`: If a caption is explicitly mentioned or clearly inferable for the element from the input text, include it. Otherwise, use `null`.
- Follow the JSON schema exactly. All fields (`id`, `type`, `description`, `caption`) must be present for each object.

### Desired JSON Schema Example:
[
  {
    "id": "figure_1",
    "type": "chart",
    "description": "Line chart showing monthly sales growth from Jan to Dec 2023.",
    "caption": "Monthly Sales Growth (2023)"
  },
  {
    "id": "figure_2",
    "type": "photograph",
    "description": "Photograph of the company's headquarters building.",
    "caption": null
  }
]

YOUR ENTIRE RESPONSE MUST BE A VALID JSON LIST OF OBJECTS. 
DO NOT INCLUDE ANY EXPLANATORY TEXT, MARKDOWN FORMATTING, OR ANYTHING ELSE OUTSIDE OF THE JSON LIST ITSELF.
IF NO DISTINCT VISUAL ELEMENTS are clearly described in the input text, YOU MUST RETURN AN EMPTY JSON LIST: `[]`.
"""
        json_extraction_user_prompt = f"""Convert the following detailed description into the JSON format above:

Description:
```
{natural_language_description_of_elements}
```
""" 

        try:
            text_llm_model_for_extraction = "gpt-4o-mini" 
            print(f"{self.name}: Sending Stage 2 (JSON Extraction) request to LLM ({text_llm_model_for_extraction}) for page {page_number}...")
            
            json_response = self.client.chat.completions.create(
                model=text_llm_model_for_extraction, 
                messages=[
                    {"role": "system", "content": json_extraction_system_prompt},
                    {"role": "user", "content": json_extraction_user_prompt}
                ],
                max_tokens=1024, 
                temperature=0.1, 
                response_format={"type": "json_object"}
            )
            llm_json_output_str = json_response.choices[0].message.content
            print(f"{self.name}: Received Stage 2 (JSON Extraction) response for page {page_number}: {llm_json_output_str[:400]}...")

            if llm_json_output_str.strip().startswith("```json"):
                llm_json_output_str = llm_json_output_str.strip()[7:-3].strip()
            elif llm_json_output_str.strip().startswith("```"):
                 llm_json_output_str = llm_json_output_str.strip()[3:-3].strip()
            
            try:
                parsed_outer = json.loads(llm_json_output_str)
                final_findings_list = []

                if isinstance(parsed_outer, list):
                    final_findings_list = parsed_outer
                elif isinstance(parsed_outer, dict):
                    if "id" in parsed_outer and "type" in parsed_outer and "description" in parsed_outer and "caption" in parsed_outer:
                        print(f"{self.name}: Stage 2 LLM returned a single JSON object for a finding, wrapping it in a list.")
                        final_findings_list = [parsed_outer]
                    elif len(parsed_outer.keys()) == 1: 
                        key_for_list = list(parsed_outer.keys())[0]
                        if isinstance(parsed_outer[key_for_list], list):
                            final_findings_list = parsed_outer[key_for_list]
                            print(f"{self.name}: Stage 2 LLM returned JSON object with list under key '{key_for_list}'.")
                        # Check if the single key itself contains a single valid finding object
                        elif isinstance(parsed_outer[key_for_list], dict) and \
                             "id" in parsed_outer[key_for_list] and \
                             "type" in parsed_outer[key_for_list] and \
                             "description" in parsed_outer[key_for_list] and \
                             "caption" in parsed_outer[key_for_list]:
                             print(f"{self.name}: Stage 2 LLM returned JSON object with single finding under key '{key_for_list}', wrapping it.")
                             final_findings_list = [parsed_outer[key_for_list]]
                        else:
                            raise ValueError(f"LLM returned JSON obj with key '{key_for_list}', but value was not list or valid single finding dict (incl. caption).")
                    else:
                        raise ValueError("LLM returned a JSON dictionary not in an expected list-providing format or as a single valid finding (incl. caption).")
                else:
                    raise ValueError("LLM response was valid JSON, but not a list or a recognized dictionary structure.")
                
                validated_findings = []
                for item in final_findings_list:
                    # Ensure all required fields are present, caption can be null but must exist as a key
                    if isinstance(item, dict) and \
                       "id" in item and \
                       "type" in item and \
                       "description" in item and \
                       "caption" in item: # Caption key must be present
                        item["image_id_within_page"] = item.pop("id")
                        validated_findings.append(item)
                    else:
                        print(f"{self.name}: Warning - Skipping invalid item in JSON list (missing id, type, description, or caption key): {item}")
                return json.dumps(validated_findings)

            except json.JSONDecodeError as je_inner:
                print(f"{self.name}: ERROR - Stage 2 response was not valid JSON for page {page_number}: {je_inner}. Response: {llm_json_output_str}")
                return json.dumps([{"error": f"Stage 2 LLM response was not valid JSON: {je_inner}"}])
            except ValueError as ve_inner:
                print(f"{self.name}: ERROR - Stage 2 JSON structure incorrect for page {page_number}: {ve_inner}. Response: {llm_json_output_str}")
                return json.dumps([{"error": f"Stage 2 LLM JSON structure incorrect: {ve_inner}"}])

        except Exception as e_json_extract:
            print(f"{self.name}: ERROR - JSON Extraction LLM call (Stage 2) failed for page {page_number}: {e_json_extract}")
            return json.dumps([{"error": f"JSON Extraction LLM call failed: {e_json_extract}"}])

class AdvancedLLMStructuringToolInput(BaseModel):
    source_document_text: Optional[str] = Field(description="The primary textual content.")
    image_details_list: List[Dict[str, Any]] = Field(default_factory=list, description="List of image objects with metadata.")
    source_content_type_hint: str = Field(description="Hint about the original content type.")
    page_title: Optional[str] = Field(default=None, description="Optional page title to help structure.")

class AdvancedLLMStructuringTool(BaseTool):
    name: str = "Advanced LLM Document Structurer"
    description: str = (
        "Uses an LLM to reconstruct a document into an ordered sequence of blocks: 'text', 'image', 'math', 'code', inserting image placeholders."
    )
    args_schema: Type[BaseModel] = AdvancedLLMStructuringToolInput
    client: Optional[OpenAI] = None 
    model_name: str = "gpt-4o-mini" # Default model

    def __init__(self, client: Optional[OpenAI] = None, model_name: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.client = client if client else openai_client_instance # Fallback to global if not provided
        if model_name: self.model_name = model_name
        
        if self.client:
            print(f"AdvancedLLMStructuringTool: Initialized with OpenAI client for model {self.model_name}.")
        else:
            print(f"AdvancedLLMStructuringTool: Initialized WITHOUT an OpenAI client. Placeholder logic will be used for {self.model_name}.")

    def _run(self, 
             source_document_text: Optional[str],
             image_details_list: List[Dict[str, Any]], 
             source_content_type_hint: str,
             page_title: Optional[str] = None) -> str: # Returns a JSON string of List[Dict]
        print(f"AdvancedLLMStructuringTool: Running ({self.model_name}). Text length: {len(source_document_text) if source_document_text else 0}, Images hints: {len(image_details_list)}, Hint: {source_content_type_hint}, Title: {page_title}")
        
        if not self.client:
            print("AdvancedLLMStructuringTool: No OpenAI client configured. Returning placeholder/simulated output.")
            # Simplified placeholder from previous step, adapt if needed for more specific simulation
            simulated_blocks = []
            if page_title: simulated_blocks.append({"type": "text", "content": f"Title: {page_title}"})
            if source_document_text: simulated_blocks.append({"type": "text", "content": source_document_text[:500] + ("..." if len(source_document_text) > 500 else "")}) # Snippet
            if image_details_list: 
                placeholder = f"[Image Reference: {image_details_list[0].get('original_source_identifier')}]"
                if simulated_blocks and simulated_blocks[-1]["type"] == "text":
                    simulated_blocks[-1]["content"] += f" {placeholder}"
                else:
                    simulated_blocks.append({"type": "text", "content": placeholder})
            if not simulated_blocks: simulated_blocks.append({"type": "text", "content": "(Placeholder: No content)"})
            return json.dumps(simulated_blocks)

        if not source_document_text:
            # If there's no text, but there are images, the gallery will be appended by the agent.
            # Return an empty list of blocks or a specific message block.
            return json.dumps([{"type": "text", "content": "(No textual content to structure from source)"}])

        system_prompt = f"""
You are an expert document structuring AI. Your task is to process the provided document text and a list of associated image metadata.
Re-structure the document text into a list of content blocks. Valid block types are "text", "code", and "math".

Instructions:
1.  **Text Blocks**: Maintain semantic paragraphs or logical chunks from the original text.
2.  **Code Blocks**: Identify code snippets. If the source_content_type_hint is 'md' and a language is specified in a fenced code block (e.g., ```python), include a 'language' field in the code block object (e.g., {{"type": "code", "language": "python", "content": "..."}}). Otherwise, omit 'language' or use 'plaintext'. Preserve code formatting (indentation, newlines).
3.  **Math Blocks**: Identify mathematical formulas, especially LaTeX (e.g., $$...$$ or \\[...\\]), and wrap them in "math" blocks. Preserve the LaTeX.
4.  **Source Hint**: The source_content_type_hint ('{source_content_type_hint}') indicates the original format. Pay attention to markdown syntax if 'md'. For 'pdf_extracted_text', omit '--- Page Break ---' markers or use them to inform paragraph breaks.
5.  **Image Placeholders**: You are given a list of image metadata (image_reference_hints). Each image has an 'original_source_identifier'.
    *   For each unique 'original_source_identifier' in 'image_reference_hints', find the *single most semantically relevant place* in the document text to insert its reference.
    *   Insert the placeholder EXACTLY in this format: `[Image Reference: EXACT_ORIGINAL_SOURCE_IDENTIFIER_HERE]`.
    *   The placeholder MUST be inserted *within an existing or newly segmented text block*, not as a standalone block that only contains the placeholder. It should flow naturally with the surrounding text.
    *   Use each unique image reference from the input list *at most once*.
    *   Do NOT create 'image' type blocks yourself; only insert the text-based placeholders.
6.  **Completeness**: Ensure all original text is represented, segmented appropriately. Do not invent new text. Remove any "Figure X:" or "Table Y:" text from the original document if an image placeholder corresponding to that figure/table is being inserted nearby, to avoid redundancy.
7.  **Output Format**: Respond ONLY with a valid JSON list of block objects. Each object must have "type" (string: "text", "code", or "math") and "content" (string). Code blocks can optionally have "language".
    Example JSON output structure:
    [
      {{"type": "text", "content": "Introduction paragraph that discusses a concept illustrated in an image. [Image Reference: IMG_ID_01] This paragraph continues after the image reference."}},
      {{"type": "code", "language": "python", "content": "print('Hello')\\n# More code"}},
      {{"type": "math", "content": "E = mc^2"}}
    ]
Ensure the JSON is a single list at the root. If the input `document_text` is empty or None, return an empty list [].
"""

        user_message_content = {
            "document_info": {
                 "page_title": page_title,
                 "source_content_type_hint": source_content_type_hint
            },
            "source_document_text": source_document_text,
            "image_reference_hints": image_details_list
        }

        try:
            print(f"AdvancedLLMStructuringTool: Sending request to {self.model_name}...")
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_message_content)} # Send structured input as JSON string
                ],
                response_format={"type": "json_object"} # Request JSON output if model supports it
            )
            
            response_content = completion.choices[0].message.content
            print(f"AdvancedLLMStructuringTool: Received raw response: {response_content[:500]}...")
            
            try:
                # Attempt to parse the entire JSON object response first
                parsed_json_object = json.loads(response_content)
                
                if isinstance(parsed_json_object, dict) and "blocks" in parsed_json_object and isinstance(parsed_json_object["blocks"], list):
                    list_of_blocks_str = json.dumps(parsed_json_object["blocks"])
                    json.loads(list_of_blocks_str) # Validate
                    print("AdvancedLLMStructuringTool: Successfully extracted 'blocks' list from LLM JSON object.")
                    return list_of_blocks_str 
                elif isinstance(parsed_json_object, dict) and "result" in parsed_json_object and isinstance(parsed_json_object["result"], list):
                    list_of_blocks_str = json.dumps(parsed_json_object["result"])
                    json.loads(list_of_blocks_str) # Validate
                    print("AdvancedLLMStructuringTool: Successfully extracted list from 'result' key in LLM JSON object.")
                    return list_of_blocks_str
                elif isinstance(parsed_json_object, dict) and "content" in parsed_json_object and isinstance(parsed_json_object["content"], list):
                    # Handle if the LLM wraps the list under a "content" key
                    list_of_blocks_str = json.dumps(parsed_json_object["content"])
                    json.loads(list_of_blocks_str) # Validate
                    print("AdvancedLLMStructuringTool: Successfully extracted list from 'content' key in LLM JSON object.")
                    return list_of_blocks_str
                elif isinstance(parsed_json_object, list):
                    print("AdvancedLLMStructuringTool: LLM returned a direct JSON list as top-level object.")
                    return response_content
                else:
                    raise ValueError("LLM response was valid JSON, but not in the expected format (object with 'blocks', 'result', or 'content' list, or a direct list).")

            except json.JSONDecodeError as je:
                # This means response_content was not a valid JSON string at all.
                print(f"AdvancedLLMStructuringTool: Failed to parse LLM response as JSON: {je}. Response: {response_content[:1000]}")
                raise ValueError(f"LLM returned non-JSON response: {je}")
            except Exception as e_struct:
                 print(f"AdvancedLLMStructuringTool: Error processing LLM response structure: {e_struct}. Response: {response_content[:1000]}")
                 raise # Re-raise to be caught by the broader exception handler below
            
        except Exception as e:
            print(f"AdvancedLLMStructuringTool: Error during LLM call or parsing response: {e}")
            # Fallback to a simple text block with error information
            error_block = {
                "type": "text", 
                "content": f"Error during LLM structuring: {str(e)}. Original text might be truncated or missing.\n--- BEGIN ORIGINAL TEXT (Partial) ---\n{source_document_text[:1000] if source_document_text else 'No source text.'}\n--- END ORIGINAL TEXT (Partial) ---"
            }
            return json.dumps([error_block])

# It's good practice to have an explicit way to initialize the client if needed by tools.
# This can be done in the CrewFactory or a similar central place.
openai_client_instance: Optional[OpenAI] = None
try:
    if settings.openai_api_key:
        openai_client_instance = OpenAI(api_key=settings.openai_api_key)
        print("llm_interaction_tools.py: OpenAI client initialized successfully using settings.openai_api_key.")
    else:
        print("llm_interaction_tools.py: OPENAI_API_KEY not found in settings. LLM tools requiring it will use placeholders if no client is passed to them.")
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