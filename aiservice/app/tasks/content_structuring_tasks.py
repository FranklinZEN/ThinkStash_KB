# Placeholder for tasks related to TS-AI-Reconstruct-5: Content Consolidation & Structuring Agent 

from crewai import Task, Agent # Assuming Agent for type hinting

class ContentStructuringTasks:
    """Defines tasks for the ContentConsolidationStructuringAgent.

    These tasks are centered around using a powerful LLM to take all processed
    text and image data and intelligently structure it into a final, ordered
    sequence of content blocks (text, image, math, code). It also includes
    detecting if the content is long and formatting the final output.
    """

    def llm_driven_structuring_task(self, agent: Agent, source_document_text: str, image_details_list: list[dict], source_content_type_hint: str) -> Task:
        """Creates a Task for LLM-driven reconstruction of document content into structured blocks.

        The LLM is provided with the main text (potentially containing image markers,
        LaTeX math, or pre-formatted code), a list of image objects with their metadata
        (including GCS URLs and any LLM-generated descriptions/captions from earlier stages),
        and a hint about the original content type to guide image placement strategy.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            source_document_text: The primary textual content, possibly with markers/LaTeX/code.
            image_details_list: A list of dictionaries, where each dict contains metadata for an image
                                (e.g., original_source_identifier, gcs_url, alt_text, caption,
                                 llm_description, context_before_text, context_after_text).
            source_content_type_hint: A string indicating the origin to help LLM with image placement
                                      (e.g., "pdf_with_markers", "docx_with_placeholders",
                                      "html_with_context", "docx_raw_no_placeholders").

        Returns:
            Task: A CrewAI Task configured for LLM-driven content structuring.
        """
        # The prompt for this task is crucial and detailed in the design document.
        # It instructs the LLM on how to handle markers, context for images without markers,
        # identify math/code, and the exact JSON output format for blocks.
        return Task(
            description=f"Reconstruct the document (text length: {len(source_document_text)} chars, images: {len(image_details_list)}, hint: {source_content_type_hint}) "
                        "into an ordered sequence of 'text', 'image', 'math', and 'code' blocks using advanced LLM reasoning. "
                        "Iterate through the source_document_text. Segment text into logical blocks. "
                        "When an image marker is encountered, use the corresponding image from image_details_list to create an 'image' block (gcs_url, alt, caption). "
                        "If source_content_type_hint is 'html_with_context' and no markers are present, use 'context_before_text' and 'context_after_text' from image_details_list to semantically determine image insertion points. "
                        "If source_content_type_hint is 'docx_raw_no_placeholders', semantically analyze text and image descriptions to infer logical image placements. "
                        "Identify text segments that are LaTeX mathematical formulas and create 'math' blocks. "
                        "Identify text segments that are code snippets and create 'code' blocks, inferring language if possible (else 'plaintext').",
            expected_output="A single JSON string representing a list of ordered content blocks. Each block is an object with a 'type' "
                            "(text, image, math, code) and relevant content fields (e.g., 'content' for text/math/code, 'gcs_url', 'alt_text', 'caption' for image). "
                            "Example: '[ { \"type\": \"text\", \"content\": \"...\" }, { \"type\": \"image\", \"gcs_url\": \"...\" }, ... ]'",
            agent=agent
            # This task will use the agent's configured LLM (e.g., OpenAI GPT-4.1 Turbo or equivalent).
            # The LLM prompt should strictly enforce the JSON output format.
        )

    def long_article_detection_task(self, agent: Agent, content_blocks_json_list_str: str) -> Task:
        """Creates a Task to determine if the structured content qualifies as a long article.

        This can be based on heuristics like the number of content blocks, total text length,
        or other metrics derived from the structured content.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            content_blocks_json_list_str: A JSON string representing the list of structured content blocks
                                     (output from llm_driven_structuring_task).

        Returns:
            Task: A CrewAI Task configured for long article detection.
        """
        return Task(
            description=f"Analyze the generated list of structured content blocks (JSON string provided) to determine if the article is considered long. "
                        f"Consider factors like total number of blocks, cumulative text length, or presence of many complex elements.",
            expected_output="A dictionary containing a boolean value for 'is_long_article' (True if long, False otherwise), "
                            "and optionally other metrics like 'total_word_count' or 'block_count'.",
            agent=agent # This task might be rule-based and not require an LLM, or use a simple LLM call for assessment.
        )

    def format_final_output_task(self, agent: Agent, structured_blocks_json_str: str, is_long_article_details: dict) -> Task:
        """Creates a Task to format the final output package from content structuring.

        Args:
            agent: The CrewAI agent assigned to execute this task.
            structured_blocks_json_str: The JSON string of structured content blocks.
            is_long_article_details: A dictionary containing the 'is_long_article' boolean flag and any other metrics from the detection task.

        Returns:
            Task: A CrewAI Task configured for formatting the final output.
        """
        return Task(
            description="Format the final output package. This involves taking the JSON string of structured_content_blocks, "
                        "parsing it into a list of block objects, and combining it with the 'is_long_article' flag and other relevant details.",
            expected_output="A dictionary representing the core content part of the main service response, typically including: "
                            "'original_content_blocks' (a Python list of content block dictionaries) and "
                            "'is_long_article' (boolean).",
            agent=agent
        ) 