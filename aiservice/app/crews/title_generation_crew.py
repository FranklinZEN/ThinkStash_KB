#!/usr/bin/env python
# coding: utf-8
"""
Defines the GeneralPurposeTitleGenerationCrew, responsible for orchestrating
agents to generate a title for a given list of content blocks.
Aligns with V2.6 Development Plan - Iteration 1.2.
"""

from crewai import Agent, Task, Crew, Process
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json

from crewai.tasks.task_output import TaskOutput
from aiservice.app.config.logging_config import get_logger
from aiservice.app.agents.title_generation_agents import TitleGenerationAgents
from aiservice.app.models.orchestration_models import ContentBlock
from crewai.crews.crew_output import CrewOutput # Import CrewOutput
from aiservice.app.models.insight_generation_models import TitleGenerationRequest
from aiservice.app.models.task_output_models import TitleGenerationOutput
from aiservice.app.tools.content_processing_tools import FullTextContentExtractorTool # Corrected import
from aiservice.app.config.settings import Settings # Corrected class name & import
from crewai.tools import BaseTool # Corrected import

logger = get_logger(__name__)

class GeneralPurposeTitleGenerationCrew:
    """Creates and runs a CrewAI crew for generating titles from content blocks."""

    def __init__(self, request_model: Optional[TitleGenerationRequest] = None):
        """
        Initializes the crew.
        Args:
            request_model: Optional TitleGenerationRequest object, not used in the current implementation.
        """
        print("Initializing GeneralPurposeTitleGenerationCrew...")
        self.request_model = request_model
        # Initialize agents and tools here if they are to be reused across runs
        # or if their initialization is expensive.
        self.title_agents = TitleGenerationAgents()
        self.full_text_extractor_tool = FullTextContentExtractorTool() # Instantiate for direct use
        self.settings = Settings() # Corrected class name
        self.llm = self.settings.get_crew_llm()

        # Agent
        self.title_crafting_agent = self.title_agents.title_crafting_agent()
        print(f"Title Crafting Agent Tools: {[tool.name for tool in self.title_crafting_agent.tools]}")

    def _create_title_generation_task(self, extracted_text: str) -> Task:
        """Creates the task for the title generation agent, providing the pre-extracted text."""
        return Task(
            description=(
                f"Your primary objective is to generate a title for the following text content. "
                f"The text has already been extracted for you.\n\n"
                f"TEXT CONTENT TO ANALYZE:\n"
                f"------------------------\n"
                f"{extracted_text}\n"
                f"------------------------\n\n"
                f"Step 1: Carefully review the TEXT CONTENT TO ANALYZE provided above.\n"
                f"Step 2: IF the TEXT CONTENT TO ANALYZE appears to be empty, nonsensical, or an error message, "
                f"THEN your final output for the 'generated_title' field MUST be the exact string: "
                f"'Error: No valid content provided for title generation.'. DO NOT attempt to generate a title.\n"
                f"Step 3: IF the TEXT CONTENT TO ANALYZE is valid, use the 'OptimizedLLMInteractionTool' "
                f"to generate a concise, informative, and engaging title (ideally under 15 words) "
                f"that accurately reflects the main topic of the text. "
                f"You MUST use a temperature setting of 0.0 for the LLM call via the tool to ensure deterministic and factual titles.\n"
                f"Step 4: The output of the 'OptimizedLLMInteractionTool' will be the title. "
                f"Ensure your final answer for the 'generated_title' field is ONLY this title string, or the error string from Step 2."
            ),
            expected_output=(
                "A single string containing the generated title (e.g., 'The Future of AI in Healthcare') OR "
                "the specific error message 'Error: No valid content provided for title generation.' if title generation is not possible."
            ),
            agent=self.title_crafting_agent,
            output_pydantic=TitleGenerationOutput
        )

    def run(self, content_block_dicts: List[Dict[str, Any]]) -> TitleGenerationOutput:
        """
        Runs the title generation crew.
        This method now expects the crew to return a TitleGenerationOutput Pydantic object.
        """
        print(f"GeneralPurposeTitleGenerationCrew running with {len(content_block_dicts)} content block(s).")

        try:
            # Step 1: Extract full text.
            extracted_text = self.full_text_extractor_tool._run(content_block_dicts=content_block_dicts)
        except Exception as e:
            logger.error(f"Error during text extraction: {e}", exc_info=True)
            return TitleGenerationOutput(suggested_title="Error: Failed to extract text content.")

        # Step 2: Create and run the crew.
        title_task = self._create_title_generation_task(extracted_text=extracted_text)
        title_crew = Crew(
            agents=[self.title_crafting_agent],
            tasks=[title_task],
            process=Process.sequential,
            verbose=True,
        )

        try:
            print("Kicking off Title Generation Crew...")
            crew_result = title_crew.kickoff()
            print(f"Title Generation Crew execution finished. Result: {crew_result}")

            if isinstance(crew_result, TitleGenerationOutput):
                return crew_result
            else:
                # This is a fallback if the crew output is not the expected Pydantic model.
                logger.warning(f"Unexpected output type from crew: {type(crew_result)}")
                raw_str_output = str(crew_result.raw) if hasattr(crew_result, 'raw') else str(crew_result)
                return TitleGenerationOutput(suggested_title=f"Error: Unexpected output format from crew: {raw_str_output}")

        except Exception as e:
            logger.error(f"An exception occurred during crew execution: {e}", exc_info=True)
            return TitleGenerationOutput(suggested_title=f"Error: An exception occurred during title generation: {e}")

# Example Usage (for testing purposes, if you run this file directly):
if __name__ == '__main__':
    # This is a very basic example. In a real scenario, content_block_dicts
    # would come from a proper source (e.g., an API request, a file, etc.)
    sample_content_blocks = [
        {'block_id': '1', 'user_id': 'test_user', 'document_id': 'doc1', 'type': 'heading', 'content': 'The Wonders of AI', 'order_index': 0, 'version': 1, 'page_number':1, 'coordinates': None, 'created_at': '2024-01-01T00:00:00', 'updated_at': '2024-01-01T00:00:00'},
        {'block_id': '2', 'user_id': 'test_user', 'document_id': 'doc1', 'type': 'text', 'content': 'Artificial intelligence is rapidly changing the world. It has applications in various fields.', 'order_index': 1, 'version': 1, 'page_number':1, 'coordinates': None, 'created_at': '2024-01-01T00:00:00', 'updated_at': '2024-01-01T00:00:00'},
        {'block_id': '3', 'user_id': 'test_user', 'document_id': 'doc1', 'type': 'text', 'content': 'From healthcare to finance, AI is making significant impacts.', 'order_index': 2, 'version': 1, 'page_number':1, 'coordinates': None, 'created_at': '2024-01-01T00:00:00', 'updated_at': '2024-01-01T00:00:00'},
        {'block_id': '4', 'user_id': 'test_user', 'document_id': 'doc1', 'type': 'image', 'content': {'url': 'http://example.com/image.png', 'alt_text':'AI concept image', 'caption': 'AI visualization'}, 'order_index': 3, 'version': 1, 'page_number':1, 'coordinates': None, 'created_at': '2024-01-01T00:00:00', 'updated_at': '2024-01-01T00:00:00'}
    ]

    # Simulate a request model if your crew expects one for other purposes,
    # otherwise, it might not be strictly necessary if run() directly takes content_blocks.
    # For this refactoring, request_model is optional in __init__ and not directly used by run()
    # request = TitleGenerationRequest(content_blocks=sample_content_blocks) 
    
    crew_runner = GeneralPurposeTitleGenerationCrew()
    
    # The run method now directly takes the list of content block dictionaries
    result_output = crew_runner.run(content_block_dicts=sample_content_blocks)
    print(f"\nSuggested Title from Crew: {result_output.suggested_title}")

    # Test with empty content
    empty_content_blocks = []
    result_empty = crew_runner.run(content_block_dicts=empty_content_blocks)
    print(f"\nSuggested Title from Crew (empty input): {result_empty.suggested_title}")

    # Test with content that should result in an error from the agent's perspective
    error_sim_content = [
         {'block_id': '1', 'user_id': 'test_user', 'document_id': 'doc1', 'type': 'text', 'content': 'Error: Malformed input data detected previously.', 'order_index': 0, 'version': 1, 'page_number':1, 'coordinates': None, 'created_at': '2024-01-01T00:00:00', 'updated_at': '2024-01-01T00:00:00'}
    ]
    result_error_content = crew_runner.run(content_block_dicts=error_sim_content)
    print(f"\nSuggested Title from Crew (error content input): {result_error_content.suggested_title}") 