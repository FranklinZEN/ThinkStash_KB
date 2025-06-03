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

class TitleOutput(BaseModel):
    """Pydantic model for the expected output of the title generation task."""
    generated_title: str = Field(description="The AI-generated title for the content.")

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
            # No context needed as text is in description
            # No async_execution, keep it simple for now
            # output_json / output_pydantic can be considered later if complex structured output is needed beyond a string
            # output_file for very long outputs, not applicable here
        )

    def run(self, content_block_dicts: List[Dict[str, Any]]) -> TitleGenerationOutput:
        print(f"GeneralPurposeTitleGenerationCrew running with {len(content_block_dicts)} content block(s).")

        # Step 1: Extract full text directly using the tool
        # The FullTextContentExtractorTool's _run method expects List[Dict[str, Any]]
        # Ensure the input format matches what the tool expects.
        try:
            print("[TitleGenerationCrew] Attempting to extract text using FullTextContentExtractorTool...")
            # The tool's _run method needs to be called correctly. 
            # If it's a BaseTool, it's usually agent.invoke(tool_input)
            # If we are using it directly, we call its _run method.
            extracted_text = self.full_text_extractor_tool._run(content_block_dicts=content_block_dicts)
            print(f"[TitleGenerationCrew] Extracted text (first 300 chars): {extracted_text[:300]}...")
        except Exception as e:
            print(f"[TitleGenerationCrew ERROR] Error during direct text extraction: {e}")
            extracted_text = "Error: Failed to extract text content for title generation."

        # Prepare task for the agent with the extracted text
        title_task = self._create_title_generation_task(extracted_text=extracted_text)

        # Setup Crew
        title_crew = Crew(
            agents=[self.title_crafting_agent],
            tasks=[title_task],
            process=Process.sequential,
            verbose=True, # Changed from 2 to True for Pydantic boolean validation
            # memory=False, # Default, appropriate for stateless title generation
            # embedder configuration for Crew AI >= 0.28.0 if memory is True & using specific embeddings
            # manager_llm can be set if using hierarchical agent structure, not for this simple crew
        )

        print("Kicking off Title Generation Crew...")
        # The result from crew.kickoff() is the raw output from the last task.
        # We expect this to be the string containing the title or an error message.
        crew_result = title_crew.kickoff() 

        print(f"Title Generation Crew execution finished. Raw result: {crew_result}")

        # Ensure the result is a string, as expected by TitleGenerationOutput
        final_title = ""
        if hasattr(crew_result, 'raw') and isinstance(getattr(crew_result, 'raw', None), str):
            raw_output_str = crew_result.raw
            print(f"Extracted raw output from CrewOutput.raw: '{raw_output_str}'")
            if raw_output_str.startswith("Error:"):
                final_title = raw_output_str  # Propagate agent's specific error
            elif not raw_output_str.strip():
                final_title = "Error: Title generation resulted in an empty string from crew."
            else:
                final_title = raw_output_str
        elif isinstance(crew_result, str):
            # Fallback for older CrewAI versions or if a raw string is somehow returned
            print(f"Crew result is already a string: '{crew_result}'")
            if crew_result.startswith("Error:"):
                final_title = crew_result
            elif not crew_result.strip():
                final_title = "Error: Title generation resulted in an empty string."
            else:
                final_title = crew_result
        else:
            print(f"[TitleGenerationCrew WARNING] Unexpected crew_result type: {type(crew_result)}. Full CrewOutput: {crew_result}")
            # Attempt to get a meaningful string from the tasks_output if possible
            tasks_output_str = ""
            if hasattr(crew_result, 'tasks_output') and crew_result.tasks_output:
                # Get the output of the last task
                last_task_output = crew_result.tasks_output[-1]
                if hasattr(last_task_output, 'raw_output') and isinstance(last_task_output.raw_output, str):
                    tasks_output_str = last_task_output.raw_output
                    print(f"Extracted raw output from last task's output: '{tasks_output_str}'")


            if tasks_output_str and not tasks_output_str.startswith("Error:") and tasks_output_str.strip():
                 final_title = tasks_output_str # Use last task output if it seems valid
            elif tasks_output_str and tasks_output_str.startswith("Error:"):
                 final_title = tasks_output_str # Propagate error from last task
            else:
                 final_title = "Error: Title generation failed due to an unexpected crew output format."

        # If text extraction itself failed, that error should take precedence
        # unless the agent produced a more specific error (which final_title would already hold).
        if extracted_text.startswith("Error:"):
            if final_title.startswith("Error:"):
                # If both extraction and agent processing resulted in errors,
                # prioritize the extraction error as it's earlier in the process.
                print(f"Text extraction failed ('{extracted_text}') and agent also produced an error ('{final_title}'). Using extraction error.")
                final_title = extracted_text
            else:
                # If extraction failed but agent somehow produced a non-error title (unlikely with current agent prompts)
                print(f"Text extraction failed ('{extracted_text}'), but crew generated a title ('{final_title}'). Overriding with extraction error as it's a prerequisite.")
                final_title = extracted_text
        
        return TitleGenerationOutput(suggested_title=final_title)

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