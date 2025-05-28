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
            model_name=settings.default_llm_model,
            temperature=0.0
        )
        print(f"MinimalLLMCrew: Agent LLM initialized with model: {settings.default_llm_model}, Temperature: 0.0")
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
        }
        image_metadata_snippet_for_desc = json.dumps(image_metadata[:1]) + ("..." if len(image_metadata) > 1 else "")

        description = (
            f"Task: Structure content using your internal LLM and the predefined 'format_content_blocks' function calling schema. "
            f"You have received 'raw_text_content' (approx. {len(raw_text)} chars) and 'image_metadata_list' ({len(image_metadata)} items, e.g., {image_metadata_snippet_for_desc}) as direct task arguments. "
            f"To achieve this, you will construct and execute an LLM call that invokes the 'format_content_blocks' function. "
            f"CRITICAL: The 'user prompt' section for THIS INTERNAL LLM CALL must include a specific segment, for example, labeled 'Raw Text to Structure:'. "
            f"The text that follows this 'Raw Text to Structure:' label in your constructed user prompt MUST BE THE EXACT, VERBATIM, UNALTERED 'raw_text_content' string you received in your task arguments. Do NOT summarize, shorten, paraphrase, or modify it in any way before placing it into that prompt. "
            f"The system prompt for this internal LLM call (derived from ContentStructuringLLMHelper's system_prompt_content) will provide further strict instructions to ONLY use text from this 'Raw Text to Structure' for any generated 'content' fields within the function arguments. "
            f"Your final answer for this task MUST be the single JSON object representing the arguments successfully passed to the 'format_content_blocks' function call. This JSON object must contain a 'blocks' key with a list of structured content objects, where all textual 'content' fields are verbatim extractions from the original 'raw_text_content'."
        )
        expected_output=(
            "A single JSON object string, representing the arguments for the 'format_content_blocks' function call (this object must contain a 'blocks' key with a list of structured content objects, where 'content' fields are verbatim extractions from the input 'raw_text_content')."
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=self.content_analyst_agent,
            arguments=task_arguments,
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
            verbose=True
        )
        
        # The task arguments are already in `