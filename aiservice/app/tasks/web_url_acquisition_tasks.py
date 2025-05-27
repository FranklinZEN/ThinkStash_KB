# Placeholder for tasks related to TS-AI-Reconstruct-3: Web URL Content Acquisition Agent 

from crewai import Task, Agent # Assuming Agent for type hinting
from pydantic import HttpUrl # For type hinting if needed in expected output examples
from typing import Optional, Dict, Any, List # Added List
import uuid # For generating unique IDs

class WebURLAcquisitionTasks:
    """Defines tasks for the WebURLContentAcquisitionAgent, focusing on using the OptimizedHtmlExtractionTool."""

    def comprehensive_url_processing_task(self, agent: Agent, url_to_process: str) -> Task:
        """Creates a Task for comprehensive processing of a web URL using the WebContentFetcherTool.
        The tool handles initial fetching, paywall detection, URL filtering, and basic content extraction.
        This task orchestrates the use of the tool and subsequent data storage if successful.
        """
        description = f"""Process the web URL: {url_to_process} using the 'Web Content Fetcher Tool'. 
        The tool will return a dictionary with fields like 'status', 'original_url', 'final_url', 'page_title', 'extracted_text', 'images', 'pdf_bytes', 'error_message', and 'processing_duration_seconds'.

        Your primary actions are:
        1. Execute the 'Web Content Fetcher Tool' with the provided URL ('{url_to_process}'). Let the output of this tool be referred to as 'tool_output'.
        2. Analyze the 'status' field from 'tool_output':
           a. If 'status' is 'success':
              - Let 'actual_text' be the value of 'tool_output.extracted_text'.
              - Let 'actual_images' be the value of 'tool_output.images'.
              - Initialize 'text_ref_id' to null. If 'actual_text' is present and not empty, YOU MUST generate a new unique UUID string (e.g., using a mental model of uuid.uuid4().hex + '_text_ref'). Then, use the 'Data Store Access Tool' with parameters: action='put', key=YOUR_GENERATED_UUID_STRING, value=actual_text. Set 'text_ref_id' to be YOUR_GENERATED_UUID_STRING.
              - Initialize 'images_ref_id' to null. If 'actual_images' list is present and not empty, YOU MUST generate another new unique UUID string (e.g., uuid.uuid4().hex + '_images_ref'). Then, use the 'Data Store Access Tool' with parameters: action='put', key=YOUR_SECOND_GENERATED_UUID_STRING, value=actual_images. Set 'images_ref_id' to be YOUR_SECOND_GENERATED_UUID_STRING.
              - Construct a summary string for 'summary_of_extraction' (e.g., 'Text and images stored', 'Only text stored', 'No new content stored').
              - Your final answer for this task MUST BE a JSON string dictionary containing: 'status' ('success'), 'original_url' (from tool_output), 'final_url' (from tool_output), 'page_title' (from tool_output), 'processing_duration_seconds' (from tool_output), 'summary_of_extraction', 'extracted_text_ref' (which is your 'text_ref_id'), and 'images_ref' (which is your 'images_ref_id').
           b. If 'status' is 'pdf_content_downloaded':
              - Your final answer for this task MUST BE a JSON string dictionary containing: 'status' ('pdf_content_downloaded'), 'original_url' (from tool_output), 'final_url' (from tool_output), 'page_title' (from tool_output), 'pdf_content_info' (e.g., 'PDF content was fetched. Reference key for pdf_bytes could be generated and stored if a system for that exists, but for now, note its presence.'), and 'processing_duration_seconds' (from tool_output).
           c. If 'status' indicates an error (e.g., 'unsupported_url_type', 'strict_paywall_domain', 'error_paywall', etc.):
              - Your final answer for this task MUST BE a JSON string dictionary containing: 'status' (the error status from tool_output), 'original_url' (from tool_output), 'final_url' (from tool_output, if any), 'page_title' (from tool_output, if any), 'error_message' (from tool_output), and 'processing_duration_seconds' (from tool_output).
        Ensure your JSON output is concise and directly reflects the outcome based on the tool's 'status'."""
        
        expected_output = """A JSON string dictionary. Examples:
If successful: {\"status\": \"success\", \"original_url\": \"...\", \"final_url\": \"...\", \"page_title\": \"...\", \"processing_duration_seconds\": 0.5, \"summary_of_extraction\": \"Text and images stored\", \"extracted_text_ref\": \"some_uuid_text_ref\", \"images_ref\": \"another_uuid_images_ref\"}
If PDF: {\"status\": \"pdf_content_downloaded\", \"original_url\": \"...\", \"final_url\": \"...\", \"page_title\": \"doc.pdf\", \"pdf_content_info\": \"PDF content was fetched...\", \"processing_duration_seconds\": 0.2}
If error (e.g. paywall): {\"status\": \"error_paywall\", \"original_url\": \"...\", \"final_url\": \"...\", \"page_title\": \"Paywall Page\", \"error_message\": \"Paywall detected\", \"processing_duration_seconds\": 0.1}
"""
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent
        )

    def url_validation_task(self, agent: Agent, url: str) -> Task:
        """Creates a Task for validating a given URL.

        This includes basic syntax checks, pre-flight checks like domain filtering
        (if applicable), and normalization.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            url: The URL string to be validated.

        Returns:
            Task: A CrewAI Task configured for URL validation.
        """
        return Task(
            description=f"Validate the provided URL: {url}. Perform pre-flight checks (e.g., filter unsupported domains if a list is provided), "
                        "and normalize the URL (e.g., ensure scheme is present).",
            expected_output="A dictionary with validation status (True/False), the normalized URL string, and an error message if validation fails.",
            agent=agent
        )

    def http_fetching_task(self, agent: Agent, normalized_url: str) -> Task:
        """Creates a Task for fetching HTML content from a URL.

        Handles HTTP complexities like redirects, user-agents, and timeouts.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            normalized_url: The validated and normalized URL to fetch content from.

        Returns:
            Task: A CrewAI Task configured for HTTP content fetching.
        """
        return Task(
            description=f"Use the HTTP Content Fetcher tool to fetch the HTML content from the URL: {normalized_url}. "
                        "After the tool runs, it will provide a dictionary. From this dictionary, extract the value associated with the 'summary' key. "
                        "Your final answer for this task MUST BE only this summary string.",
            expected_output="A short summary string indicating the result of the fetch (e.g., 'Successfully fetched HTML from {URL}. Length: {length} chars.') or an error summary from the tool.",
            agent=agent
            # tools=[HTTPFetchingTool_instance]
        )

    def paywall_detection_task(self, agent: Agent, url: str, raw_html_content: Optional[str] = None, extracted_text_length: int = -1) -> Task:
        """Creates a Task for detecting potential paywalls on a web page.

        Uses a multi-tiered strategy including domain checks, HTML scanning, and potentially
        post-extraction analysis hints if main content is minimal.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            url: The URL of the page being analyzed.
            raw_html_content: Optional raw HTML content of the page if already fetched.
            extracted_text_length: Optional length of main text extracted by another tool. -1 if not available.

        Returns:
            Task: A CrewAI Task configured for paywall detection.
        """
        description_str = (
            f"Analyze the content from URL ({url}) for signs of a paywall. "
            f"HTML content provided: {bool(raw_html_content)}. "
            f"Length of pre-extracted text available: {extracted_text_length if extracted_text_length != -1 else 'N/A'}. "
            "This may involve checking against a known list of paywalled domains, "
            "scanning the HTML for common paywall markers (e.g., subscription prompts, blurred content indicators), "
            "or inferring based on very short extracted content later."
        )
        return Task(
            description=description_str,
            expected_output="A dictionary indicating paywall status (e.g., 'detected', 'not_detected', 'uncertain') and any supporting details or confidence level.",
            agent=agent
        )

    def main_content_extraction_task(self, agent: Agent, raw_html_content: str, url: str) -> Task:
        """Creates a Task for extracting the main article content from HTML.

        Uses libraries like Trafilatura to filter out boilerplate, ads, and navigation elements.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            raw_html_content: The raw HTML string of the web page.
            url: The URL of the page (for context, e.g., if Trafilatura uses it).

        Returns:
            Task: A CrewAI Task configured for main content extraction.
        """
        return Task(
            description=f"Extract the main article/textual content from the provided raw HTML of {url}. "
                        "Utilize a robust extraction library like Trafilatura to effectively filter out boilerplate, ads, navigation menus, and comments.",
            expected_output="A string containing the cleaned main textual content of the web page. Should be an empty string if no meaningful content is found.",
            agent=agent
            # tools=[TrafilaturaTool_instance]
        )

    def image_extraction_contextualization_task(self, agent: Agent, raw_html_content: str, base_url: str) -> Task:
        """Creates a Task for extracting and contextualizing images from HTML.

        Uses libraries like BeautifulSoup to parse HTML for image tags and related metadata.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            raw_html_content: The raw HTML string of the web page.
            base_url: The base URL of the page, used for resolving relative image URLs.

        Returns:
            Task: A CrewAI Task configured for image extraction and contextualization.
        """
        return Task(
            description=f"Extract images from the raw HTML of {base_url}. Utilize BeautifulSoup for detailed parsing and refinement. "
                        "For each image, attempt to source its URL (absolute), extract metadata like 'alt' text, and identify potential captions "
                        "from nearby text elements. Also, try to capture short text snippets immediately before and after the image for contextual understanding.",
            expected_output="A list of dictionaries, where each dictionary represents an image and contains: 'image_url' (absolute), 'alt_text', "
                            "'extracted_caption' (if found), 'context_before_text', and 'context_after_text'. Returns an empty list if no suitable images are found.",
            agent=agent
            # tools=[BeautifulSoupImageExtractorTool_instance]
        )

    def title_extraction_task(self, agent: Agent, raw_html_content: str) -> Task:
        """Creates a Task for extracting the title of a web page.

        Prioritizes common HTML elements used for titles (<title>, OpenGraph, <h1>).

        Args:
            agent: The CrewAI agent assigned to execute this task.
            raw_html_content: The raw HTML string of the web page.

        Returns:
            Task: A CrewAI Task configured for title extraction.
        """
        return Task(
            description="Extract the primary title of the web page from its HTML content. "
                        "Prioritize the content of the <title> tag. As fallbacks, check OpenGraph meta properties (e.g., 'og:title') "
                        "and the content of the main <h1> heading.",
            expected_output="A string containing the extracted page title. Returns an empty string or a sensible default if no title can be reliably extracted.",
            agent=agent
        )

    def package_web_output_task(self, agent: Agent, extracted_text: str, extracted_images: list, extracted_title: str, paywall_status: dict, source_url: str) -> Task:
        """Creates a Task for packaging all outputs from web URL processing.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            extracted_text: The main text content extracted from the URL.
            extracted_images: A list of image metadata dictionaries.
            extracted_title: The extracted page title.
            paywall_status: A dictionary indicating the paywall detection outcome.
            source_url: The original URL that was processed.

        Returns:
            Task: A CrewAI Task configured for packaging the web processing output.
        """
        return Task(
            description=f"Package all outputs from the web URL ({source_url}) processing into a standardized, structured format.",
            expected_output="A dictionary containing keys such as: 'main_text_content' (string), 'extracted_image_list' (list of image data objects), "
                            "'page_title' (string), 'paywall_info' (dictionary with status and details), and 'original_url' (string).",
            agent=agent
        ) 