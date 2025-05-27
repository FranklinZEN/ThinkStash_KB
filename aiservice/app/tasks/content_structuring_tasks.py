# Placeholder for tasks related to TS-AI-Reconstruct-5: Content Consolidation & Structuring Agent 

from crewai import Task, Agent # Assuming Agent for type hinting
from typing import List, Dict, Any, Optional

class ContentStructuringTasks:
    """Defines tasks for the ContentConsolidationStructuringAgent.

    These tasks are centered around using a powerful LLM to take all processed
    text and image data and intelligently structure it into a final, ordered
    sequence of content blocks (text, image, math, code). It also includes
    detecting if the content is long and formatting the final output.
    """

    def llm_driven_structuring_task(
        self, 
        agent: Agent, 
        source_document_text_ref: Optional[str],
        image_details_list_ref: Optional[str],
        source_content_type_hint: str,
        page_title: Optional[str] = None
    ) -> Task:
        """Creates a Task for LLM-driven reconstruction using data references."""
        
        description = (
            f"Precisely structure the content retrieved from the data store into a coherent, logically ordered document using the AdvancedLLMStructuringTool. "
            f"Explicitly prioritize key introductory information, main topic details, and critical insights, arranging them sequentially for optimal readability and comprehension. "
            f"Clearly distinguish between primary content and secondary details, and exclude redundant, promotional, or irrelevant material unless explicitly relevant. "
            f"Leverage provided hints (source_content_type_hint: '{source_content_type_hint}', page_title: '{page_title}') meticulously to guide accurate structuring. "
            f"Deliver structured output promptly with high accuracy and minimal iterations.\n"
            f"The main text content is in the shared data_store. Use the 'Data Store Access Tool' with action 'get' and the key '{source_document_text_ref}' to retrieve it. If '{source_document_text_ref}' is null, empty, or the key is not found, consider the text content as None or empty.\n"
            f"The list of image details is in the shared data_store. Use the 'Data Store Access Tool' with action 'get' and the key '{image_details_list_ref}' to retrieve it. If '{image_details_list_ref}' is null, empty, or the key is not found, consider the image details list as empty.\n"
            "After retrieving the data (or defaults if retrieval fails), use the 'AdvancedLLMStructuringTool'. "
            "Pass the retrieved text content as 'source_document_text' (can be None or empty string). "
            "Pass the retrieved list of image details as 'image_details_list' (can be an empty list). "
            f"Also, pass the original 'source_content_type_hint' (which is '{source_content_type_hint}') and 'page_title' (which is '{page_title}') to the AdvancedLLMStructuringTool. "
            "The direct output from this single call to AdvancedLLMStructuringTool will be your final answer for this task. Do not attempt to call it multiple times."
        )
        expected_output=(
            "A single JSON string representing a list of ordered content blocks (text, image, math, code) "
            "as produced by the AdvancedLLMStructuringTool."
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent
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