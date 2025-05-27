# Placeholder for tasks related to TS-AI-Reconstruct-2: Generic File Content Acquisition Agent 

from crewai import Task, Agent # Assuming Agent for type hinting

class GenericFileAcquisitionTasks:
    """Defines tasks for the GenericFileContentAcquisitionAgent.

    These tasks are responsible for processing various common file formats like
    DOCX, TXT, and Markdown. Each task focuses on extracting relevant content
    (text, images, structured data) from the specific file type and packaging it.
    """

    def docx_processing_task(self, agent: Agent, docx_file_path: str) -> Task:
        """Creates a Task for processing a DOCX file.

        This task involves extracting text content and images from the DOCX file.
        Images are typically handled by saving them and using placeholders in the text.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            docx_file_path: The file path to the DOCX document.

        Returns:
            Task: A CrewAI Task configured for DOCX file processing.
        """
        return Task(
            description=f"Process the DOCX file: {docx_file_path}. Extract all text content. "
                        "Identify and extract images, implementing a placeholder strategy for them within the text "
                        "(e.g., '[IMAGE_PLACEHOLDER_DOCX_1]'). Package the extracted text (with image placeholders) "
                        "and a list of raw image data (e.g., image bytes or paths to temporarily saved images, along with their placeholder IDs).",
            expected_output="A dictionary containing: 'extracted_text_content' (string with image placeholders), "
                            "and 'raw_image_list' (list of dictionaries, each with 'id', 'data' or 'path', and potentially 'filename').",
            agent=agent
            # tools=[DocxParserTool_instance] # Tool to be used by the agent for this task
        )

    def txt_processing_task(self, agent: Agent, txt_file_path: str) -> Task:
        """Creates a Task for processing a plain TXT file.

        This task involves reading the raw text content, being mindful of potential character encoding issues.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            txt_file_path: The file path to the TXT document.

        Returns:
            Task: A CrewAI Task configured for TXT file processing.
        """
        return Task(
            description=f"Process the TXT file: {txt_file_path}. Read the raw text content. "
                        "Ensure correct handling of character encodings to prevent data corruption.",
            expected_output="A dictionary containing: 'extracted_text_content' (string).",
            agent=agent
            # tools=[TxtParserTool_instance]
        )

    def markdown_processing_task(self, agent: Agent, md_file_path: str) -> Task:
        """Creates a Task for processing a Markdown (MD) file.

        This task involves parsing the Markdown content to extract not only the text but also
        structured elements like linked images, code blocks (with language detection if possible),
        and mathematical expressions (e.g., LaTeX).

        Args:
            agent: The CrewAI agent assigned to execute this task.
            md_file_path: The file path to the Markdown document.

        Returns:
            Task: A CrewAI Task configured for Markdown file processing.
        """
        return Task(
            description=f"Process the Markdown (MD) file: {md_file_path}. Parse the text content. "
                        "Identify and extract information about linked images (e.g., alt text, URL). "
                        "Identify and extract code blocks, including the programming language if specified. "
                        "Identify and extract mathematical expressions (e.g., LaTeX blocks or inline math).",
            expected_output="A dictionary containing: 'extracted_text_content' (string, which might be the raw Markdown or converted HTML/text), "
                            "'linked_image_list' (list of dictionaries, each with 'alt_text', 'url'), "
                            "'code_block_list' (list of dictionaries, each with 'language', 'content'), "
                            "and 'math_expression_list' (list of strings, e.g., LaTeX content).",
            agent=agent
            # tools=[MarkdownParserTool_instance]
        )

    def package_generic_output_task(self, agent: Agent, file_type: str, extracted_data: dict) -> Task:
        """Creates a Task for packaging the output from any generic file processing task.

        This task standardizes the output format for data extracted from DOCX, TXT, or MD files.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            file_type: The type of file that was processed (e.g., 'docx', 'txt', 'md').
            extracted_data: The dictionary of data extracted by the specific file processing task.

        Returns:
            Task: A CrewAI Task configured for packaging the output.
        """
        return Task(
            description=f"Package the output from the {file_type} processing. Consolidate extracted text, "
                        f"image information (raw or linked), and any special content (like code or math blocks from Markdown) "
                        f"into a standardized structure. Input data: {extracted_data.keys() if isinstance(extracted_data, dict) else 'data'}.",
            expected_output="A structured dictionary, typically containing keys like: 'extracted_text_content', "
                            "'raw_or_linked_image_list' (list of image metadata), "
                            "and 'extracted_special_content' (dictionary for MD code/math, or None).",
            agent=agent
        ) 