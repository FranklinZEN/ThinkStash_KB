from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI 
from typing import List, Dict, Any, Optional
import json
import os # Added for os.getenv as a fallback if settings doesn't have key directly
import ast # For ast.literal_eval

from aiservice.app.config.settings import settings # Import global settings
from aiservice.app.tools.llm_tools import (
    ContentStructuringLLMHelper, # Changed from Tool to Helper
    block_item_schema_for_llm_tool, # The schema for function calling
    ContentStructuringOutput, 
    StructuredContentBlock 
)
from aiservice.app.models.orchestration_models import ContentBlock # Final desired output block structure
from crewai.tools import BaseTool as CrewAIBaseTool_ForCheck # For isinstance check

# Global LLM for the Agent itself
agent_llm_instance = None # Renamed for clarity from just agent_llm to avoid confusion with tool's llm
if settings.openai_api_key and settings.default_llm_model:
    try:
        agent_llm_instance = ChatOpenAI(
            api_key=settings.openai_api_key,
            model_name=settings.default_llm_model
        )
        print(f"MinimalLLMCrew: Agent LLM initialized with model: {settings.default_llm_model}")
    except Exception as e:
        print(f"MinimalLLMCrew: ERROR - Failed to initialize Agent LLM: {e}.")
else:
    print("MinimalLLMCrew: WARNING - Agent LLM not configured.")

# Default LLM for the tool if no override is passed to MinimalLLMCrew
default_llm_for_tool_if_needed = None
if settings.openai_api_key and settings.default_llm_model:
    try:
        default_llm_for_tool_if_needed = ChatOpenAI(api_key=settings.openai_api_key, model_name=settings.default_llm_model)
    except Exception: pass # Silently fail for default, tool init will raise if truly needed and not provided

class MinimalLLMCrew:
    """
    A minimal CrewAI setup for LLM-dependent content structuring tasks.
    Uses a ContentAnalystAgent equipped with ContentStructuringLLMTool.
    """
    def __init__(self):
        self.agent_llm = agent_llm_instance
        if not self.agent_llm:
            print("MinimalLLMCrew __init__: CRITICAL - Agent LLM is not configured. Agent cannot function.")
            # In a real app, might raise ValueError here

        # Instantiate the helper class, passing the agent's LLM to it
        # (or could use default_llm_client_for_tools from llm_tools.py if desired)
        self.structuring_helper = ContentStructuringLLMHelper(llm_instance=self.agent_llm)

        self.content_analyst_agent = Agent(
            role="Content Structuring Specialist",
            goal=("Given 'raw_text_content' and 'image_metadata_list' from task arguments, I will directly use my LLM capabilities "
                  "(leveraging an internal structuring helper with a specific function calling schema named 'format_content_blocks') "
                  "to process this data. My final answer MUST be the JSON object argument that was successfully passed to the 'format_content_blocks' function."),
            backstory=("I am an AI assistant that uses my own LLM and a predefined function calling schema to structure content. "
                       "I ensure the output is the exact JSON arguments from the function call, using the full provided text and metadata."),
            tools=[], # Agent has no external CrewAI tools for this task
            llm=self.agent_llm, 
            verbose=True, 
            allow_delegation=False
        )

    def create_structuring_task(self, raw_text: str, image_metadata: List[Dict[str, Any]]) -> Task:
        task_arguments = {
            "raw_text_content": raw_text, 
            "image_metadata_list": image_metadata
            # The agent will use these arguments to call self.structuring_helper.perform_direct_structuring
        }
        image_metadata_snippet_for_desc = json.dumps(image_metadata[:1]) + ("..." if len(image_metadata) > 1 else "")

        # The agent will perform the structuring internally using its LLM and the helper logic.
        # The description guides the agent on how to use its arguments for this internal process.
        return Task(
            description=(
                f"Task: Structure content using your internal LLM and the predefined 'format_content_blocks' function calling schema. "
                f"Process the 'raw_text_content' (approx. {len(raw_text)} chars) and 'image_metadata_list' ({len(image_metadata)} items, e.g., {image_metadata_snippet_for_desc}) from your task arguments. "
                f"You will effectively be calling a helper method that encapsulates the LLM call with function calling. "
                f"Ensure the full text and all image metadata are used. "
                f"Your final answer MUST be the JSON object representing the arguments of the 'format_content_blocks' function call."
            ),
            expected_output=(
                "A single JSON object string, representing the arguments for the 'format_content_blocks' function call (this object must contain a 'blocks' key with a list of structured content objects)."
            ),
            agent=self.content_analyst_agent,
            arguments=task_arguments,
            # This is where we define the agent's action if not using tools:
            # The agent, when this task is run, will execute this function.
            # We need to ensure this function has access to `self.structuring_helper` and task arguments.
            # This is a more advanced CrewAI pattern.
            # For now, we assume the agent's LLM, based on the goal/description, will know to call a Python method if we could equip it so.
            # --- OR --- the agent's response will be the JSON it *would* have used, and we parse that.
            # The current `run` method assumes the agent's final response *is* the JSON string.
        )

    def run(self, raw_text: str, image_metadata: List[Dict[str, Any]]) -> List[StructuredContentBlock]:
        if not self.agent_llm:
            print("MinimalLLMCrew.run(): CRITICAL - Agent LLM not configured.")
            return []
        
        # The agent itself is now responsible for the logic that was in ContentStructuringLLMTool.perform_direct_structuring
        # It will use its own LLM (self.agent_llm) and the schema (block_item_schema_for_llm_tool).
        # We are essentially asking the agent to perform this complex LLM call with function calling as its main action.
        
        structuring_task = self.create_structuring_task(raw_text, image_metadata)
        minimal_crew = Crew(
            agents=[self.content_analyst_agent],
            tasks=[structuring_task],
            process=Process.sequential,
            verbose=2 
        )
        
        # The task arguments are already in `structuring_task.arguments`
        # The agent should pick these up and use them for its direct LLM call.
        try:
            crew_kickoff_result = minimal_crew.kickoff() 
            print(f"MinimalLLMCrew: kickoff result type: {type(crew_kickoff_result)}")
            raw_agent_output_str = str(crew_kickoff_result).strip()
            if hasattr(crew_kickoff_result, 'tasks_output') and crew_kickoff_result.tasks_output:
                raw_agent_output_str = str(crew_kickoff_result.tasks_output[0].raw).strip()
            print(f"MinimalLLMCrew: Agent's raw output from kickoff: {raw_agent_output_str[:1000]}...")

            if raw_agent_output_str:
                cleaned_json_str = raw_agent_output_str
                if cleaned_json_str.startswith("```json"):
                    cleaned_json_str = cleaned_json_str[7:]
                    if cleaned_json_str.endswith("```"):
                        cleaned_json_str = cleaned_json_str[:-3]
                elif cleaned_json_str.startswith("```"):
                    cleaned_json_str = cleaned_json_str[3:]
                    if cleaned_json_str.endswith("```"):
                        cleaned_json_str = cleaned_json_str[:-3]
                cleaned_json_str = cleaned_json_str.strip()
                try:
                    output_dict = None
                    if (cleaned_json_str.startswith('{') and cleaned_json_str.endswith('}')):
                        try: output_dict = ast.literal_eval(cleaned_json_str)
                        except (ValueError, SyntaxError): 
                            print(f"MinimalLLMCrew: ast.literal_eval failed, attempting json.loads for: {cleaned_json_str[:200]}...")
                            output_dict = json.loads(cleaned_json_str) 
                    else:
                        print(f"MinimalLLMCrew: Agent output was not a dict-like string: {cleaned_json_str[:500]}")
                        return []
                    
                    # output_dict is now expected to be the args of the function call, i.e., {"blocks": [...]}
                    parsed_output = ContentStructuringOutput(**output_dict) 
                    if parsed_output.error_message:
                        print(f"MinimalLLMCrew: Parsed output contained an error from LLM: {parsed_output.error_message}")
                        return [] 
                    return parsed_output.blocks
                except Exception as e_parse: 
                    print(f"MinimalLLMCrew: Error parsing agent output: {e_parse}. String was: {cleaned_json_str[:500]}")
                    return []
            else:
                print(f"MinimalLLMCrew: No valid string output obtained from crew agent.")
                return []
        except Exception as e:
            print(f"MinimalLLMCrew: Error running crew - {str(e)}")
            import traceback; traceback.print_exc() 
            return []

# Need to import json for parsing if task output is stringified JSON
# import json # Removed redundant import 