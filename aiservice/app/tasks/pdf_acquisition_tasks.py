# Placeholder for tasks related to TS-AI-Reconstruct-1: PDF Content Acquisition & Marking Agent 

from crewai import Task, Agent # Assuming Agent might be needed for type hinting if tasks are tied to specific agent instances

class PDFAcquisitionTasks:
    """Defines tasks specific to the PDFContentAcquisitionAgent.

    These tasks cover the workflow for processing PDF files, including tiered parsing,
    converting pages to images for multimodal analysis, invoking LLMs for image marking,
    integrating these markers, and packaging the final output from PDF processing.
    """

    def tiered_pdf_parsing_task(self, agent: Agent, pdf_file_path: str) -> Task:
        """Creates a Task for performing tiered PDF parsing.

        The agent will attempt parsing with increasingly sophisticated tools (e.g., PyMuPDF, then Nougat)
        to balance speed and extraction quality, especially for complex layouts, math, and code.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            pdf_file_path: The file path to the PDF document to be parsed.

        Returns:
            Task: A CrewAI Task configured for tiered PDF parsing.
        """
        return Task(
            description=f"Perform tiered PDF parsing on the file: {pdf_file_path}. "
                        "Start with PyMuPDF for quick text extraction. If the PDF is complex (e.g., academic paper), "
                        "consider using Nougat for deep semantic/structural parsing, aiming to convert math to LaTeX and extract code accurately. "
                        "Handle errors and fallbacks gracefully at each tier of parsing.",
            expected_output="A dictionary containing: 'parsed_text_content' (string, potentially with LaTeX/code), "
                            "'extracted_math_content' (list of LaTeX strings if available), "
                            "'extracted_code_blocks' (list of code strings/objects if available), "
                            "'parsing_tier_used' (string indicating the successful parser), and 'status_message'.",
            agent=agent,
            # tools=[PyMuPDFParserTool_instance, NougatPDFParserTool_instance] # Tools would be passed to the agent executing this
        )

    def page_to_image_conversion_task(self, agent: Agent, pdf_file_path: str, output_folder:str, page_numbers: list[int] = None, dpi: int = 200, fmt: str = 'png') -> Task:
        """Creates a Task for converting specific PDF pages to images.

        This is typically done for pages identified as containing relevant visual content
        that needs to be analyzed by a multimodal LLM.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            pdf_file_path: The file path to the PDF document.
            output_folder: The folder path where output images should be saved.
            page_numbers: An optional list of 1-indexed page numbers to convert. If None, handles all pages.
            dpi: DPI for image conversion.
            fmt: Image format (e.g., 'png', 'jpeg').

        Returns:
            Task: A CrewAI Task configured for PDF page-to-image conversion.
        """
        page_spec = f"pages {page_numbers}" if page_numbers else "all pages"
        description = (
            f"Convert {page_spec} of the PDF file '{pdf_file_path}' to images. "
            f"Save output images to the folder: '{output_folder}'. "
            f"Use DPI: {dpi} and format: '{fmt}'."
        )
        return Task(
            description=description,
            expected_output=f"A list of dictionaries, each with 'page_number' and 'image_path' for converted images saved in '{output_folder}', or an error status.",
            agent=agent
            # tools=[PDFToImageTool_instance]
        )

    def multimodal_llm_image_marking_task(self, agent: Agent, page_image_path: str, page_number: int, page_text_content: str = None) -> Task:
        """Creates a Task for analyzing a PDF page image with a multimodal LLM to mark and describe images.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            page_image_path: Path to the image of the PDF page.
            page_number: The original page number from the PDF for this image.
            page_text_content: Optional text extracted from this page to provide context to the LLM.

        Returns:
            Task: A CrewAI Task configured for LLM-based image marking.
        """
        description_for_task = (
            f"Analyze the provided PDF page image ({page_image_path}, page number {page_number}) using a multimodal LLM (e.g., GPT-4 Vision). "
            "Identify distinct images/figures. For each, generate a unique marker in the format '[IMAGE_MARKER_PAGE<P>_INDEX<I>]', "
            f"where you should replace '<P>' with the actual page number ({page_number}) and '<I>' with a sequential 1-based index for images you identify on this page. "
            "Also provide a visual description, extract any visible caption, identify surrounding text context, and determine its ordinal position on the page. "
            f"Optional page text for context has been provided: {bool(page_text_content)}."
        )
        
        expected_output_for_task = (
            "A JSON string representing a list of objects, one for each identified image, containing: 'marker_id' (using the <P> and <I> replaced format), 'llm_description', "
            "'llm_extracted_caption', 'llm_context_before_text', 'llm_context_after_text', 'ordinal_position_on_page', and importantly 'local_path' (the file path of the analyzed page image). "
            "Returns an empty list as JSON string if no images are found."
        )
        return Task(
            description=description_for_task,
            expected_output=expected_output_for_task,
            agent=agent
            # This task heavily relies on the agent's configured multimodal LLM, likely via MultimodalLLMImageMarkerTool.
        )

    def integrate_image_markers_task(self, agent: Agent, parsed_text_content: str, image_marker_json_list_str: str) -> Task:
        """Creates a Task for integrating LLM-generated image markers into the extracted text.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            parsed_text_content: The main text extracted from the PDF (potentially by Nougat or other parsers).
            image_marker_json_list_str: A JSON string (from multimodal_llm_image_marking_task) containing the list of image metadata and markers.

        Returns:
            Task: A CrewAI Task configured for marker integration.
        """
        return Task(
            description="Integrate the LLM-generated image markers (from the provided JSON list string) into the parsed PDF text content. "
                        "Ensure markers are placed accurately, either at specific locations if parsers support it, or by replacing placeholders. "
                        "The goal is to have a single text stream where image locations are clearly denoted.",
            expected_output="The 'parsed_text_content' string now including the integrated image markers at appropriate positions.",
            agent=agent
        )

    def package_pdf_output_task(self, agent: Agent, text_with_markers: str, raw_image_list_with_markers: list, extracted_math_content: list, extracted_code_blocks: list, parsing_tier_used: str) -> Task:
        """Creates a Task for packaging all outputs from the PDF processing workflow.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            text_with_markers: The final text content including image markers and potentially LaTeX/code.
            raw_image_list_with_markers: List of raw image data (e.g., paths to converted page images or extracted raw images) associated with their markers/metadata from the LLM.
            extracted_math_content: List of LaTeX strings for mathematical content.
            extracted_code_blocks: List of extracted code blocks (strings or objects).
            parsing_tier_used: String indicating the primary parsing tool that yielded the main text.

        Returns:
            Task: A CrewAI Task configured for packaging the PDF processing output.
        """
        return Task(
            description="Package all outputs from the PDF processing into a structured dictionary. This includes "
                        "the consolidated text content with integrated image markers (and any embedded LaTeX/code), "
                        "a list of all identified images (with their GCS URLs after persistence, markers, and LLM-generated metadata), "
                        "any separately identified mathematical content (e.g., list of LaTeX strings), "
                        "any separately identified code blocks, and the parsing tier that was primarily used.",
            expected_output="A dictionary containing: 'final_text_content_with_markers', 'processed_image_data_list' "
                            "(list of objects, each with image GCS URL, marker, LLM descriptions, caption, context, etc.), "
                            "'final_extracted_math_content' (list), 'final_extracted_code_blocks' (list), "
                            "and 'final_parsing_tier_used' (string).",
            agent=agent
        ) 