#!/usr/bin/env python
# coding: utf-8
"""
Defines the Crew for General Purpose AI Keyword Extraction.
"""
from typing import List, Dict, Any, Union
import json # For parsing stringified list output from LLM if necessary
import re # Added for robust parsing of LLM list output
import ast # Added for robust parsing of LLM list output

from aiservice.app.config.logging_config import get_logger
from aiservice.app.config.settings import Settings # MODIFIED: Import Settings

from crewai import Crew, Process, Task
# from crewai.tasks.task_output import TaskOutput # TaskOutput is available via crew_result.tasks_output[0] if needed

from aiservice.app.agents.keyword_extraction_agents import KeywordExtractionAgents
from aiservice.app.tools.content_processing_tools import FullTextContentExtractorTool
# KeywordToTagFormatterTool is used by the agent, not directly by the crew typically

class GeneralPurposeKeywordExtractionCrew:
    def __init__(self, content_blocks: List[Dict[str, Any]]):
        self.logger = get_logger(self.__class__.__name__)
        self.content_blocks = content_blocks
        
        self.settings = Settings() # MODIFIED: Initialize Settings
        llm_instance = self.settings.get_crew_llm() # MODIFIED: Get LLM instance via Settings

        # Initialize agents
        # MODIFIED: Pass llm_instance to agent_factory using 'llm_client' as expected by KeywordExtractionAgents
        agent_factory = KeywordExtractionAgents(llm_client=llm_instance) 
        self.keyword_agent = agent_factory.keyword_identifier_agent()

        # Initialize tools for tasks (if any are directly used by tasks and not just agents)
        self.full_text_extractor_tool = FullTextContentExtractorTool()

    def _create_keyword_extraction_task_description_suffix(self) -> str:
        """Helper to keep the main task description part tidy."""
        return (
            "Analyze the provided full text content to identify 3-7 of the most relevant and specific key terms or concepts. "
            "These can be single words or short phrases. Focus on terms that represent the core topics of the content.\n"
            "IMPORTANT FORMATTING REQUIREMENTS:\n"
            "1. After identifying the raw key terms/concepts, you MUST use the 'Keyword to Tag Formatter' tool to convert them into standardized tags.\n"
            "2. The tool will handle common abbreviations (e.g., 'Artificial Intelligence' becomes '#AI', 'Machine Learning' becomes '#ML').\n"
            "3. For specific concepts or multi-word terms that are not common abbreviations, the tool will format them in UpperCamelCase (e.g., 'Ads Prediction' becomes '#AdsPrediction', 'System Architecture' becomes '#SystemArchitecture').\n"
            "4. The final output of this task MUST be a Python list of these formatted string tags.\n"
            "Example desired output format: ['#AI', '#SystemArchitecture', '#DataAnalysis']"
        )

    def run(self) -> Union[List[str], str]:
        self.logger.info("Starting Keyword Extraction Crew execution...")
        
        try:
            full_text_content = self.full_text_extractor_tool._run(content_block_dicts=self.content_blocks)
            self.logger.debug(f"Full text extracted (first 500 chars): {full_text_content[:500]}...")
        except Exception as e:
            self.logger.error(f"Error during full text extraction: {e}", exc_info=True)
            return f"Error: Failed to extract text from content blocks - {str(e)}"

        if not full_text_content or (isinstance(full_text_content, str) and full_text_content.startswith("Error:")):
            error_msg = full_text_content if isinstance(full_text_content, str) and full_text_content.strip() else "Error: Extracted text content is empty."
            self.logger.warning(f"Full text extraction resulted in an error or empty content: {error_msg}")
            return error_msg

        task_desc_suffix = self._create_keyword_extraction_task_description_suffix()
        # Prepend the full text content to the task description for the agent to use.
        current_task_description = (
            f"Text Content to Analyze:\n"
            f"------------------------\n"
            f"{full_text_content}\n"
            f"------------------------\n\n"
            f"Based on the Text Content to Analyze provided above, your task is as follows:\n"
            f"{task_desc_suffix}"
        )

        keyword_task = Task(
            description=current_task_description,
            expected_output=(
                "A Python list of 3-7 string tags, each starting with '#', correctly abbreviated or CamelCased. "
                "Example: ['#AI', '#SystemArchitecture', '#DataAnalysis']"
            ),
            agent=self.keyword_agent,
        )
        
        self.logger.info(f"Kicking off crew with task description including text of length: {len(full_text_content)}")
        
        crew = Crew(
            agents=[self.keyword_agent],
            tasks=[keyword_task],
            process=Process.sequential,
            verbose=True 
        )
        crew_result = crew.kickoff()
        self.logger.info(f"Keyword Extraction Crew execution finished. Raw CrewOutput: {crew_result}")

        final_keywords: Union[List[str], str] = "Error: Keyword extraction failed to produce a recognizable list."

        raw_output_str = None
        # CrewAI >= 0.28.0, kickoff() returns a CrewOutput object.
        # The actual result of the last task is in crew_result.raw or crew_result.tasks_output[0].exported_output
        if hasattr(crew_result, 'raw') and isinstance(crew_result.raw, str):
            raw_output_str = crew_result.raw
        elif hasattr(crew_result, 'tasks_output') and crew_result.tasks_output:
             # Check the last task's output
            last_task_output = crew_result.tasks_output[-1]
            if hasattr(last_task_output, 'exported_output') and isinstance(last_task_output.exported_output, str):
                raw_output_str = last_task_output.exported_output
            elif hasattr(last_task_output, 'raw_output') and isinstance(last_task_output.raw_output, str):
                raw_output_str = last_task_output.raw_output # Older attribute, but check just in case
        elif isinstance(crew_result, str): # Fallback for very old CrewAI or direct string error
            raw_output_str = crew_result
        
        if raw_output_str:
            self.logger.info(f"Extracted raw output string for parsing: '{raw_output_str}'")
            if not raw_output_str.strip():
                final_keywords = "Error: Keyword extraction resulted in an empty string from the crew."
            elif raw_output_str.startswith("Error:"):
                final_keywords = raw_output_str 
            else:
                try:
                    # Attempt to parse if it looks like a stringified list.
                    parsed_list = ast.literal_eval(raw_output_str)
                    if isinstance(parsed_list, list) and all(isinstance(item, str) for item in parsed_list):
                        final_keywords = parsed_list
                    else:
                        self.logger.warning(f"Raw output was a string list but ast.literal_eval failed to yield List[str]: {parsed_list}")
                        final_keywords = f"Error: Output was string list-like but not in expected List[str] format: {raw_output_str}"
                except (ValueError, SyntaxError) as e_parse:
                    self.logger.warning(f"ast.literal_eval parsing of raw output failed: {e_parse}. Trying regex extraction for list-like patterns.")
                    # Fallback: try to extract list-like string using regex (less robust)
                    try:
                        # This regex looks for something like: ['#Tag1', '#Tag2'] or ["#Tag1", "#Tag2"]
                        match = re.search(r"(\[\s*(?:\'[^\']+\'|\"[^\"]+\")(?:\s*,\s*(?:\'[^\']+\'|\"[^\"]+\"))*\s*\])", raw_output_str)
                        if match:
                            potential_list_str = match.group(1)
                            self.logger.info(f"Regex extracted potential list string: {potential_list_str}")
                            parsed_list_regex = ast.literal_eval(potential_list_str)
                            if isinstance(parsed_list_regex, list) and all(isinstance(item, str) for item in parsed_list_regex):
                                final_keywords = parsed_list_regex
                            else:
                                raise ValueError("Regex extracted list, but not List[str]")
                        else:
                            self.logger.warning(f"No list-like structure found via regex in string: {raw_output_str}")
                            final_keywords = f"Error: Output string not a recognized list format: {raw_output_str}"
                    except (ValueError, SyntaxError) as e_regex_parse:
                        self.logger.error(f"Error parsing regex-extracted list string '{raw_output_str}': {e_regex_parse}", exc_info=True)
                        final_keywords = f"Error: Could not parse LLM output as list. Raw: {raw_output_str}"
                except Exception as e_general:
                     self.logger.error(f"General error processing raw output: {e_general}. Raw: {raw_output_str}", exc_info=True)
                     final_keywords = f"Error: An unexpected error occurred processing agent output. Raw: {raw_output_str}"
        # Handling for direct list output (e.g. if crew_result.raw was already a list from a tool)
        elif hasattr(crew_result, 'raw') and isinstance(crew_result.raw, list):
            potential_list = crew_result.raw
            if all(isinstance(item, str) for item in potential_list):
                final_keywords = potential_list
            else:
                self.logger.warning(f"Raw output was a list but not List[str]: {potential_list}")
                final_keywords = f"Error: Output was a list but not in expected List[str] format: {potential_list}"
        elif isinstance(crew_result, list) and all(isinstance(item, str) for item in crew_result): # Direct list from kickoff (very unlikely)
             final_keywords = crew_result
        else:
            self.logger.warning(f"Unexpected crew_result type or content not handled above. Value: {crew_result}")
            final_keywords = f"Error: Keyword extraction failed due to an unexpected crew output format or type. Result: {crew_result}"

        if isinstance(final_keywords, list):
            self.logger.info(f"Successfully extracted keywords: {final_keywords}")
        else: 
            self.logger.error(f"Keyword extraction failed: {final_keywords}")
            
        return final_keywords

# Example Usage (for testing, similar to Title Generation Crew)
# if __name__ == '__main__':
#     from aiservice.app.models.content_structuring_models import ContentBlock, ImageBlockData, ListBlockData
#     logger = get_logger("__main__")

#     # Sample ContentBlocks (replace with actual data or load from a JSON for testing)
#     sample_blocks_data = [
#         {"type": "heading", "level": 1, "text": "The Future of Artificial Intelligence"},
#         {"type": "text", "text": "Artificial intelligence (AI) is rapidly evolving. Its impact on various industries is profound, from healthcare to finance. Machine learning (ML) and large language models (LLMs) are key components of modern AI systems."},
#         {"type": "text", "text": "We also see advancements in ads prediction and overall system architecture improvements thanks to AI. Generative AI is a hot topic."}
#     ]
#     sample_content_blocks = [ContentBlock(**block) for block in sample_blocks_data]

#     logger.info("Initializing Keyword Extraction Crew for testing...")
#     keyword_crew = GeneralPurposeKeywordExtractionCrew(content_blocks=sample_content_blocks)
#     logger.info("Running Keyword Extraction Crew...")
#     results = keyword_crew.run()

#     logger.info("\n--- Keyword Extraction Results ---")
#     if isinstance(results, list):
#         logger.info(f"Suggested Keywords: {results}")
#         for kw in results:
#             logger.info(f" - {kw}")
#     else:
#         logger.error(f"Error: {results}")
#     logger.info("----------------------------") 