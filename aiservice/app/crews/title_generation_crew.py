#!/usr/bin/env python
# coding: utf-8
"""
Defines the GeneralPurposeTitleGenerationCrew, responsible for orchestrating
agents to generate a title for a given list of content blocks.
This version combines asynchronous execution with robust prompting and error handling.
"""

from crewai import Agent, Task, Crew, Process
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import asyncio

from aiservice.app.config.logging_config import get_logger
from aiservice.app.agents.title_generation_agents import TitleGenerationAgents
from aiservice.app.models.task_output_models import TitleGenerationOutput
from aiservice.app.tools.content_processing_tools import FullTextContentExtractorTool
from aiservice.app.config.settings import Settings

logger = get_logger(__name__)

class TitleOutput(BaseModel):
    """Pydantic model for the expected output of the title generation task."""
    generated_title: str = Field(description="The AI-generated title for the content.")

class GeneralPurposeTitleGenerationCrew:
    """Creates and runs a CrewAI crew for generating titles from content blocks."""

    def __init__(self, card_content: str, settings: Settings, job_id: Optional[str] = None):
        """Initializes the crew, agents, and tools."""
        self.card_content = card_content
        self.settings = settings
        self.job_id = job_id
        self.llm = self.settings.get_crew_llm()
        
        title_agents = TitleGenerationAgents()
        self.title_crafting_agent = title_agents.title_crafting_agent()

    def _create_title_generation_task(self) -> Task:
        """Creates the task for the title generation agent, embedding the pre-extracted text."""
        return Task(
            description=(
                f"Your primary objective is to generate a title for the following text content. "
                f"The text has already been extracted for you.\\n\\n"
                f"TEXT CONTENT TO ANALYZE:\\n"
                f"------------------------\\n"
                f"{self.card_content}\\n"
                f"------------------------\\n\\n"
                f"Step 1: Carefully review the TEXT CONTENT TO ANALYZE provided above.\\n"
                f"Step 2: IF the TEXT CONTENT TO ANALYZE appears to be empty, nonsensical, or an error message, "
                f"THEN your final output MUST be the exact string: "
                f"'Error: No valid content provided for title generation.'. DO NOT attempt to generate a title.\\n"
                f"Step 3: IF the TEXT CONTENT TO ANALYZE is valid, use your language model capabilities "
                f"to generate a concise, informative, and engaging title (ideally under 15 words) "
                f"that accurately reflects the main topic of the text. Use a low temperature (e.g., 0.0) to ensure factual titles.\\n"
                f"Step 4: Your final answer MUST ONLY be the title string, or the specific error string from Step 2."
            ),
            expected_output=(
                "A single string containing the generated title OR "
                "the specific error message 'Error: No valid content provided for title generation.' if title generation is not possible."
            ),
            agent=self.title_crafting_agent,
        )

    async def akickoff(self) -> str:
        """Asynchronously runs the crew to generate a title."""
        logger.info(f"Job {self.job_id}: GeneralPurposeTitleGenerationCrew kicking off.")

        title_task = self._create_title_generation_task()

        title_crew = Crew(
            agents=[self.title_crafting_agent],
            tasks=[title_task],
            process=Process.sequential,
            verbose=True,
        )

        logger.info(f"Job {self.job_id}: Kicking off Title Generation Crew asynchronously...")
        crew_result = await title_crew.kickoff_async()
        logger.info(f"Job {self.job_id}: Title Generation Crew execution finished. Full result object: {crew_result}")

        final_title = ""
        if crew_result and crew_result.tasks_output:
            last_task_output = crew_result.tasks_output[-1]
            if isinstance(last_task_output.raw, str):
                final_title = last_task_output.raw.strip()
                logger.info(f"Job {self.job_id}: Extracted final title from last task's raw output: '{final_title}'")
            else:
                logger.warning(f"Job {self.job_id}: Last task's 'raw' output was not a string: {last_task_output.raw}")
                final_title = "Error: Could not decode the final answer from the agent."
        else:
            logger.warning(f"Job {self.job_id}: Unexpected crew_result format or no tasks_output. Full output: {crew_result}")
            final_title = "Error: Title generation failed due to an unexpected crew output format."

        return final_title

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
    
    crew_runner = GeneralPurposeTitleGenerationCrew(card_content="", settings=Settings())
    
    # The run method now directly takes the list of content block dictionaries
    result_output = asyncio.run(crew_runner.akickoff())
    print(f"\nSuggested Title from Crew: {result_output}")

    # Test with empty content
    empty_content_blocks = []
    result_empty = asyncio.run(crew_runner.akickoff())
    print(f"\nSuggested Title from Crew (empty input): {result_empty}")

    # Test with content that should result in an error from the agent's perspective
    error_sim_content = [
         {'block_id': '1', 'user_id': 'test_user', 'document_id': 'doc1', 'type': 'text', 'content': 'Error: Malformed input data detected previously.', 'order_index': 0, 'version': 1, 'page_number':1, 'coordinates': None, 'created_at': '2024-01-01T00:00:00', 'updated_at': '2024-01-01T00:00:00'}
    ]
    result_error_content = asyncio.run(crew_runner.akickoff())
    print(f"\nSuggested Title from Crew (error content input): {result_error_content}") 