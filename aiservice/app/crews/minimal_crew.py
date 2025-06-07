from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI 
from typing import List, Dict, Any, Optional
import json
import os # Added for os.getenv as a fallback if settings doesn't have key directly
import ast # For ast.literal_eval

from aiservice.app.config.settings import settings # Corrected import
from aiservice.app.tools.llm_tools import (
    ContentStructuringLLMHelper, # Changed from Tool to Helper
    block_item_schema_for_llm_tool, # The schema for function calling
    ContentStructuringOutput, 
    StructuredContentBlock 
)
from aiservice.app.models.orchestration_models import ContentBlock # Corrected import
from crewai.tools import BaseTool as CrewAIBaseTool_ForCheck # For isinstance check
from crewai.tools import BaseTool # Corrected import if it were used, but seems it is not directly

# Global LLM for the Agent itself
agent_llm_instance = None # Renamed for clarity from just agent_llm to avoid confusion with tool's llm

if settings.use_gemini_via_openai_compatibility and \
   settings.gemini_api_key and \
   settings.gemini_text_model_compat and \
   settings.gemini_compatibility_base_url:
    try:
        agent_llm_instance = ChatOpenAI(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_text_model_compat, # Assuming agent uses the text model
            base_url=settings.gemini_compatibility_base_url,
            temperature=0.0
        )
        print(f"MinimalLLMCrew: Agent LLM initialized using GEMINI compatibility (Model: {settings.gemini_text_model_compat}, Temp: 0.0).")
    except Exception as e:
        print(f"MinimalLLMCrew: ERROR - Failed to initialize Agent LLM with GEMINI compatibility: {e}.")
elif settings.openai_api_key and settings.default_llm_model:
    try:
        agent_llm_instance = ChatOpenAI(
            api_key=settings.openai_api_key,
            model_name=settings.default_llm_model,
            temperature=0.0 # Ensure temperature is 0 for deterministic structuring
        )
        print(f"MinimalLLMCrew: Agent LLM initialized with OpenAI model: {settings.default_llm_model}, Temperature: 0.0")
    except Exception as e:
        print(f"MinimalLLMCrew: ERROR - Failed to initialize Agent LLM with OpenAI: {e}.")
else:
    print("MinimalLLMCrew: WARNING - Agent LLM not configured (neither Gemini nor OpenAI settings found).")

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
            print("MinimalLLMCrew __init__: CRITICAL - Agent LLM is not configured. Structuring will fail.")
            # Initialize helper with None, it should handle this
            self.structuring_helper = ContentStructuringLLMHelper(llm_instance=None)
        else:
            # If using Gemini, ContentStructuringLLMHelper should use its own default (Gemini-aware) client.
            # Otherwise, pass the normally configured OpenAI agent_llm.
            if settings.use_gemini_via_openai_compatibility:
                print("MinimalLLMCrew __init__: Using Gemini compatibility. ContentStructuringLLMHelper will use its default (Gemini-aware) LLM.")
                self.structuring_helper = ContentStructuringLLMHelper()
            else:
                print("MinimalLLMCrew __init__: Not using Gemini compatibility. Passing agent_llm to ContentStructuringLLMHelper.")
                self.structuring_helper = ContentStructuringLLMHelper(llm_instance=self.agent_llm)

        # The ContentAnalystAgent and its task are no longer directly used in .run()
        # but could be kept if there's a future use case for a CrewAI agent performing other actions.
        # For now, they are effectively bypassed by the direct call to the helper.
        self.content_analyst_agent_for_other_uses = Agent( # Renamed for clarity
            role="Content Structuring Specialist",
            goal=("This agent's run method is now bypassed for structuring. Structuring is done by ContentStructuringLLMHelper."),
            backstory=("I was an AI assistant for structuring content, but my primary structuring task is now handled directly by a helper class using LLM function calling."),
            tools=[], 
            llm=self.agent_llm, 
            verbose=True, 
            allow_delegation=False
        )

    def create_structuring_task_for_other_uses(self, raw_text: str, image_metadata: List[Dict[str, Any]]) -> Task:
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
            f"The system prompt for this internal LLM call (derived from ContentStructuringLLMHelper's system_prompt_content) will provide further strict instructions. These include: "
            f"  - ONLY use text from the 'Raw Text to Structure' for any generated 'content' fields within the function arguments for 'text', 'code', and 'math' blocks. "
            f"  - All general text segments MUST be output with type 'text'. Code segments as 'code', math as 'math'. "
            f"  - Image captions MUST be taken from provided metadata or be null if not provided; DO NOT invent captions. "
            f"Your final answer for this task MUST be the single JSON object representing the arguments successfully passed to the 'format_content_blocks' function call. This JSON object must contain a 'blocks' key with a list of structured content objects, where all textual 'content' fields are verbatim extractions from the original 'raw_text_content', and all block types are one of ['text', 'image_reference', 'code', 'math']."
        )
        expected_output=(
            "A single JSON object string, representing the arguments for the 'format_content_blocks' function call (this object must contain a 'blocks' key with a list of structured content objects, adhering to the type constraints ['text', 'image_reference', 'code', 'math'] and verbatim content rules)."
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=self.content_analyst_agent_for_other_uses,
            arguments=task_arguments,
        )

    def run(self, raw_text: str, image_metadata: List[Dict[str, Any]]) -> List[StructuredContentBlock]:
        if not self.structuring_helper or not self.structuring_helper.llm_instance:
            print("MinimalLLMCrew.run(): CRITICAL - Structuring helper or its LLM not configured.")
            return []
        
        print(f"MinimalLLMCrew.run: Calling ContentStructuringLLMHelper.perform_direct_structuring for raw_text (approx {len(raw_text)} chars) and {len(image_metadata)} images.")
        
        try:
            # Directly call the helper method that uses LLM function calling
            structuring_result_dict = self.structuring_helper.perform_direct_structuring(
                raw_text=raw_text,
                image_metadata=image_metadata
            )

            # The helper method already returns a dict that ContentStructuringOutput can parse
            # (or a dict with an 'error_message' key)
            if structuring_result_dict.get("error_message"):
                print(f"MinimalLLMCrew.run: Error from structuring_helper: {structuring_result_dict['error_message']}")
                return []

            # Validate and extract blocks
            validated_output = ContentStructuringOutput(**structuring_result_dict)
            print(f"MinimalLLMCrew.run: Successfully structured by helper, {len(validated_output.blocks)} blocks found.")
            return list(validated_output.blocks)

        except Exception as e_direct_call:
            print(f"MinimalLLMCrew.run: Exception during direct call to structuring_helper: {e_direct_call}")
            import traceback
            traceback.print_exc()
            return []