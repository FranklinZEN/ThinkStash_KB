#!/usr/bin/env python
# coding: utf-8
"""
Defines the GeneralPurposeTitleGenerationCrew, responsible for orchestrating
agents to generate a title for a given list of content blocks.
Aligns with V2.6 Development Plan - Iteration 1.2.
"""

from crewai import Crew, Process, Task
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import json

from aiservice.app.agents.title_generation_agents import TitleGenerationAgents
from aiservice.app.models.orchestration_models import ContentBlock
from crewai.crews.crew_output import CrewOutput # Import CrewOutput

class TitleOutput(BaseModel):
    """Pydantic model for the expected output of the title generation task."""
    generated_title: str = Field(description="The AI-generated title for the content.")

class GeneralPurposeTitleGenerationCrew:
    """Creates and runs a CrewAI crew for generating titles from content blocks."""

    def __init__(self, user_id: str = "default_crew_user"):
        """
        Initializes the crew.
        Args:
            user_id: Identifier for the user, can be used for logging or if agents need it.
        """
        self.user_id = user_id
        # Agents factory can be initialized here if it doesn't need per-run parameters
        # or if user_id is the only parameter needed at init time.
        self.agents_factory = TitleGenerationAgents() # Pass user_id if TitleGenerationAgents expects it

    def _create_title_task(self, agent: Any) -> Task:
        """
        Creates the title generation task for the given agent.
        The task description guides the agent to use its tools sequentially and handle errors:
        1. FullTextContentExtractorTool to process 'content_block_dicts'.
        2. Check if text was extracted; if not, output error in 'generated_title'.
        3. OptimizedLLMInteractionTool to generate the title using the extracted text with temperature 0.1.
        """
        return Task(
            description=(
                "Your primary objective is to generate a title.\\n"
                "IMPORTANT: Your task inputs contain a key named 'content_block_dicts'. The value associated with this key is a list of dictionaries, where each dictionary is a complete representation of a content block.\\n"
                "Step 1: You MUST use the 'FullTextContentExtractorTool'. This tool expects a single argument which is a list of content block dictionaries. "
                "You MUST provide the list of dictionaries (obtained from the 'content_block_dicts' key in your task inputs) directly as the argument to this tool. DO NOT WRAP IT IN ANOTHER DICTIONARY. DO NOT MODIFY OR SIMPLIFY THIS LIST. "
                "The tool will return a string. Store this string result as 'extracted_text'.\\n"
                "Step 2: Examine the 'extracted_text'. IF 'extracted_text' is an empty string, OR IF it starts with the literal string 'Error:', THEN title generation is not possible. In this scenario, your final output for the 'generated_title' field MUST be the exact string 'Error: No content available for title generation.'.\\n"
                "Step 3: IF 'extracted_text' is valid (not empty and not an error string), THEN use this 'extracted_text' to generate a title. Call the 'OptimizedLLMInteractionTool', providing the 'extracted_text' as input to the tool. For this LLM call, you MUST use a temperature setting of 0.1. The result should be a concise and relevant title, ideally under 15 words.\\n"
                "Your final output MUST be a JSON object that strictly conforms to the TitleOutput Pydantic model, specifically by populating the 'generated_title' field with your result (either the generated title or the error message)."
            ),
            expected_output=(
                "A single string representing the generated title, or an error message if title generation was not possible. "
                "This output must conform to the TitleOutput Pydantic model, "
                "specifically populating the 'generated_title' field."
            ),
            agent=agent,
            output_pydantic=TitleOutput, # Ensures the output is validated against TitleOutput
            # async_execution=False, # Default is False, explicit if needed
        )

    def run(self, content_blocks: List[ContentBlock]) -> str:
        """
        Runs the title generation crew with the given content blocks.

        Args:
            content_blocks: A list of ContentBlock objects to process.

        Returns:
            A string containing the suggested title, or an error message string.
        """
        title_agent = self.agents_factory.title_crafting_agent()
        title_task = self._create_title_task(title_agent)

        crew = Crew(
            agents=[title_agent],
            tasks=[title_task],
            process=Process.sequential, # Tasks will be executed sequentially
            verbose=True, # Changed from integer 2 to boolean True
            memory=False # This crew is stateless for each run
            # manager_llm=None, # Optional: Specify a manager LLM if needed for complex flows
        )

        # Inputs for the kickoff. The task description tells the agent
        # to find 'content_block_dicts' here.
        task_inputs = {
            "content_block_dicts": [block.model_dump() for block in content_blocks]
        }

        print(f"INFO: Kicking off GeneralPurposeTitleGenerationCrew for user: {self.user_id} with {len(content_blocks)} content blocks (serialized to dicts).")
        kickoff_result = crew.kickoff(inputs=task_inputs)
        print(f"INFO: GeneralPurposeTitleGenerationCrew kickoff complete. Result type: {type(kickoff_result)}")

        if isinstance(kickoff_result, CrewOutput):
            print(f"DEBUG: Crew returned CrewOutput. Tasks output count: {len(kickoff_result.tasks_output) if kickoff_result.tasks_output else 'N/A'}")
            final_title_str = None

            # Attempt 1: Check if CrewOutput itself has a Pydantic object (newer CrewAI versions might put the *final task's* Pydantic output here)
            if hasattr(kickoff_result, 'pydantic') and isinstance(kickoff_result.pydantic, TitleOutput):
                print(f"DEBUG: Extracted TitleOutput from CrewOutput.pydantic: {kickoff_result.pydantic.generated_title}")
                final_title_str = kickoff_result.pydantic.generated_title
            
            # Attempt 2: Check tasks_output (usually where individual task outputs reside)
            if final_title_str is None and kickoff_result.tasks_output:
                task_output = kickoff_result.tasks_output[0] # Assuming the first/only task is the one we want
                title_to_return_from_task = None

                if hasattr(task_output, 'parsed_output') and isinstance(task_output.parsed_output, TitleOutput):
                    title_pydantic_obj = task_output.parsed_output
                    print(f"DEBUG: Extracted TitleOutput from tasks_output[0].parsed_output: {title_pydantic_obj.generated_title}")
                    title_to_return_from_task = title_pydantic_obj.generated_title
                
                if title_to_return_from_task is None and hasattr(task_output, 'raw_output') and isinstance(task_output.raw_output, str):
                    raw_title_str = task_output.raw_output
                    print(f"DEBUG: Extracted raw_output from tasks_output[0].raw_output: {raw_title_str}")
                    try:
                        data = json.loads(raw_title_str)
                        if isinstance(data, dict) and 'generated_title' in data and isinstance(data['generated_title'], str):
                            print("DEBUG: Parsed 'generated_title' from task's raw_output JSON string.")
                            title_to_return_from_task = data['generated_title']
                        else:
                            print("DEBUG: Task's raw_output was JSON but not TitleOutput structure, using raw string.")
                            title_to_return_from_task = raw_title_str
                    except json.JSONDecodeError:
                        print("DEBUG: Task's raw_output was not JSON, using raw string directly.")
                        title_to_return_from_task = raw_title_str
                
                if title_to_return_from_task is not None:
                    final_title_str = title_to_return_from_task

            # Attempt 3: Check CrewOutput.raw (often contains the string output of the last task if not Pydantic)
            if final_title_str is None and hasattr(kickoff_result, 'raw') and isinstance(kickoff_result.raw, str):
                raw_crew_result_str = kickoff_result.raw
                print(f"DEBUG: Extracted string from CrewOutput.raw: {raw_crew_result_str}")
                try:
                    data = json.loads(raw_crew_result_str)
                    if isinstance(data, dict) and 'generated_title' in data and isinstance(data['generated_title'], str):
                        print("DEBUG: Parsed 'generated_title' from CrewOutput.raw JSON string.")
                        final_title_str = data['generated_title']
                    else:
                        print("DEBUG: CrewOutput.raw was JSON but not TitleOutput, using raw string.")
                        final_title_str = raw_crew_result_str # Use the raw string if JSON doesn't match
                except json.JSONDecodeError:
                    print("DEBUG: CrewOutput.raw was not JSON, using raw string directly.")
                    final_title_str = raw_crew_result_str # Use the raw string if not JSON

            if final_title_str is not None:
                return final_title_str.strip('"\'')

        # Fallback for older CrewAI or direct Pydantic model return (less likely)
        if isinstance(kickoff_result, TitleOutput):
            print(f"DEBUG: Crew returned TitleOutput directly. Title: {kickoff_result.generated_title}")
            return kickoff_result.generated_title.strip('"\'')
        
        # Fallback handling for different result structures (should be less needed with CrewOutput handling)
        raw_output_text = None
        if hasattr(kickoff_result, 'raw_output') and isinstance(kickoff_result.raw_output, str): # e.g. if CrewOutput itself has a raw_output attr
            raw_output_text = kickoff_result.raw_output
        elif isinstance(kickoff_result, str):
            raw_output_text = kickoff_result
        elif isinstance(kickoff_result, dict):
            if 'generated_title' in kickoff_result and isinstance(kickoff_result['generated_title'], str):
                print("DEBUG: Crew returned dict with 'generated_title'.")
                return kickoff_result['generated_title'].strip('"\'')
            else:
                try: raw_output_text = json.dumps(kickoff_result)
                except: pass
        
        if raw_output_text:
            print(f"DEBUG: Crew returned raw output text (fallback): {raw_output_text[:200]}...")
            try:
                data = json.loads(raw_output_text)
                if isinstance(data, dict) and 'generated_title' in data and isinstance(data['generated_title'], str):
                    return data['generated_title'].strip('"\'')
            except json.JSONDecodeError:
                return raw_output_text.strip('"\'') 

        error_msg = f"Error: Title generation failed or produced an unexpected result structure. Type: {type(kickoff_result)}, Value: {str(kickoff_result)[:200]}..."
        print(f"ERROR: {error_msg}")
        return error_msg

# Example Usage (commented out, for direct testing if needed):
# if __name__ == '__main__':
#     from uuid import uuid4
#     # Define or import ContentBlock for this example to run
#     # class ContentBlock(BaseModel):
#     #     block_id: str; tmp_id: Optional[str]; user_id: str; document_id: str; type: str; 
#     #     order_index: Optional[int]; content: Optional[str]; level: Optional[int]; 
#     #     items: Optional[List[Any]]; ordered: Optional[bool]; image_id_ref: Optional[str] = None

#     sample_blocks_data = [
#         {"block_id": str(uuid4()), "tmp_id":str(uuid4()), "user_id": "test_user", "document_id": "doc1", "type": "heading", "order_index": 0, "content": "The Future of AI", "level": 1},
#         {"block_id": str(uuid4()), "tmp_id":str(uuid4()), "user_id": "test_user", "document_id": "doc1", "type": "text", "order_index": 1, "content": "Artificial intelligence is rapidly changing various industries. This document explores the potential impacts and future trends."},
#         {"block_id": str(uuid4()), "tmp_id":str(uuid4()), "user_id": "test_user", "document_id": "doc1", "type": "list", "order_index": 2, "items": ["Healthcare advancements", "Autonomous transportation", "Personalized education"], "ordered": False},
#     ]
#     # This assumes ContentBlock can be instantiated with these fields.
#     # Adjust if ContentBlock definition is different or has more required fields.
#     sample_content_blocks = [ContentBlock(**block) for block in sample_blocks_data]

#     print("Running title generation crew example...")
#     title_crew_instance = GeneralPurposeTitleGenerationCrew(user_id="example_main_user")
#     generated_title = title_crew_instance.run(content_blocks=sample_content_blocks)
#     print(f"\n==> Suggested Title by Crew: {generated_title}") 