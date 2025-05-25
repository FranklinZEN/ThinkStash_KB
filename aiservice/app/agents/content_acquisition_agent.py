"""Agent responsible for fetching and initially processing content from URLs or files."""

from crewai import Agent, Task # Assuming these are the correct base classes
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Union, Dict, Any
import re # Ensure re is imported for the new URL parsing

# Import tools
from app.tools.web_content_fetcher_tool import WebContentFetcherTool, WebContent, FetchedWebImage
from app.tools.file_content_extractor_tool import FileContentExtractorTool, FileContent, ExtractedFileImage

# Import shared Pydantic models for standardized output
from app.models.content_models import AcquiredContent, ImageRefUrl, ImageRefData

import os # For path operations if needed for filename from URL
from urllib.parse import urlparse # For extracting filename from URL

class ContentAcquisitionAgent(Agent): # Or directly from BaseAgent if that's what CrewAI uses
    """
    Content Acquisition Agent for ThinkStash.
    Fetches content from web URLs or local files, performs initial processing,
    and returns a standardized AcquiredContent object.
    Refer to TS-AI-4 & TS-AI-4.5 Development Plan - V1.2 for details.
    """
    def __init__(self, llm: Optional[Any] = None, verbose: bool = False):
        # Define role, goal, and backstory as per V1.2 plan (TS-AI-4 Core Agent Structure)
        # Note: CrewAI Agent constructor might vary. Adjust as per actual CrewAI setup.
        # If an LLM is not directly needed for this agent's orchestration logic (as it primarily uses tools),
        # it might be optional or configured differently.
        super().__init__(
            role="Expert Content Acquirer",
            goal=(
                "To meticulously fetch and preprocess textual and visual content from web pages and local files. "
                "Identifies potential ingestion issues like paywalls or unsupported formats, "
                "ensuring only relevant and processable data is passed downstream."
            ),
            backstory=(
                "A specialist in navigating the digital and local file landscapes, adept at extracting raw materials. "
                "This agent is the first point of contact for new information, ensuring it's viable before committing further resources."
            ),
            tools=[WebContentFetcherTool(), FileContentExtractorTool()],
            llm=llm, # Pass LLM if agent needs to make decisions or if tools require it implicitly
            verbose=verbose,
            allow_delegation=False # This agent typically doesn't delegate its core fetching tasks
        )
        # Direct instantiation of tools if not passed via constructor or if preferred
        # self.web_fetcher = WebContentFetcherTool()
        # self.file_extractor = FileContentExtractorTool()

    def _extract_filename_from_url(self, url_str: str) -> str:
        """Helper to extract a filename from a URL path."""
        try:
            path = urlparse(url_str).path
            filename = os.path.basename(path)
            return filename if filename else "downloaded_file"
        except Exception:
            return "downloaded_file"

    def _normalize_and_validate_url(self, url_input: Optional[str]) -> Optional[HttpUrl]:
        """Normalizes schemeless URLs, extracts from browser extension wrappers, and validates."""
        if not isinstance(url_input, str) or not url_input.strip():
            return None

        url_to_process = url_input.strip()
        original_for_error_msg = url_to_process # Keep original for better error messages

        extension_prefixes = ["chrome-extension://", "ms-browser-extension://", "moz-extension://", "edge://"]
        was_extension_url = False
        for prefix in extension_prefixes:
            if url_to_process.lower().startswith(prefix.lower()):
                was_extension_url = True
                # Remove the prefix part. The actual URL might be URL-encoded after a path.
                # Example: chrome-extension://<id>/html/viewer.html?file=http%3A%2F%2Fexample.com%2Ffile.pdf
                # A common pattern is that the real URL is the last http/https part.
                
                # Try to find the last occurrence of http:// or https://
                last_http_start = url_to_process.rfind("http://")
                last_https_start = url_to_process.rfind("https://")

                actual_url_start_index = -1
                if last_http_start != -1 and last_https_start != -1:
                    actual_url_start_index = max(last_http_start, last_https_start) # Prefer https if both somehow exist and https is later
                elif last_http_start != -1:
                    actual_url_start_index = last_http_start
                elif last_https_start != -1:
                    actual_url_start_index = last_https_start
                
                if actual_url_start_index != -1 and actual_url_start_index > len(prefix):
                    # Ensure the found http(s) is after the prefix itself
                    extracted_url_candidate = url_to_process[actual_url_start_index:]
                    # Basic check to see if it looks like a URL (has a scheme and some path part)
                    if "//" in extracted_url_candidate and "." in extracted_url_candidate:
                        url_to_process = extracted_url_candidate
                        # print(f"DEBUG: Extracted URL from extension wrapper: {url_to_process}")
                        break 
                # If the above didn't find a clear http/s, the URL might be URL-encoded in a query param
                # This is a simplified check for ?file= or &file=
                match = re.search(r"[?&]file=([^&]+)", url_to_process, re.IGNORECASE)
                if match:
                    from urllib.parse import unquote
                    potential_url = unquote(match.group(1))
                    if potential_url.lower().startswith("http://") or potential_url.lower().startswith("https://"):
                        url_to_process = potential_url
                        # print(f"DEBUG: Extracted URL from ?file= param: {url_to_process}")
                        break
        
        if not (url_to_process.lower().startswith("http://") or url_to_process.lower().startswith("https://")):
            if "://" in url_to_process: 
                # If it was an extension URL and we failed to extract a valid http/s part, error out
                if was_extension_url:
                    raise ValueError(f"Could not extract a valid http/https URL from extension URL: {original_for_error_msg}")
                raise ValueError(f"Unsupported URL scheme in: {original_for_error_msg}. Only http/https are supported.")
            url_to_process = "https://" + url_to_process
        
        return HttpUrl(url_to_process)

    def acquire_content(self, source_type: str, source_data: Dict[str, Any]) -> AcquiredContent:
        """
        Main task method for the agent to acquire content.
        
        Args:
            source_type (str): "url" or "file".
            source_data (Dict[str, Any]): 
                For "url": {"url": "http://example.com"}
                For "file": {"file_bytes": b"...", "filename": "doc.pdf", "mime_type": "application/pdf"}
        
        Returns:
            AcquiredContent: The standardized output.
        """
        
        # Initialize tools - CrewAI might handle tool execution differently, 
        # this shows direct call for clarity of logic flow. 
        # If using CrewAI tasks, the task would invoke the tool.
        web_fetcher = WebContentFetcherTool() # Or self.tools[0] if ordered predictably
        file_extractor = FileContentExtractorTool() # Or self.tools[1]

        if source_type == "url":
            url_input_raw = source_data.get("url")
            
            try:
                validated_url_pydantic = self._normalize_and_validate_url(url_input_raw)
                if not validated_url_pydantic:
                    return AcquiredContent(status="agent_error", input_type="url", source_identifier=str(url_input_raw or "unknown_url"), error_message="Missing or empty URL in source_data.")
                url_to_fetch = str(validated_url_pydantic)
            except ValueError as ve:
                 return AcquiredContent(status="agent_error", input_type="url", source_identifier=str(url_input_raw or "unknown_url"), error_message=str(ve)) # Pass specific error from validation

            # Call the WebContentFetcherTool with the potentially normalized URL
            web_tool_output: WebContent = web_fetcher.run(url=url_to_fetch)

            # Special PDF Handling (TS-AI-4.3, Step 2.a)
            if web_tool_output.status == "pdf_content_downloaded" and web_tool_output.pdf_bytes:
                pdf_filename = self._extract_filename_from_url(str(web_tool_output.original_url))
                if not pdf_filename.lower().endswith('.pdf'): pdf_filename += ".pdf" # Ensure extension
                
                file_tool_output: FileContent = file_extractor.run(
                    file_content=web_tool_output.pdf_bytes,
                    filename=pdf_filename,
                    mime_type="application/pdf"
                )
                # Transform FileContent (from PDF) to AcquiredContent
                return self._transform_file_content_to_acquired_content(
                    file_tool_output, 
                    input_type="url", # Still originated from a URL
                    original_source_id=str(web_tool_output.original_url),
                    final_url=web_tool_output.final_url
                )
            else:
                # Transform WebContent (HTML path) to AcquiredContent
                return self._transform_web_content_to_acquired_content(web_tool_output)
        
        elif source_type == "file":
            file_bytes = source_data.get("file_bytes")
            filename = source_data.get("filename")
            mime_type = source_data.get("mime_type")

            if not all([file_bytes, filename, mime_type]):
                return AcquiredContent(status="agent_error", input_type="file", source_identifier=str(filename or "unknown_file"), error_message="Missing file_bytes, filename, or mime_type in source_data.")

            file_tool_output: FileContent = file_extractor.run(
                file_content=file_bytes,
                filename=filename,
                mime_type=mime_type
            )
            # Transform FileContent to AcquiredContent
            return self._transform_file_content_to_acquired_content(file_tool_output, input_type="file", original_source_id=filename)
        
        else:
            return AcquiredContent(status="agent_error", input_type=source_type, source_identifier="unknown", error_message=f"Unsupported source_type: {source_type}")

    def _transform_web_content_to_acquired_content(self, web_content: WebContent) -> AcquiredContent:
        """Transforms WebContent (from WebContentFetcherTool) to AcquiredContent."""
        image_refs: Optional[List[ImageRefUrl]] = None
        if web_content.images:
            image_refs = []
            for img in web_content.images:
                image_refs.append(ImageRefUrl(
                    url=img.url, 
                    alt_text=img.alt_text, 
                    caption=img.caption,
                    source_scope=img.source_scope,
                    context_before=img.context_before,
                    context_after=img.context_after
                ))
        
        agent_status = web_content.status
        # Simplified status mapping for now - direct pass-through or fallback
        # V1.2 AcquiredContent status list: "success", "strict_paywall_domain", "suspected_paywall_patterns", 
        # "unsupported_url_type", "unsupported_file_type", "fetch_error", "parse_error", "agent_error", 
        # "pdf_requires_manual_review_for_layout"
        # WebContent status list: "success", "unsupported_url_type", "strict_paywall_domain", "suspected_paywall_patterns", 
        # "error_paywall", "unsupported_content_type", "pdf_content_downloaded", "fetch_error", "parse_error"

        expected_agent_statuses = {
            "success", "strict_paywall_domain", "suspected_paywall_patterns", 
            "unsupported_url_type", "fetch_error", "parse_error", "unsupported_content_type",
            "pdf_requires_manual_review_for_layout" # Placeholder, tool doesn't directly set this
        }

        if web_content.status == "error_paywall":
            agent_status = "suspected_paywall_patterns" # Map tool's specific error to agent's broader category
        elif web_content.status == "pdf_content_downloaded":
            # This state should have been handled by the agent to call FileContentExtractorTool.
            # If it reaches here, it's an agent logic error or unexpected tool output.
            agent_status = "agent_error"
            web_content.error_message = web_content.error_message or "Agent logic error: PDF downloaded but not processed as file."
        elif web_content.status not in expected_agent_statuses:
            # For any other status from the tool not directly in the agent's primary list, 
            # and not handled above, consider it a parse_error or fetch_error from the tool perspective.
            # The agent will then report this status.
            # This assumes tool statuses like "fetch_error", "parse_error" are valid for AcquiredContent.
            pass # Keep web_content.status as is if it's a shared one like fetch_error, parse_error etc.

        return AcquiredContent(
            status=agent_status,
            input_type="url",
            source_identifier=str(web_content.original_url),
            final_url_if_redirected=web_content.final_url,
            page_title=web_content.page_title,
            extracted_text=web_content.extracted_text,
            image_references=image_refs, # Type is List[ImageRefUrl] here
            error_message=web_content.error_message
        )

    def _transform_file_content_to_acquired_content(
        self, 
        file_content_model: FileContent, 
        input_type: str, 
        original_source_id: str, 
        final_url: Optional[HttpUrl] = None
    ) -> AcquiredContent:
        """Transforms FileContent (from FileContentExtractorTool) to AcquiredContent."""
        
        img_refs_union: List[Union[ImageRefUrl, ImageRefData]] = []
        if file_content_model.images: # These are ExtractedFileImage with data_base64_string
            for img_data_from_tool in file_content_model.images:
                img_refs_union.append(ImageRefData(
                    data_base64_string=img_data_from_tool.data_base64_string, # Use the base64 string
                    filename_hint=img_data_from_tool.filename_hint,
                    mime_type_hint=img_data_from_tool.mime_type_hint,
                    alt_text=img_data_from_tool.alt_text,
                    caption=img_data_from_tool.caption,
                    source_scope="file_embedded" # Default for ExtractedFileImage
                ))
        
        if file_content_model.linked_markdown_images: 
            for md_img in file_content_model.linked_markdown_images:
                try:
                    img_refs_union.append(ImageRefUrl(
                        url=HttpUrl(md_img["url"]), 
                        alt_text=md_img.get("alt_text"),
                        source_scope="markdown_link"
                    ))
                except ValueError: pass 
        
        agent_status = file_content_model.status
        expected_file_agent_statuses = {"success", "unsupported_file_type", "parse_error", "pdf_requires_manual_review_for_layout"}
        if file_content_model.status == "password_protected_pdf":
            agent_status = "parse_error"
            file_content_model.error_message = file_content_model.error_message or "File is password protected."
        elif file_content_model.status not in expected_file_agent_statuses:
            agent_status = "parse_error"

        return AcquiredContent(
            status=agent_status,
            input_type=input_type,
            source_identifier=original_source_id,
            final_url_if_redirected=final_url if input_type == "url" else None,
            page_title=file_content_model.page_title,
            extracted_text=file_content_model.extracted_text,
            image_references=img_refs_union if img_refs_union else None,
            error_message=file_content_model.error_message
        )

# To use this agent in a CrewAI setup:
# from crewai import Crew, Process
# content_agent = ContentAcquisitionAgent(llm=your_llm_instance, verbose=True)
# task_acquire = Task(
#     description="Acquire content from a given URL or File.",
#     agent=content_agent,
#     # inputs would be dynamically set when the task is run, e.g., from crew inputs
#     # This agent's acquire_content method is the primary entry point for its capability.
#     # How it's called by a Task would depend on how Task expects to invoke agent methods.
#     # Often, the agent's main logic is in a method the Task is configured to call, 
#     # or the agent has a more generic entry point that dispatches based on task description.
#     # For this agent, acquire_content is the designed entry point.
# )
# Example of how a task might be structured if agent has specific method:
# class AcquireContentTask(Task):
#     def run(self, source_type: str, source_data: Dict[str, Any], **kwargs):
#         return self.agent.acquire_content(source_type=source_type, source_data=source_data) 