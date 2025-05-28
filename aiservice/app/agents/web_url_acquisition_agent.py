# Placeholder for TS-AI-Reconstruct-3: Web URL Content Acquisition Agent (HTML) 

import sys # Added import for sys
from crewai import Agent, Task
from typing import List, Type, Dict, Any, Optional
from pydantic import BaseModel
import os # For potential use in _extract_title_from_path if needed for file naming
import re # Added import for re here
from urllib.parse import urlparse
import json
import uuid

from app.tools.web_tools import WebContentFetcherTool, FetchedWebImage # WebContent model is used by the tool
from app.tools.utility_tools import DataStoreAccessTool
from app.models.web_acquisition_models import WebAcquisitionInput, WebAcquisitionOutput, ExtractedImageURLWithID

class WebURLContentAcquisitionAgent:
    """Fetches and parses HTML web pages according to processing_level for V2.4."""

    def __init__(self, web_content_fetcher_tool: WebContentFetcherTool, data_store_tool: DataStoreAccessTool):
        self.web_content_fetcher_tool = web_content_fetcher_tool
        self.data_store_tool = data_store_tool
        
        agent_tools = [self.web_content_fetcher_tool, self.data_store_tool]
        self.agent_instance = self._create_agent_instance(agent_tools)

    def _create_agent_instance(self, configured_tools: List[BaseModel]) -> Agent:
        return Agent(
            role='Web URL Content Acquisition Agent for V2.4',
            goal=('Fetch and parse HTML web pages based on URL and processing_level. ' 
                  'Extract main text, page title, and if full_content, image URLs with generated unique IDs (WEB_IMG_X). ' 
                  'Handle PDF redirections. Store outputs using DataStoreAccessTool and return references/status.'),
            backstory=(
                "You are a specialized agent in the CoreReconstructionCrew, focused on acquiring content from web URLs. " 
                "You use the WebContentFetcherTool to handle URL validation, HTTP fetching, paywall detection, content type checking (including PDF redirection), " 
                "main content extraction (e.g., via Trafilatura), and title extraction. " 
                "If 'processing_level' is 'full_content', you also extract image URLs and assign them unique sequential IDs like 'WEB_IMG_1', 'WEB_IMG_2'. " 
                "All significant extracted data (text, image URL lists, or downloaded PDF references) is stored via DataStoreAccessTool, and you return references to this data, along with the page title and final URL status."
            ),
            tools=configured_tools,
            verbose=True,
            allow_delegation=False
        )

    def get_agent(self) -> Agent:
        return self.agent_instance

    def _extract_title_from_path(self, url_or_path: str) -> str:
        # Basic title from URL, filename-like part
        name = url_or_path.split("?")[0].split("#")[0].split("/")[-1]
        if '.' in name: # if it looks like a filename an_article.html
            return os.path.splitext(name)[0]
        return name if name else "untitled_web_resource"

    def _sanitize_for_path(self, text: Optional[str], max_length: int = 100) -> str:
        if not text: return f"untitled_{uuid.uuid4().hex[:6]}"
        text = str(text)
        text = re.sub(r'[^a-zA-Z0-9._-]', '_', text)
        text = re.sub(r'_+', '_', text)
        text = text.strip('_')
        return text[:max_length]

    def execute_comprehensive_url_processing(self, input_data: WebAcquisitionInput, job_id_for_ds_keys: Optional[str] = None) -> WebAcquisitionOutput:
        print(f"WebURLAgent: Executing comprehensive URL processing for {input_data.url}, level: {input_data.processing_level}, job ID: {job_id_for_ds_keys}")
        job_id_suffix = f"_{job_id_for_ds_keys}" if job_id_for_ds_keys else "_no_job_id"
        
        # Sanitize part of the URL to use in DataStore keys for uniqueness
        # Taking the domain and first path part for a somewhat readable key prefix
        try:
            url_parts = input_data.url.split("//")[-1].split("/")
            domain_part = self._sanitize_for_path(url_parts[0], 30)
            path_part = self._sanitize_for_path(url_parts[1], 20) if len(url_parts) > 1 else "root"
            url_key_prefix = f"web_{domain_part}_{path_part}"
        except Exception:
            url_key_prefix = f"web_generic_{uuid.uuid4().hex[:8]}" # Fallback key prefix
        
        # Call the WebContentFetcherTool
        tool_output = self.web_content_fetcher_tool._run(url=input_data.url)
        print(f"WebURLAgent: tool_output from WebContentFetcherTool: {json.dumps(tool_output, indent=2, default=str)}") # Log the full tool output

        # Process the tool's output
        status = tool_output.get("status", "error_tool_did_not_return_status")
        final_url_after_redirects = tool_output.get("final_url")
        page_title_from_web = tool_output.get("page_title")
        extracted_text = tool_output.get("extracted_text")
        # Agent gets raw list of dicts from tool_output.get("images")
        raw_images_from_tool: List[Dict[str, Any]] = tool_output.get("images", []) 
        is_paywalled = tool_output.get("is_paywalled", False)
        pdf_download_path = tool_output.get("pdf_download_path") # If URL redirected to a PDF and was downloaded
        tool_error_message = tool_output.get("error")
        print(f"WebURLAgent: Extracted text from tool_output (before agent logic): {'None' if extracted_text is None else 'Populated'}, Length: {len(extracted_text.strip()) if extracted_text else 0}")

        text_content_ref: Optional[str] = None
        image_list_ref: Optional[str] = None
        downloaded_pdf_ref: Optional[str] = None
        agent_error_message: Optional[str] = tool_error_message
        final_agent_status = status # Start with tool status

        if status == "pdf_content_downloaded" and pdf_download_path:
            final_agent_status = "success_pdf_redirect"
            pdf_ref_key = f"{url_key_prefix}_pdf_content{job_id_suffix}"
            # Instead of storing bytes, let's assume WebContentFetcherTool gives a path it will manage or a temp path.
            # For now, we'll store the path itself. The PDF agent would then be invoked.
            # However, Orchestrator routes to PDF agent based on ContentTypeDetectionTool, not this path.
            # So, this downloaded_pdf_ref should be a signal or actual content if orchestrator can use it.
            # For V2.4, if it's a PDF, ContentTypeDetection will say PDF, and PDF agent handles it.
            # This path is more for if a URL *becomes* a PDF that the tool itself downloads.
            # Let's assume this is a local path for now.
            self.data_store_tool._run(action="put", key=pdf_ref_key, value=pdf_download_path) 
            downloaded_pdf_ref = pdf_ref_key
            # If it's a PDF, text/images would be extracted by the PDF agent, not here.
            # So, extracted_text and extracted_images from the web tool for this path might be None or irrelevant.
            extracted_text = None # Clear any web-extracted text if it became a PDF
            extracted_images = [] # Clear any web-extracted images

        elif extracted_text:
            text_ref_key = f"{url_key_prefix}_text_content{job_id_suffix}"
            self.data_store_tool._run(action="put", key=text_ref_key, value=extracted_text)
            text_content_ref = text_ref_key
            final_agent_status = "success" # Assuming text implies overall success for web page
        else:
            if final_agent_status not in ["success_pdf_redirect", "error_tool_did_not_return_status"] and not tool_error_message:
                 final_agent_status = "error_no_text_extracted"
                 agent_error_message = (agent_error_message + "; " if agent_error_message else "") + "No text content extracted by WebContentFetcherTool."
            elif not tool_error_message: # If status was an error but no message from tool
                 agent_error_message = (agent_error_message + "; " if agent_error_message else "") + f"WebContentFetcherTool returned status '{status}' but no error message and no text."

        if input_data.processing_level == "full_content" and raw_images_from_tool and final_agent_status != "success_pdf_redirect":
            processed_web_images: List[ExtractedImageURLWithID] = []
            for idx, img_dict in enumerate(raw_images_from_tool):
                try:
                    # Convert dict back to FetchedWebImage model instance
                    fetched_img = FetchedWebImage(**img_dict)
                    if fetched_img.url: # Check if url is not None
                        img_id = f"WEB_IMG_{idx + 1}{job_id_suffix}" 
                        processed_web_images.append(ExtractedImageURLWithID(
                            image_id=img_id,
                            image_url=str(fetched_img.url), # Ensure str
                            alt_text=fetched_img.alt_text # Corrected attribute name
                        ))
                except Exception as e_img_parse: # Catch potential Pydantic validation errors or others
                    print(f"WebURLAgent: Error parsing image dictionary into FetchedWebImage: {img_dict}, error: {e_img_parse}")
            
            if processed_web_images:
                image_list_key = f"{url_key_prefix}_image_list{job_id_suffix}"
                self.data_store_tool._run(action="put", key=image_list_key, value=json.dumps([img.model_dump() for img in processed_web_images]))
                image_list_ref = image_list_key
                if final_agent_status == "success": final_agent_status = "success_text_and_images"
            elif final_agent_status == "success": # Text but no images
                final_agent_status = "success_text_no_images"
        elif final_agent_status == "success": # Text only processing or no images found
             final_agent_status = "success_text_only_or_no_images_found"

        return WebAcquisitionOutput(
            status=final_agent_status,
            page_title_from_web=page_title_from_web,
            final_url_after_redirects=str(final_url_after_redirects) if final_url_after_redirects else None,
            extracted_text_content_ref=text_content_ref,
            extracted_image_url_list_with_ids_ref=image_list_ref,
            downloaded_pdf_path_ref=downloaded_pdf_ref,
            error_message=agent_error_message,
            is_paywalled=is_paywalled 
        )

    # --- Task Definition for Agent ---
    def comprehensive_url_processing_task(self, agent_to_use: Agent, input_data: WebAcquisitionInput) -> Task:
        """Task for comprehensively processing a URL to extract content and images."""
        
        # This task would be configured to call self.execute_comprehensive_url_processing
        # The CrewAI framework handles passing arguments if the task is defined with them
        # or passing context which can then be parsed by the action method.

        return Task(
            description=(
                f"Comprehensively process URL: {input_data.url} with processing level: {input_data.processing_level}. "
                f"This involves using the WebContentFetcherTool for fetching, parsing (including PDF redirection handling, paywall checks), "
                f"extracting main text, title, and image URLs. If 'full_content', generate unique IDs for images (e.g., WEB_IMG_X). "
                f"Store extracted data via DataStoreAccessTool and return structured output references and status."
            ),
            expected_output=(
                "A WebAcquisitionOutput model as a dictionary, containing status, page title, final URL, "
                "references to extracted text, list of image URLs with IDs (if applicable), and reference to downloaded PDF (if applicable), along with any error messages."
            ),
            agent=agent_to_use,
            # arguments=input_data.model_dump() # How input is passed to agent's method
            # To directly call execute_comprehensive_url_processing, its signature needs to match task action requirements.
            # Or, the agent's LLM uses its tools based on the description.
            # For now, assuming the agent's method will be called.
        )

# Placeholder for os module if not already imported by other parts of the file
if 'os' not in sys.modules:
    import os

# Placeholder for re module if not already imported
if 're' not in sys.modules:
    import re # This can be removed now or kept as a redundant check

# Agent-specific methods for orchestrating the processing of a URL could be added here.
# def process_url(self, url):
#     # 1. Validate URL
#     # 2. Fetch HTTP content
#     # 3. Detect paywall
#     # 4. Extract main content, images, title
#     # 5. Package output
#     pass

# Methods for URL validation, fetching, paywall detection, content/image extraction will be added here. 