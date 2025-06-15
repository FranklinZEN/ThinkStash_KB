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
from aiservice.app.services.task_db_service import update_task_progress_stage, update_task_status_completed, update_task_status_failed

logger = get_logger(__name__)

class ContentRewriteCrewManager:
    """Manages the creation and execution of the Content Rewrite Crew."""

    def __init__(self,
                 rewrite_input: RewriteContentInput,
                 task_id: Optional[str] = None,
                 db_connection: Optional[Any] = None,
                 verbose_level: int = 0,
                 correlation_id: Optional[str] = None):
        """
        Initializes the crew manager with the necessary input data.
        Args:
            rewrite_input: The input data containing content_blocks and optional metadata.
            task_id: The ID of the current task, for progress updates.
            db_connection: Active database connection for progress updates.
            verbose_level: Integer to control verbosity of logs. 0 = minimal.
            correlation_id: Optional correlation ID for end-to-end request tracing.
        """
        self.rewrite_input = rewrite_input
        self.task_id = task_id if task_id else str(uuid.uuid4())
        self.db_connection = db_connection
        self.verbose_level = verbose_level
        self.correlation_id = correlation_id
        
        self.user_id_for_rewrite = "default_user_id_rewrite_op"
        if self.rewrite_input.user_id:
            self.user_id_for_rewrite = self.rewrite_input.user_id
        elif self.rewrite_input.document_metadata and self.rewrite_input.document_metadata.user_id:
            self.user_id_for_rewrite = self.rewrite_input.document_metadata.user_id
        
        self.original_document_id = "original_doc_id_not_found"
        if self.rewrite_input.document_metadata and self.rewrite_input.document_metadata.document_id:
            self.original_document_id = self.rewrite_input.document_metadata.document_id

        self.new_rewritten_document_id = str(uuid.uuid4())

        logger.info("ContentRewriteCrewManager initialized", extra={
            'task_id': self.task_id,
            'correlation_id': self.correlation_id,
            'user_id_for_rewrite': self.user_id_for_rewrite,
            'original_document_id': self.original_document_id,
            'new_rewritten_document_id': self.new_rewritten_document_id
        })
        
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
        Handles markdown code blocks and finds the main JSON object, ignoring leading/trailing text.
        Returns the cleaned JSON string or None if no valid JSON object is found.
        """
        if not raw_output:
            return None
        
        # Enhanced pattern to find JSON within ```json ... ``` or ``` ... ```, more resilient to variations
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_output, re.DOTALL)
        
        content_to_parse = raw_output
        if match:
            # If a markdown block is found, parse its content
            content_to_parse = match.group(1).strip()
        
        # Find the first '{' and the last '}' to isolate the main JSON object
        # This is effective against leading/trailing garbage text from the LLM
        start_brace_index = content_to_parse.find('{')
        end_brace_index = content_to_parse.rfind('}')
        
        if start_brace_index != -1 and end_brace_index > start_brace_index:
            json_str_candidate = content_to_parse[start_brace_index : end_brace_index + 1]
            try:
                # The final check: ensure the extracted string is valid JSON
                json.loads(json_str_candidate)
                return json_str_candidate
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Extracted string appeared to be a JSON object but failed validation.",
                    extra={
                        'task_id': self.task_id, 
                        'correlation_id': self.correlation_id,
                        'error': str(e),
                        'json_candidate': json_str_candidate[:500] # Log a preview of the invalid string
                    }
                )
                return None # Return None if parsing fails

        logger.warning(
            "Could not extract a valid JSON object from the raw output.",
            extra={
                'task_id': self.task_id,
                'correlation_id': self.correlation_id,
                'raw_output_preview': raw_output[:500]
            }
        )
        return None

    def safe_parse_to_content_blocks(self, data: Any, field_name: str) -> List[ContentBlock]:
        parsed_blocks: List[ContentBlock] = []
        if not isinstance(data, list):
            logger.error("Data for field is not a list, cannot parse into ContentBlocks.", extra={
                'task_id': self.task_id,
                'correlation_id': self.correlation_id,
                'field_name': field_name,
                'data_type': str(type(data))
            })
            return []

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                logger.error("Item in field is not a dictionary, skipping.", extra={
                    'task_id': self.task_id,
                    'correlation_id': self.correlation_id,
                    'field_name': field_name,
                    'item_index': i,
                    'item_type': str(type(item))
                })
                continue
            try:
                if 'block_id' not in item or item['block_id'] is None:
                    item['block_id'] = str(uuid.uuid4())
                
                if 'type' not in item or item['type'] is None:
                    if 'content' in item and isinstance(item['content'], str):
                         item['type'] = 'text'
                    else:
                        logger.warning("Content block item is missing 'type' and cannot be inferred to 'text'. Skipping.", extra={
                            'task_id': self.task_id,
                            'correlation_id': self.correlation_id,
                            'item_index': i,
                            'item_preview': str(item)[:200]
                        })
                        continue

                if item['type'] not in ['text', 'image', 'video', 'audio', 'file', 'embed', 'link', 'divider', 'heading', 'list_item', 'list']:
                    logger.error("Content block item has an unrecognized 'type'.", extra={
                        'task_id': self.task_id,
                        'correlation_id': self.correlation_id,
                        'item_index': i,
                        'block_type': item.get('type'),
                        'item_preview': str(item)[:200]
                    })
                    continue 
                
                if item['type'] == 'image':
                    if 'image_url' not in item or not item['image_url']:
                         logger.warning("Image block is missing 'image_url'. Attempting to use 'gcs_url'.", extra={
                            'task_id': self.task_id,
                            'correlation_id': self.correlation_id,
                            'item_index': i,
                            'item_data': str(item)[:200]
                         })
                         if 'gcs_url' in item and item['gcs_url']:
                             item['image_url'] = item['gcs_url']
                         else:
                             logger.error("Image block is missing 'image_url' and 'gcs_url'. Skipping.", extra={
                                 'task_id': self.task_id,
                                 'correlation_id': self.correlation_id,
                                 'item_index': i,
                                 'item_data': str(item)[:200]
                             })
                             continue

                if 'document_id' not in item or item['document_id'] is None:
                    item['document_id'] = self.new_rewritten_document_id
                
                if 'user_id' not in item or item['user_id'] is None:
                    item['user_id'] = self.user_id_for_rewrite

                parsed_blocks.append(ContentBlock(**item))
            except ValidationError as e:
                logger.error("Pydantic validation error for item in field.", extra={
                    'task_id': self.task_id,
                    'correlation_id': self.correlation_id,
                    'field_name': field_name,
                    'item_index': i,
                    'validation_error': str(e),
                    'item_data': str(item)[:200]
                })
            except Exception as e_gen:
                logger.error("Generic error parsing item in field.", extra={
                    'task_id': self.task_id,
                    'correlation_id': self.correlation_id,
                    'field_name': field_name,
                    'item_index': i,
                    'error': str(e_gen),
                    'item_data': str(item)[:200]
                }, exc_info=True)
        return parsed_blocks

    async def run(self) -> RewriteContentOutput:
        start_time = time.time()
        current_trace_id = self.correlation_id if self.correlation_id else self.task_id

        def _update_progress(stage_message: str, status_code_enum_member: Optional[OrchestrationStatusCodeEnum] = None):
            logger.info(f"Progress: {stage_message}", extra={
                'task_id': self.task_id, 
                'correlation_id': self.correlation_id, 
                'stage': stage_message,
                'status_code': status_code_enum_member.value if status_code_enum_member else None
            })
            if self.task_id and self.db_connection and status_code_enum_member:
                try:
                    update_task_progress_stage(self.task_id, stage_message, self.db_connection)
                except Exception as e_db_progress:
                    logger.error("Failed to update task progress in DB.", extra={
                        'task_id': self.task_id,
                        'correlation_id': self.correlation_id,
                        'stage': stage_message,
                        'status_code_being_set': status_code_enum_member.value if status_code_enum_member else 'N/A',
                        'error': str(e_db_progress)
                    }, exc_info=True)

        logger.info("ContentRewriteCrewManager run method started.", extra={
            'task_id': self.task_id, 
            'correlation_id': self.correlation_id
        })
        _update_progress("Rewrite process initiated", OrchestrationStatusCodeEnum.REWRITE_STARTED)

        try:
            _update_progress("Preparing input for summarization agent", OrchestrationStatusCodeEnum.REWRITE_SUMMARIZATION_AGENT_STARTED)
            concatenated_text = ""
            if self.rewrite_input.content_blocks_to_rewrite:
                concatenated_text = "\n\n".join(
                    [block.content for block in self.rewrite_input.content_blocks_to_rewrite if block.type == "text" and block.content]
                )
            
            essential_image_metadata = []
            if self.rewrite_input.content_blocks_to_rewrite:
                for block in self.rewrite_input.content_blocks_to_rewrite:
                    if block.type == "image":
                        # Direct access to flat attributes on the ContentBlock model
                        essential_image_metadata.append({
                            "image_id_ref": block.image_id_ref or block.block_id,
                            "caption": block.caption,
                            "alt_text": block.alt_text,
                            "llm_description": block.llm_description,
                            "gcs_url": block.gcs_url
                        })
            
            if not concatenated_text and not essential_image_metadata:
                logger.warning("No text or image content to rewrite.", extra={
                    'task_id': self.task_id, 
                    'correlation_id': self.correlation_id
                })
                _update_progress("No content provided for rewrite", OrchestrationStatusCodeEnum.REWRITE_FAILED_EMPTY_INPUT)
                return RewriteContentOutput(
                    status_code=OrchestrationStatusCodeEnum.REWRITE_FAILED_EMPTY_INPUT.value,
                    error_message="AI rewrite failed: No text or image content was provided.",
                    ai_rewritten_content_blocks=[],
                    trace_id=current_trace_id
                )

            self.crew = self.setup_crew()
            logger.info("Content Rewrite Crew setup complete. Kicking off...", extra={
                'task_id': self.task_id, 
                'correlation_id': self.correlation_id
            })
            _update_progress("Summarization agent running", OrchestrationStatusCodeEnum.REWRITE_SUMMARIZATION_AGENT_PROCESSING)

            crew_inputs = {
                'concatenated_text': concatenated_text,
                'essential_image_metadata_for_summarizer_prompt': json.dumps(essential_image_metadata)
            }
            
            self.logger.info("ContentRewriteCrewManager: Kicking off crew...")

            # Execute the crew asynchronously
            crew_result = await self.crew.kickoff_async(inputs=crew_inputs)

            duration = time.time() - start_time
            self.logger.info(f"ContentRewriteCrewManager: Crew execution finished in {duration:.2f} seconds.")

            if not crew_result or not crew_result.tasks_output:
                logger.error("Crew kickoff returned empty or no task outputs.", extra={
                    'task_id': self.task_id, 
                    'correlation_id': self.correlation_id, 
                    'crew_result_raw': str(crew_result)[:500]
                })
                _update_progress("Summarization agent failed to produce output", OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_AGENT_ERROR)
                return RewriteContentOutput(
                    status_code=OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_AGENT_ERROR.value,
                    error_message="AI rewrite failed: The summarization agent did not produce any output.",
                    ai_rewritten_content_blocks=[],
                    trace_id=current_trace_id
                )

            logger.info(f"Crew kickoff completed. Number of task outputs: {len(crew_result.tasks_output)}", extra={
                'task_id': self.task_id, 
                'correlation_id': self.correlation_id
            })
            _update_progress("Summarization agent finished, processing output", OrchestrationStatusCodeEnum.REWRITE_SUMMARIZATION_AGENT_COMPLETED)

            summarizer_task_output: Optional[TaskOutput] = None
            for task_out in crew_result.tasks_output:
                # Check agent name or a unique characteristic of the summarizer task's output/description
                if hasattr(task_out, 'agent') and "Summarization Specialist" in str(task_out.agent):
                     summarizer_task_output = task_out
                     break
                elif hasattr(task_out, 'description') and "Detailed Content Analysis and High-Fidelity Summarization Specialist" in task_out.description:
                     summarizer_task_output = task_out
                     break
            
            if not summarizer_task_output:
                logger.error("Could not find Summarization Specialist's output in crew results.", extra={
                    'task_id': self.task_id, 
                    'correlation_id': self.correlation_id, 
                    'crew_task_outputs_summary': [str(t)[:100] for t in crew_result.tasks_output] # Log summary of outputs
                })
                _update_progress("Summarization agent output not found", OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_AGENT_ERROR)
                return RewriteContentOutput(
                    status_code=OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_AGENT_ERROR.value,
                    error_message="AI rewrite failed: The output from the summarization agent could not be found.",
                    ai_rewritten_content_blocks=[],
                    trace_id=current_trace_id
                )

            # For debugging: log the raw output from the summarizer task
            if summarizer_task_output:
                logger.debug("Raw output from summarizer_task_output", extra={
                    'task_id': self.task_id, 
                    'correlation_id': self.correlation_id,
                    'summarizer_output_str': str(summarizer_task_output)[:1000] # Log first 1000 chars
                })
                
                log_extras = {'task_id': self.task_id, 'correlation_id': self.correlation_id}

                try:
                    # The 'raw' output from the task is the JSON string we need.
                    raw_output_str = summarizer_task_output.raw
                    
                    # Clean the string to remove markdown and other text outside the JSON object.
                    cleaned_json_str = self._clean_json_string(raw_output_str)
                    if not cleaned_json_str:
                        # Raise a specific error if cleaning results in an empty string
                        raise ValueError("After cleaning, the summarizer agent's output was empty or contained no valid JSON.")

                    # The agent's output is the 'StructuredSummary' itself, not a wrapper object.
                    # We validate the cleaned JSON string directly into the StructuredSummary model.
                    structured_summary_from_llm = StructuredSummary.model_validate_json(cleaned_json_str)

                    logger.info("Successfully parsed and validated agent output into StructuredSummary.", extra=log_extras)

                except (ValidationError, json.JSONDecodeError, AttributeError, ValueError) as e:
                    logger.error(
                        "Failed to validate or parse agent output into StructuredSummary.",
                        extra={
                            **log_extras, 
                            'error': str(e),
                            'cleaned_json_string_that_failed': cleaned_json_str,
                            'raw_agent_output': raw_output_str,
                        },
                        exc_info=True
                    )
                    _update_progress("Failed to parse summarizer output (validation)", OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_OUTPUT_PARSING)
                    return RewriteContentOutput(
                        status_code=OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_OUTPUT_PARSING.value,
                        error_message=f"AI rewrite failed: The summarization agent produced output that could not be parsed. Details: {str(e)}",
                        ai_rewritten_content_blocks=[],
                        trace_id=current_trace_id
                    )

            # Get the reconstruction tool directly from the agents_factory instance
            reconstruction_tool = self.agents_factory.content_processor_tool
            
            # Re-get essential image metadata for the reconstruction tool
            # This is done here again to ensure the tool gets the exact same data as the summarizer
            essential_image_metadata = reconstruction_tool._run(
                operation="extract_image_metadata", 
                content_blocks=self.rewrite_input.content_blocks_to_rewrite
            )
            image_metadata_json = json.dumps(essential_image_metadata or [])

            try:
                # The tool expects the structured summary data directly
                reconstructed_block_dicts: List[Dict[str, Any]] = reconstruction_tool._run(
                    operation="reconstruct_content_from_summary",
                    structured_summary_input=structured_summary_from_llm,
                    image_metadata_list_json=image_metadata_json
                )
                
                if not reconstructed_block_dicts or not isinstance(reconstructed_block_dicts, list):
                    raise ValueError("Reconstruction tool returned no valid block dictionaries.")

                logger.info(f"FastContentBlockProcessorTool finished reconstruction. Number of blocks: {len(reconstructed_block_dicts)}", extra={
                    'task_id': self.task_id, 
                    'correlation_id': self.correlation_id
                })

            except Exception as e_recon:
                logger.error("FastContentBlockProcessorTool._run failed during reconstruction.", extra={
                    'task_id': self.task_id,
                    'correlation_id': self.correlation_id,
                    'error': str(e_recon)
                }, exc_info=True)
                _update_progress(f"Content reconstruction failed: {str(e_recon)}", OrchestrationStatusCodeEnum.REWRITE_FAILED_RECONSTRUCTION)
                return RewriteContentOutput(
                    status_code=OrchestrationStatusCodeEnum.REWRITE_FAILED_RECONSTRUCTION.value,
                    error_message=f"AI rewrite failed: The content reconstruction step encountered an error. Details: {str(e_recon)}",
                    ai_rewritten_content_blocks=[],
                    trace_id=current_trace_id
                )

            _update_progress("Content reconstruction successful, parsing to ContentBlock models", OrchestrationStatusCodeEnum.REWRITE_RECONSTRUCTION_COMPLETED)
            rewritten_content_blocks = self.safe_parse_to_content_blocks(
                reconstructed_block_dicts, "reconstructed_blocks_from_tool"
            )

            if not rewritten_content_blocks and reconstructed_block_dicts:
                 logger.warning("Reconstruction tool returned data, but safe_parse_to_content_blocks yielded empty result.", extra={
                    'task_id': self.task_id, 
                    'correlation_id': self.correlation_id
                 })
                 # This might be a partial success or a type of failure depending on requirements.
                 # For now, it will proceed to a success status but with empty blocks.

            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info("Content rewrite process completed successfully.", extra={
                'task_id': self.task_id, 
                'correlation_id': self.correlation_id,
                'processing_time_ms': processing_time_ms,
                'num_rewritten_blocks': len(rewritten_content_blocks)
            })
            _update_progress("Rewrite process completed successfully", OrchestrationStatusCodeEnum.REWRITE_SUCCESS)
            
            return RewriteContentOutput(
                status_code=OrchestrationStatusCodeEnum.REWRITE_SUCCESS.value,
                ai_rewritten_content_blocks=rewritten_content_blocks,
                token_usage=crew_result.token_usage.model_dump() if crew_result and crew_result.token_usage else None,
                processing_time_ms=processing_time_ms,
                trace_id=current_trace_id
            )

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Unhandled exception in ContentRewriteCrewManager.run: {str(e)}", extra={
                'task_id': self.task_id,
                'correlation_id': self.correlation_id,
                'processing_time_ms': processing_time_ms
            }, exc_info=True)
            
            _update_progress(f"Unhandled exception: {str(e)}", OrchestrationStatusCodeEnum.REWRITE_FAILED_UNHANDLED_EXCEPTION)

            return RewriteContentOutput(
                status_code=OrchestrationStatusCodeEnum.REWRITE_FAILED_UNHANDLED_EXCEPTION.value,
                error_message=f"AI rewrite failed due to an unexpected internal error. Please try again later or contact support if the issue persists. Details: {str(e)}",
                ai_rewritten_content_blocks=[],
                processing_time_ms=processing_time_ms,
                trace_id=current_trace_id
            )

# Example Usage (for direct testing if needed)
if __name__ == "__main__":
    import asyncio
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
    output = asyncio.run(crew_manager.run())

    print("\n--- Crew Output ---")
    if output.status_code == OrchestrationStatusCodeEnum.REWRITE_SUCCESS.value: # Compare with Enum value
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
    if output.token_usage:
        print(f"Token Usage: {output.token_usage}")
    else:
        print("Token Usage: N/A")
    print(f"Processing Time: {output.processing_time_ms} ms") 