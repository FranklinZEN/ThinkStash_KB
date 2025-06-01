#!/usr/bin/env python
# coding: utf-8
"""
Defines the crew responsible for general-purpose keyword extraction.
"""

import json
from typing import List, Dict, Any, Optional
from crewai import Crew, Process, Task
from aiservice.app.models.orchestration_models import ContentBlock
from aiservice.app.agents.keyword_extraction_agents import KeywordIdentificationAgent
# Assuming Gemini LLM setup is handled globally or passed during crew initialization if needed by agents/tools directly
# from langchain_google_genai import ChatGoogleGenerativeAI

class GeneralPurposeKeywordExtractionCrew:
    """
    A crew designed to extract relevant keywords from a list of ContentBlock objects.
    It utilizes a KeywordIdentificationAgent to perform the core extraction task.
    """
    def __init__(self, llm_provider_config: Optional[Dict[str, Any]] = None):
        """
        Initializes the crew with its agent and task.
        llm_provider_config: Optional configuration for the LLM, if required by agents/tools directly.
                             For OptimizedLLMInteractionTool, this might not be needed here if it's self-configured.
        """
        self.agent = KeywordIdentificationAgent()
        # self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", verbose=True, temperature=0.1) # Example direct LLM
        # The plan is to use OptimizedLLMInteractionTool which should handle LLM interaction.

    def _create_task(self, content_blocks_json_string: str) -> Task:
        """
        Creates the keyword extraction task for the agent.
        The task input is a JSON string representation of List[ContentBlock].
        The FullTextContentExtractorTool used by the agent expects List[ContentBlock],
        but the task description input mechanism for agents in CrewAI typically takes string inputs.
        The tool itself should handle the conversion if necessary, or the agent adapts.
        Let's assume the FullTextContentExtractorTool can accept the direct List[ContentBlock]
        if passed in the `inputs` dict to kickoff, or it can parse the string if needed.
        For simplicity, we'll use the stringified content as the main descriptive input.
        """
        return Task(
            description=(
                f"Analyze the following content and extract 5-7 key terms or concepts. "
                f"The content is provided as a JSON string of content blocks: {content_blocks_json_string}. "
                f"Focus on identifying the most salient topics. Return the keywords as a simple list of strings."
            ),
            expected_output="A list of 5-7 unique keywords as strings (e.g., ['keyword1', 'keyword2', 'keyword3']).",
            agent=self.agent,
            # context=None, # No specific context needed beyond the content itself for this task
        )

    def run(self, content_blocks: List[ContentBlock]) -> List[str]:
        """
        Runs the keyword extraction crew with the given list of content blocks.

        Args:
            content_blocks: A list of ContentBlock objects to process.

        Returns:
            A list of suggested keywords. Returns an empty list if extraction fails or no keywords are found.
        """
        if not content_blocks:
            return []

        # Convert content_blocks to a JSON string for the task description input
        # The FullTextContentExtractorTool within the agent should ideally take List[ContentBlock]
        # directly. We are passing it via the `inputs` to kickoff.
        try:
            # Create a simplified list of dicts for JSON string representation if needed for task description
            simplified_blocks = [block.model_dump(exclude_none=True) for block in content_blocks]
            content_blocks_json_string = json.dumps(simplified_blocks)
        except Exception as e:
            # Handle potential serialization errors, though Pydantic models should be serializable
            print(f"Error serializing content_blocks for keyword extraction task: {e}")
            # Fallback or error handling if serialization fails for description
            content_blocks_json_string = "[Error serializing content blocks]"

        task = self._create_task(content_blocks_json_string)

        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            process=Process.sequential,
            verbose=2 # Set verbosity for debugging; can be configured
            # llm=self.llm # If passing LLM directly to crew
        )

        # The `inputs` dictionary to `kickoff` is where we can pass complex objects like `content_blocks`
        # that tools within agents can pick up.
        # The FullTextContentExtractorTool is designed to take `content_blocks: List[ContentBlock]`
        # The OptimizedLLMInteractionTool takes `text_to_process: str` and `prompt_template: str`.
        # The agent will first use FullTextContentExtractorTool, then its output (string) will be used by LLM tool.
        
        inputs_for_kickoff = {
            # This key `content_blocks` must match what FullTextContentExtractorTool expects or can handle.
            # If FullTextContentExtractorTool._run expects `content_blocks: List[ContentBlock]`, this is correct.
            "content_blocks": content_blocks 
        }
        
        # For the LLM tool, the prompt is embedded in the agent's goal/task, and the input text comes from the first tool.
        # So, no explicit "text_to_process" or "prompt_template" needed in `inputs_for_kickoff` for the LLM tool itself.

        result_raw = crew.kickoff(inputs=inputs_for_kickoff)

        # Process the result_raw to extract the list of keywords
        # The expected output from the task is "A list of 5-7 unique keywords as strings"
        # The actual output from the LLM might be a string that needs parsing,
        # or if the LLM tool/agent is well-prompted, it might be a directly usable list.

        if isinstance(result_raw, str):
            try:
                # Attempt to parse if it looks like a JSON list string
                if result_raw.strip().startswith("[") and result_raw.strip().endswith("]"):
                    parsed_result = json.loads(result_raw)
                    if isinstance(parsed_result, list) and all(isinstance(item, str) for item in parsed_result):
                        return parsed_result
                # Otherwise, if it's a comma-separated string or newline-separated, split it.
                # This is a simple heuristic; more robust parsing might be needed based on LLM output variance.
                keywords = [kw.strip() for kw in result_raw.replace("\n", ",").split(",") if kw.strip()]
                return list(set(keywords)) # Ensure uniqueness and return as list
            except json.JSONDecodeError:
                # If not a JSON list, and splitting by comma doesn't make sense, return as single item list or process further.
                # For now, assume comma/newline separation or a single keyword string if not JSON.
                keywords = [kw.strip() for kw in result_raw.replace("\n", ",").split(",") if kw.strip()]
                return list(set(keywords)) if keywords else [] # Return empty if split results in nothing
        elif isinstance(result_raw, list) and all(isinstance(item, str) for item in result_raw):
            return list(set(result_raw)) # Already a list of strings, ensure uniqueness
        
        return [] # Default to empty list if result is not in expected format

# Example Usage (for testing purposes):
# if __name__ == "__main__":
#     from aiservice.app.models.orchestration_models import ContentBlock

#     # Sample ContentBlocks
#     sample_blocks = [
#         ContentBlock(block_id="1", type="text", text_content="Artificial intelligence is rapidly changing the world."),
#         ContentBlock(block_id="2", type="text", text_content="Machine learning, a subset of AI, is key to this transformation.")
#     ]

#     keyword_crew = GeneralPurposeKeywordExtractionCrew()
#     keywords = keyword_crew.run(sample_blocks)
#     print(f"Suggested Keywords: {keywords}") 