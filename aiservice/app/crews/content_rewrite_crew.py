#!/usr/bin/env python
# coding: utf-8
"""
Defines the ContentRewriteCrew, responsible for orchestrating agents
to rewrite/summarize content based on the V2.6 plan.
"""

from crewai import Crew, Process, Task
from typing import List, Dict, Any, Optional
import json
import re
import time
import uuid
import ast
from textwrap import dedent
from pydantic import BaseModel, Field, ValidationError

from crewai.process import Process
from crewai.tasks.task_output import TaskOutput

from aiservice.app.config.logging_config import get_logger
from aiservice.app.agents.content_rewrite_agents import ContentRewriteAgents
from aiservice.app.config.settings import Settings

from aiservice.app.models.orchestration_models import ContentBlock, OrchestrationStatusCodeEnum
from aiservice.app.models.insight_generation_models import RewriteContentInput, RewriteContentOutput
from aiservice.app.models.task_output_models import SummarizerTaskOutput, StructuredSummary, Segment
from aiservice.app.services.task_db_service import update_task_progress_stage

logger = get_logger(__name__)

class ContentRewriteCrewManager:
    """Manages the creation and execution of the Content Rewrite Crew."""

    def __init__(self,
                 rewrite_input: RewriteContentInput,
                 task_id: Optional[str] = None,
                 db_connection: Optional[Any] = None,
                 verbose_level: int = 0):
        """
        Initializes the crew manager with the necessary input data.
        Args:
            rewrite_input: The input data containing content_blocks and optional metadata.
            task_id: The ID of the current task, for progress updates.
            db_connection: Active database connection for progress updates.
            verbose_level: Integer to control verbosity of logs. 0 = minimal.
        """
        self.rewrite_input = rewrite_input
        self.task_id = task_id
        self.db_connection = db_connection
        self.verbose_level = verbose_level
        
        # Determine user_id for the rewrite operation (self.user_id_for_rewrite)
        self.user_id_for_rewrite = "default_user_id_rewrite_op" # Default
        if self.rewrite_input.user_id:
            self.user_id_for_rewrite = self.rewrite_input.user_id
        elif self.rewrite_input.document_metadata and self.rewrite_input.document_metadata.user_id:
            self.user_id_for_rewrite = self.rewrite_input.document_metadata.user_id
        
        # Determine the original document_id if available (for logging/reference, not for new blocks)
        self.original_document_id = "original_doc_id_not_found" # Default
        if self.rewrite_input.document_metadata and self.rewrite_input.document_metadata.document_id:
            self.original_document_id = self.rewrite_input.document_metadata.document_id

        # Generate a new unique document_id for the rewritten content blocks
        self.new_rewritten_document_id = str(uuid.uuid4())

        print(f"INFO: ContentRewriteCrewManager initialized. User ID for rewrite: {self.user_id_for_rewrite}, Original Document ID: {self.original_document_id}, New Rewritten Document ID: {self.new_rewritten_document_id}")
        
        # Pass user_id_for_rewrite and new_rewritten_document_id to ContentRewriteAgents
        self.agents_factory = ContentRewriteAgents(
            user_id=self.user_id_for_rewrite,
            document_id_for_output_blocks=self.new_rewritten_document_id
        )
        self.crew: Optional[Crew] = None

    def setup_crew(self) -> Crew:
        """
        Defines and configures the Content Rewrite Crew, its agents, and tasks.
        This method sets up the crew structure, and the actual data is passed during kickoff.
        """
        # Get agents
        summarization_agent = self.agents_factory.summarization_agent()
        # output_constructor_agent = self.agents_factory.output_constructor_agent() # REMOVED

        # Define Tasks
        # Note: CrewAI's {{variable_name}} syntax will be used in descriptions for kickoff inputs.
        # Constants like temperature are embedded directly using f-string from agents_factory.
        task_summarize_content = Task(
            description=dedent(f"""\
                ## Persona & Overall Objective:
                You are an AI Detailed Content Analysis and High-Fidelity Summarization Specialist. Your primary goal is to analyze the provided 'concatenated_text' and 'essential_image_metadata'. You will generate a single, clean JSON string that represents a 'StructuredSummary'. This summary MUST begin with a specifically formatted TL;DR section. The remainder of the summary should be a detailed, high-fidelity synthesis of the source text, ensuring at least 90% overall information retention and contextual integration of crucial image references.

                ## Input Data:
                1.  **'concatenated_text'**: The primary text content to summarize.
                    ```
                    {{{{concatenated_text}}}}
                    ```
                2.  **'essential_image_metadata_for_summarizer_prompt'**: A JSON string list of image metadata. You will use 'image_id_ref' (or 'gcs_url' as a fallback) from this list for "image_reference" segments.
                    ```
                    {{{{essential_image_metadata_for_summarizer_prompt}}}}
                    ```

                ## Core Task: Hybrid Structured Summarization:

                **Part 1: Generate the Structured TL;DR Segment (First Segment)**
                1.  This TL;DR segment MUST be the very first segment in the output "segments" list.
                2.  It MUST be a JSON object with `"type": "text"`.
                3.  The "content" string for this segment MUST start exactly with "**TL;DR**".
                4.  Immediately following "**TL;DR**", provide exactly four bullet points using '\n' for line breaks. Each bullet point must be concise and derived from the 'concatenated_text':
                    * `\n• **What:** [Concise description of the main topic, event, or announcement]`
                    * `\n• **Why:** [Concise explanation of its importance, the problem it addresses, or the reason it occurred]`
                    * `\n• **Key numbers:** [List 1-3 critical quantifiable data points, statistics, or significant figures. If no explicit numbers are central, identify the most critical factual takeaways that can be presented concisely.]`
                    * `\n• **Impact:** [Concise summary of the primary outcome, benefit, significance, or consequence]`
                5.  Example "content" for the TL;DR segment:
                    `"**TL;DR**\n• **What:** Introduction of the new 'Helios' solar energy panel.\n• **Why:** To provide a more efficient and affordable renewable energy source for residential use.\n• **Key numbers:** 25% higher energy conversion, 15-year extended warranty, costs $0.80/watt.\n• **Impact:** Aims to accelerate solar adoption and reduce household carbon footprints."`

                **Part 2: Generate the Main Body Summary Segments (Following TL;DR)**
                1.  After the initial TL;DR segment, continue constructing the summary with a series of "text" and "image_reference" segments.
                2.  **High-Fidelity Summarization:**
                    * Thoroughly summarize the remaining important information from the 'concatenated_text'.
                    * The combined summary (TL;DR + Main Body) MUST achieve at least 90% information retention from the original source. Preserve key facts, figures, arguments, conclusions, and the core narrative flow.
                    * Focus on accuracy, clarity, coherence, and providing a comprehensive understanding.
                3.  **Image Integration:**
                    * Identify CRUCIAL images from 'essential_image_metadata_for_summarizer_prompt'. An image is CRUCIAL if its 'caption', 'alt_text', or 'llm_description' indicates it provides significant visual support for key points in the text (e.g., diagrams, charts, important illustrations).
                    * Integrate "image_reference" segments for these CRUCIAL images.
                    * Place these references contextually where they are most relevant within the flow of the summarized text segments in this main body. Ensure a natural flow between text and image references.
                4.  **Text Segmentation for Main Body:**
                    * Structure the main body summary into logical "text" segments. A new segment might start for a new topic, a detailed explanation, or following an image reference.
                    * There are no strict length constraints (like ≤ 2 sentences or ≈ 120 characters) for these main body text segments. Prioritize conveying information clearly and comprehensively.
                    * Avoid overly long monolithic text blocks; break content into digestible paragraphs or sections as appropriate for readability.

                ## JSON Output Structure Specification (Reminder):
                Your entire output MUST be a single JSON object. This JSON object MUST have one top-level key: "segments".
                The value of "segments" MUST be a list of JSON objects.
                Each object in the "segments" list MUST have:
                  1. A "type" field: a string, either "text" or "image_reference".
                  2. EITHER a "content" field (if type is "text"): a string containing that part of the summarized text.
                  3. OR an "image_id_ref" field (if type is "image_reference"): a string, using the 'image_id_ref' (or 'gcs_url' as fallback) from the 'essential_image_metadata' for CRUCIAL images.

                ### Example JSON Output (Illustrating Hybrid Structure):
                ```json
                {{
                  "segments": [
                    {{
                      "type": "text",
                      "content": "**TL;DR**\n• **What:** Launch of the 'Nova' AI research platform.\n• **Why:** To accelerate breakthroughs in machine learning model development.\n• **Key numbers:** Supports 1000+ users, 5 PetaFLOPS processing power.\n• **Impact:** Empowers researchers with enhanced computational tools and collaborative features."
                    }},
                    {{
                      "type": "text",
                      "content": "The 'Nova' AI research platform represents a significant step forward in providing accessible high-performance computing for the AI community. It addresses the growing need for powerful tools to train increasingly complex models."
                    }},
                    {{
                      "type": "text",
                      "content": "Key architectural components of the 'Nova' platform are detailed in the diagram below, showcasing its distributed processing capabilities and data handling mechanisms."
                    }},
                    {{
                      "type": "image_reference",
                      "image_id_ref": "nova_architecture_diagram_v2"
                    }},
                    {{
                      "type": "text",
                      "content": "Early adoption programs have shown promising results, with research teams reporting up to a 60% reduction in model training times for specific benchmarks. The platform also includes integrated tools for data versioning and experiment tracking, further streamlining the research workflow."
                    }}
                    // ... more text and image_reference segments as needed for 90% fidelity ...
                  ]
                }}
                ```
                
                ### Tool Usage:
                - You MUST use your 'Optimized LLM Interaction Tool' for this task.
                - Set 'temperature' to {self.agents_factory.summarizer_temperature} and 'max_tokens' to {self.agents_factory.summarizer_max_tokens}. Ensure your response respects the 'max_tokens' limit while fulfilling all requirements, especially information retention.

                ### CRITICAL Final Output Instruction:
                Your final raw output for this task MUST be ONLY the JSON string itself, conforming to the structure specified above. Do NOT include any explanatory text, markdown formatting (like ```json), or any characters whatsoever outside of the single, valid JSON object. The output must start with {{ and end with }}.
                The system will directly parse this JSON string into the 'StructuredSummary' Pydantic model.
                """),
            expected_output=(
                "A single, valid JSON string representing a structured summary. This JSON string must conform to the specified structure: "
                "an object with a 'segments' key, where 'segments' is a list of objects, each having 'type' and either 'content' or 'image_id_ref'. "
                "This JSON string will be used to populate the 'structured_summary' field of the 'SummarizerTaskOutput' Pydantic model."
            ),
            agent=summarization_agent,
            context_data_from_main_crew_inputs = ['concatenated_text', 'essential_image_metadata_for_summarizer_prompt']
        )

        # task_reconstruct_output REMOVED

        content_rewrite_crew = Crew(
            agents=[summarization_agent], # Only summarization_agent
            tasks=[task_summarize_content],  # Only task_summarize_content
            process=Process.sequential,
            verbose=True, 
        )
        return content_rewrite_crew

    def _clean_json_string(self, raw_output: Optional[str]) -> Optional[str]:
        """
        Cleans the raw LLM output to extract a valid JSON string.
        Handles markdown code blocks (triple and single backticks) and attempts to find a JSON object.
        Returns the cleaned JSON string or None if no valid JSON object is found.
        """
        if not raw_output:
            return None
        
        # Pattern to find JSON within ```json ... ``` or ``` ... ```
        # It also handles cases where 'json' might be missing after ```
        # DOTALL allows . to match newlines, MULTILINE is not needed here as we search the whole string
        match_triple = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
        if match_triple:
            return match_triple.group(1).strip()

        # Pattern to find JSON within ` ... ` (single backticks)
        match_single = re.search(r"`(\{.*\})`", raw_output, re.DOTALL)
        if match_single:
            return match_single.group(1).strip()
        
        # If the raw output itself looks like a JSON object (e.g. agent returned only JSON)
        # This is a fallback and might be too greedy if the string contains {} but isn't valid JSON.
        stripped_output = raw_output.strip()
        if stripped_output.startswith("{") and stripped_output.endswith("}"):
            try:
                # Validate if it's actually parseable JSON
                json.loads(stripped_output)
                return stripped_output
            except json.JSONDecodeError:
                # It looked like a JSON object but wasn't valid.
                logger.debug(f"_clean_json_string: Stripped output '{stripped_output[:100]}...' looked like JSON but failed to parse.")
                pass # Fall through to return None or let other patterns try

        logger.warning(f"_clean_json_string: Could not extract JSON object from raw_output using common patterns. Raw output (first 200 chars): {raw_output[:200]}")
        return None # Return None if no JSON object is reliably extracted

    def safe_parse_to_content_blocks(self, data: Any, field_name: str) -> List[ContentBlock]:
        parsed_blocks: List[ContentBlock] = []
        if not isinstance(data, list):
            print(f"ERROR: Data for '{field_name}' is not a list, but type {type(data)}. Cannot parse into ContentBlocks.") # Retained
            return []

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                print(f"ERROR: Item {i} in '{field_name}' is not a dictionary, but type {type(item)}. Skipping.") # Retained
                continue
            try:
                if 'block_id' not in item or item['block_id'] is None:
                    item['block_id'] = str(uuid.uuid4())
                
                if 'type' not in item or item['type'] is None:
                    if 'content' in item and isinstance(item['content'], str):
                         item['type'] = 'text'
                    else:
                        print(f"WARNING: Item {i} in '{field_name}' is missing 'type' and cannot infer. Skipping. Item: {str(item)[:100]}") # Retained
                        continue

                block = ContentBlock(**item)
                parsed_blocks.append(block)
            except Exception as e:
                print(f"ERROR: Failed to validate item {i} in '{field_name}' as ContentBlock. Error: {e}. Item: {str(item)[:200]}") # Retained
        
        if data and not parsed_blocks:
             print(f"WARNING: Input data for '{field_name}' was non-empty but resulted in zero successfully parsed ContentBlocks.") # Retained
        elif not data:
             pass

        return parsed_blocks

    def run(self) -> RewriteContentOutput:
        start_time = time.time()
        logger.info(f"ContentRewriteCrewManager run initiated. User ID: {self.user_id_for_rewrite}, Rewritten Document ID: {self.new_rewritten_document_id}")

        parsed_content_blocks: List[ContentBlock] = []
        usage_metrics_dict: Optional[Dict[str, Any]] = None
        final_status_code: OrchestrationStatusCodeEnum = OrchestrationStatusCodeEnum.ERROR_UNKNOWN
        final_error_message: Optional[str] = "Rewrite process did not complete successfully."

        # Helper for progress updates
        def _update_progress(stage_message: str):
            if self.task_id and self.db_connection:
                try:
                    update_task_progress_stage(self.task_id, stage_message, self.db_connection)
                    logger.info(f"[Task {self.task_id}] Progress updated to: {stage_message}")
                except Exception as e:
                    logger.error(f"[Task {self.task_id}] Failed to update progress stage to '{stage_message}': {e}")
            else:
                logger.debug(f"Skipping progress update (task_id or db_connection not set): {stage_message}")

        _update_progress("Preparing content...")

        # 1. Pre-process input
        concatenated_text = ""
        essential_image_metadata: List[Dict[str, Any]] = []
        text_parts = []
        for block in self.rewrite_input.content_blocks_to_rewrite:
            if block.type == "text" and block.content:
                text_parts.append(block.content)
            elif block.type == "image" and block.image_id_ref:
                normalized_gcs_url = block.gcs_url.replace("\\\\", "/") if block.gcs_url else None
                essential_meta = {
                    "image_id_ref": block.image_id_ref,
                    "gcs_url": normalized_gcs_url,
                    "alt_text": block.alt_text,
                    "caption": block.caption,
                    "llm_description": block.llm_description,
                    "width": block.width,
                    "height": block.height
                }
                essential_image_metadata.append({k: v for k, v in essential_meta.items() if v is not None})
        concatenated_text = "\n\n".join(text_parts)
        
        essential_image_metadata_json = json.dumps(essential_image_metadata)

        logger.info(f"ContentRewriteCrewManager: Populated essential_image_metadata for reconstruction tool: {essential_image_metadata_json[:200]}...")

        # 2. Setup the crew
        self.crew = self.setup_crew()

        # 3. Prepare inputs for the crew's summarization task
        crew_kickoff_inputs = {
            'concatenated_text': concatenated_text,
            'essential_image_metadata_for_summarizer_prompt': essential_image_metadata_json 
        }
        
        _update_progress("Summarizing content with AI...")

        if self.verbose_level > 1:
            logger.debug(f"Kicking off crew with inputs (metadata potentially truncated for log):")
            logger.debug(f"  concatenated_text length: {len(crew_kickoff_inputs['concatenated_text'])}")
            logger.debug(f"  essential_image_metadata_for_summarizer_prompt: {crew_kickoff_inputs['essential_image_metadata_for_summarizer_prompt'][:200] if crew_kickoff_inputs['essential_image_metadata_for_summarizer_prompt'] else '[]'}...")

        crew_result_raw: Any = None
        summarizer_output_obj: Optional[SummarizerTaskOutput] = None
        
        try:
            # 4. Kick off the crew execution (only summarization task now)
            crew_result_raw = self.crew.kickoff(inputs=crew_kickoff_inputs)

            # 5. Process usage metrics
            if crew_result_raw and hasattr(self.crew, 'usage_metrics') and self.crew.usage_metrics:
                um = self.crew.usage_metrics
                temp_metrics_dict = {}
                known_attrs = ['total_tokens', 'prompt_tokens', 'completion_tokens', 'successful_requests']
                for attr in known_attrs:
                    if hasattr(um, attr): temp_metrics_dict[attr] = getattr(um, attr)
                
                if isinstance(um, dict): usage_metrics_dict = {**um, **temp_metrics_dict}
                elif temp_metrics_dict: usage_metrics_dict = temp_metrics_dict
                else:
                    try: usage_metrics_dict = vars(um)
                    except TypeError: logger.error(f"vars(um) failed for type {type(um)}. usage_metrics will be None.")
                
                if not isinstance(usage_metrics_dict, dict) and usage_metrics_dict is not None:
                    logger.critical(f"usage_metrics_dict is NOT a dict after conversion. Type: {type(usage_metrics_dict)}. Setting to None.")
                    usage_metrics_dict = None

            # 6. Process summarization output
            raw_json_from_llm_for_segments = None
            parsed_structured_summary_model: Optional[StructuredSummary] = None

            if crew_result_raw:
                task_outputs = getattr(crew_result_raw, 'tasks_output', None)
                if task_outputs and isinstance(task_outputs, list) and task_outputs:
                    last_task_output = task_outputs[-1] # This is a TaskOutput object

                    # Path 1: Ideal - CrewAI's Pydantic parser worked as expected for the task
                    if hasattr(last_task_output, 'exported_output') and isinstance(last_task_output.exported_output, StructuredSummary):
                        parsed_structured_summary_model = last_task_output.exported_output
                        # Try to get the original raw string from the agent that led to this parsed model
                        raw_json_from_llm_for_segments = getattr(last_task_output, 'raw', None)
                        if not raw_json_from_llm_for_segments and parsed_structured_summary_model: # Fallback if .raw is not available
                            raw_json_from_llm_for_segments = parsed_structured_summary_model.model_dump_json() # Re-serialize
                        logger.info("Extracted StructuredSummary from last_task_output.exported_output.")
                    
                    # Path 2: CrewAI's Pydantic parser for the task didn't populate exported_output as StructuredSummary (e.g., it's None).
                    # So, we attempt to parse from last_task_output.raw manually.
                    elif hasattr(last_task_output, 'raw') and isinstance(last_task_output.raw, str):
                        agent_raw_output_for_task = last_task_output.raw
                        logger.info(
                            f"last_task_output.exported_output was None or not a StructuredSummary "
                            f"(type: {type(getattr(last_task_output, 'exported_output', None))}). "
                            f"Attempting to parse from last_task_output.raw: {agent_raw_output_for_task[:200]}..."
                        )
                        try:
                            cleaned_json_str = self._clean_json_string(agent_raw_output_for_task)
                            if cleaned_json_str:
                                parsed_data = json.loads(cleaned_json_str)
                                parsed_structured_summary_model = StructuredSummary(**parsed_data)
                                # Store the original agent's raw output for this task for transparency,
                                # even if it included markdown, as it's what we processed.
                                raw_json_from_llm_for_segments = agent_raw_output_for_task 
                                logger.info(f"Successfully parsed StructuredSummary from cleaned last_task_output.raw. Cleaned JSON preview: {cleaned_json_str[:100]}...")
                            else:
                                logger.error(f"Cleaning last_task_output.raw resulted in an empty or None string. Original raw: {agent_raw_output_for_task[:200]}...")
                        except (json.JSONDecodeError, ValidationError) as e:
                            # Log the cleaned string attempt if available, otherwise the original raw for context
                            cleaned_attempt_preview = "N/A"
                            if 'cleaned_json_str' in locals() and cleaned_json_str: # Check if cleaned_json_str was defined
                                cleaned_attempt_preview = cleaned_json_str[:100]
                            elif agent_raw_output_for_task: # Fallback to previewing the result of cleaning the raw output directly
                                 cleaned_attempt_preview = (self._clean_json_string(agent_raw_output_for_task) or "None after cleaning")[:100]

                            logger.error(
                                f"Failed to parse StructuredSummary from cleaned last_task_output.raw. Error: {e}. "
                                f"Cleaned JSON attempt preview: {cleaned_attempt_preview}. "
                                f"Original raw content for task: {agent_raw_output_for_task[:200]}..."
                            )
                        except Exception as e: # Catch any other unexpected error during cleaning/parsing
                            logger.error(f"Unexpected error processing last_task_output.raw: {e}. Original raw content for task: {agent_raw_output_for_task[:200]}...")
                    else: # This case means last_task_output.raw was not a string or not present.
                        logger.warning(
                            "last_task_output.exported_output was not StructuredSummary, and last_task_output.raw "
                            f"is not available or not a string. last_task_output.raw type: {type(getattr(last_task_output, 'raw', None))}"
                        )
                
                # Path 3: Fallback if tasks_output is not available/helpful, or if parsing above failed.
                # Try to parse from crew_result_raw.raw (this is the raw output of the entire crew execution).
                # This is less direct, as crew_result_raw.raw can be verbose.
                if not parsed_structured_summary_model and hasattr(crew_result_raw, 'raw') and isinstance(crew_result_raw.raw, str):
                    entire_crew_raw_output = crew_result_raw.raw
                    logger.info(f"Could not get StructuredSummary from task_outputs. Attempting to parse from crew_result_raw.raw: {entire_crew_raw_output[:200]}...")
                    try:
                        cleaned_json_str = self._clean_json_string(entire_crew_raw_output)
                        if cleaned_json_str:
                            # The _clean_json_string should ideally find the JSON from the "Final Answer" if present in the log
                            parsed_data = json.loads(cleaned_json_str)
                            parsed_structured_summary_model = StructuredSummary(**parsed_data)
                            # If we parsed from the entire crew's raw output, the cleaned_json_str is the best "raw JSON" we have.
                            raw_json_from_llm_for_segments = cleaned_json_str 
                            logger.info(f"Successfully parsed StructuredSummary from cleaned crew_result_raw.raw. Cleaned JSON preview: {cleaned_json_str[:100]}...")
                        else:
                            logger.error(f"Cleaning crew_result_raw.raw resulted in an empty or None string. Original crew raw: {entire_crew_raw_output[:200]}...")
                    except (json.JSONDecodeError, ValidationError) as e:
                        cleaned_attempt_preview = "N/A"
                        if 'cleaned_json_str' in locals() and cleaned_json_str:
                            cleaned_attempt_preview = cleaned_json_str[:100]
                        elif entire_crew_raw_output:
                             cleaned_attempt_preview = (self._clean_json_string(entire_crew_raw_output) or "None after cleaning")[:100]
                        logger.error(
                            f"Failed to parse StructuredSummary from cleaned crew_result_raw.raw. Error: {e}. "
                            f"Cleaned JSON attempt preview: {cleaned_attempt_preview}. "
                            f"Original crew_result_raw.raw content: {entire_crew_raw_output[:200]}..."
                        )
                    except Exception as e:
                            logger.error(f"Unexpected error processing crew_result_raw.raw: {e}. Original crew_result_raw.raw content: {entire_crew_raw_output[:200]}...")
                
                # Path 4: Check crew_result_raw.pydantic_output (if crew itself has pydantic_output defined, which it doesn't here but good for robustness)
                if not parsed_structured_summary_model and hasattr(crew_result_raw, 'pydantic_output') and isinstance(crew_result_raw.pydantic_output, StructuredSummary):
                    parsed_structured_summary_model = crew_result_raw.pydantic_output
                    raw_json_from_llm_for_segments = parsed_structured_summary_model.model_dump_json() # Re-serialize as best guess for raw
                    logger.info("Extracted StructuredSummary from crew_result_raw.pydantic_output.")

                # Final check and return logic
                if parsed_structured_summary_model and raw_json_from_llm_for_segments is not None:
                    summarizer_output_obj = SummarizerTaskOutput(
                        structured_summary=parsed_structured_summary_model,
                        raw_llm_output_json=raw_json_from_llm_for_segments
                    )
                    logger.info(f"Summarization successful. Number of segments: {len(summarizer_output_obj.structured_summary.segments)}")

                    _update_progress("Reconstructing content from summary...")

                    # 7. Call FastContentBlockProcessorTool directly for reconstruction
                    reconstruction_tool = self.agents_factory.content_processor_tool # Get the instance directly
                    
                    logger.info(f"Calling FastContentBlockProcessorTool with structured_summary_input, image_metadata_list_json: {essential_image_metadata_json[:200]}..., and document_id: {self.new_rewritten_document_id}")
                    
                    reconstructed_block_dicts: List[Dict] = reconstruction_tool._run(
                        operation="reconstruct_content_from_summary",
                        structured_summary_input=summarizer_output_obj.structured_summary, # Pass Pydantic model
                        image_metadata_list_json=essential_image_metadata_json,
                        document_id=self.new_rewritten_document_id
                    )

                    if isinstance(reconstructed_block_dicts, list) and reconstructed_block_dicts and isinstance(reconstructed_block_dicts[0], dict) and "error" in reconstructed_block_dicts[0]:
                        tool_error_msg = reconstructed_block_dicts[0]["error"]
                        final_status_code = OrchestrationStatusCodeEnum.ERROR_CONTENT_BLOCK_VALIDATION # Or a new specific code
                        final_error_message = f"FastContentBlockProcessorTool failed during reconstruction: {tool_error_msg}"
                        logger.error(final_error_message)
                    elif not isinstance(reconstructed_block_dicts, list):
                        final_status_code = OrchestrationStatusCodeEnum.ERROR_UNEXPECTED_OUTPUT_TYPE
                        final_error_message = f"FastContentBlockProcessorTool returned unexpected type: {type(reconstructed_block_dicts)}. Expected List[Dict]."
                        logger.error(final_error_message)
                    else:
                        parsed_content_blocks = self.safe_parse_to_content_blocks(reconstructed_block_dicts, "ai_rewritten_content_blocks (from_tool)")
                        if not parsed_content_blocks and reconstructed_block_dicts: # Non-empty list from tool, but parsing failed
                            final_status_code = OrchestrationStatusCodeEnum.ERROR_CONTENT_BLOCK_VALIDATION
                            final_error_message = "FastContentBlockProcessorTool output was a list of dicts, but failed Pydantic validation into ContentBlocks."
                            logger.error(f"{final_error_message} Tool output (first item): {str(reconstructed_block_dicts[0])[:500] if reconstructed_block_dicts else 'Empty List'}")
                        elif parsed_content_blocks or not reconstructed_block_dicts: # Successfully parsed or empty list output
                            final_status_code = OrchestrationStatusCodeEnum.SUCCESS
                            final_error_message = None
                            logger.info(f"Successfully reconstructed and parsed {len(parsed_content_blocks)} content blocks.")
                        else: # Should not happen if above logic is correct
                            final_status_code = OrchestrationStatusCodeEnum.ERROR_UNKNOWN
                            final_error_message = "Unknown error after attempting to parse reconstructed blocks from tool."
                            logger.error(final_error_message)
                else: # ADDED: Handle case where summarization output processing failed
                    _update_progress("Failed to process summarization output.") # Update progress before error
                    final_status_code = OrchestrationStatusCodeEnum.ERROR_UNEXPECTED_OUTPUT_TYPE
                    final_error_message = "Failed to process or parse valid structured summary from LLM output after all attempts."
                    logger.error(f"{final_error_message} parsed_structured_summary_model is None or raw_json_from_llm_for_segments is None.")
                    # parsed_content_blocks will remain empty, and usage_metrics might still be available from crew.kickoff

        except Exception as e:
            _update_progress("Error during rewrite process.") # Update progress on generic exception
            final_status_code = OrchestrationStatusCodeEnum.ERROR_CREW_EXECUTION_FAILED
            final_error_message = f"An exception occurred during crew kickoff or direct tool call: {str(e)}"
            logger.critical(f"Crew/Tool execution failed: {final_error_message}", exc_info=True)
            # Attempt to capture usage metrics if available
            if self.crew and hasattr(self.crew, 'usage_metrics') and self.crew.usage_metrics:
                try:
                    usage_metrics_dict = self.crew.usage_metrics if isinstance(self.crew.usage_metrics, dict) else vars(self.crew.usage_metrics)
                except: # Be very defensive here
                    logger.error("Failed to capture usage_metrics during exception handling.")


        end_time = time.time()
        processing_time_ms = (end_time - start_time) * 1000
        status_value = final_status_code.value if isinstance(final_status_code, OrchestrationStatusCodeEnum) else str(final_status_code)
        logger.info(f"ContentRewriteCrewManager run finished in {processing_time_ms/1000:.2f} seconds. Status: {status_value}")

        return RewriteContentOutput(
            ai_rewritten_content_blocks=parsed_content_blocks,
            status_code=status_value,
            error_message=final_error_message,
            usage_metrics=usage_metrics_dict,
            processing_time_ms=processing_time_ms,
            trace_id=None # TODO: Implement trace_id propagation if needed
        )

# Example Usage (for direct testing if needed)
if __name__ == "__main__":
    # Ensure necessary model imports for example are within __main__ or globally accessible if run directly
    from aiservice.app.models.pipeline_models import DocumentMetadata # For sample data
    import datetime

    print("Setting up sample data for ContentRewriteCrewManager...")
    sample_doc_metadata = DocumentMetadata(
        document_id="sample_doc_123",
        source_identifier="internal_sample",
        source_type="text",
        extracted_at=datetime.datetime.utcnow(),
        user_id="test_user_123" # Added user_id for testing the init logic
    )
    sample_content_blocks = [
        ContentBlock(block_id="cb1", type="text", content="This is the first paragraph of a document we want to summarize. It has some interesting points."),
        ContentBlock(block_id="cb2", type="image", image_id_ref="img1", gcs_url="gs://example/image1.jpg", alt_text="An illustrative image"),
        ContentBlock(block_id="cb3", type="text", content="The second paragraph elaborates further, providing more details and context. We hope the summary captures this."),
        # ContentBlock(block_id="cb4", type="list", items=["Point one", "Point two", "Point three"], ordered=False) # Removed list type as it's not handled by summarizer text part
    ]

    rewrite_input_data = RewriteContentInput(
        content_blocks_to_rewrite=sample_content_blocks,
        document_metadata=sample_doc_metadata
        # user_id="test_user_direct" # Alternative way to pass user_id
    )

    print("Initializing ContentRewriteCrewManager...")
    # Pass verbose_level if you want more debug prints from the manager itself
    crew_manager = ContentRewriteCrewManager(rewrite_input=rewrite_input_data, verbose_level=2)

    print("Running ContentRewriteCrew...")
    # Note: Running this will make actual LLM calls if GEMINI_API_KEY is set and valid.
    # Ensure your .env and settings are configured.
    output = crew_manager.run()

    print("\n--- Crew Output ---")
    if output.status_code == OrchestrationStatusCodeEnum.SUCCESS.value: # Compare with Enum value
        print("Rewrite successful!")
        for i, block in enumerate(output.ai_rewritten_content_blocks):
            print(f"Block {i+1} (Type: {block.type}, ID: {block.block_id}):")
            if block.type == "text":
                print(f"  Content: {block.content}")
            elif block.type == "image":
                print(f"  Image GCS URL: {block.gcs_url}")
                print(f"  Image ID Ref: {block.image_id_ref}")
                print(f"  Alt Text: {block.alt_text}")
            # Add more types as needed
    else:
        print(f"Rewrite failed. Status: {output.status_code}")
        print(f"Error: {output.error_message}")

    print("\n--- Crew Execution Metrics ---")
    if output.usage_metrics:
        print(f"Usage Metrics: {output.usage_metrics}")
    else:
        print("Usage Metrics: N/A")
    print(f"Processing Time: {output.processing_time_ms} ms") 