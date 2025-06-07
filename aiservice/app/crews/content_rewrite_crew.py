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
from textwrap import dedent
from pydantic import ValidationError

from crewai.tasks.task_output import TaskOutput

from aiservice.app.config.logging_config import get_logger
from aiservice.app.agents.content_rewrite_agents import ContentRewriteAgents
from aiservice.app.models.orchestration_models import ContentBlock, OrchestrationStatusCodeEnum
from aiservice.app.models.insight_generation_models import RewriteContentInput, RewriteContentOutput
from aiservice.app.models.task_output_models import StructuredSummary
from aiservice.app.services.task_db_service import update_task_progress_stage

logger = get_logger(__name__)

class ContentRewriteCrewManager:
    """Manages the creation and execution of the Content Rewrite Crew."""

    def __init__(self,
                 rewrite_input: RewriteContentInput,
                 task_id: Optional[str] = None,
                 db_connection: Optional[Any] = None,
                 verbose_level: int = 0,
                 correlation_id: Optional[str] = None):
        """Initializes the crew manager."""
        self.rewrite_input = rewrite_input
        self.task_id = task_id if task_id else str(uuid.uuid4())
        self.db_connection = db_connection
        self.verbose_level = verbose_level
        self.correlation_id = correlation_id
        
        self.user_id_for_rewrite = "default_user_id_rewrite_op"
        if rewrite_input.user_id:
            self.user_id_for_rewrite = rewrite_input.user_id
        
        self.original_document_id = "original_doc_id_not_found"
        if rewrite_input.document_metadata and rewrite_input.document_metadata.document_id:
            self.original_document_id = rewrite_input.document_metadata.document_id

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
        """Defines and configures the Content Rewrite Crew."""
        summarization_agent = self.agents_factory.summarization_agent()

        task_summarize_content = Task(
            description=dedent(f"""\
                Analyze the provided 'concatenated_text' and 'essential_image_metadata' to generate a single, clean JSON string representing a 'StructuredSummary'. This summary MUST begin with a specifically formatted TL;DR section, followed by a detailed, high-fidelity synthesis of the source text, retaining at least 90% of the information and contextually integrating crucial image references.

                - **TL;DR Format**: The first segment MUST be a "text" type with content starting with "**TL;DR**" followed by four bullet points: What, Why, Key numbers, and Impact.
                - **Main Body**: Summarize the remaining information into logical "text" segments and "image_reference" segments for CRUCIAL images (e.g., diagrams, charts). Place image references contextually.
                - **JSON Output**: The entire output MUST be a single JSON object with a "segments" key, which is a list of segment objects. Each segment object has a "type" ("text" or "image_reference") and either a "content" or "image_id_ref" field.
                - **Tool Usage**: Use your 'Optimized LLM Interaction Tool' with temperature set to {self.agents_factory.summarizer_temperature} and max_tokens to {self.agents_factory.summarizer_max_tokens}.
                - **CRITICAL**: Your final raw output MUST be ONLY the JSON string itself, starting with {{ and ending with }}.

                **Inputs for Task:**
                - 'concatenated_text': `{{{{concatenated_text}}}}`
                - 'essential_image_metadata_for_summarizer_prompt': `{{{{essential_image_metadata_for_summarizer_prompt}}}}`
                """),
            expected_output="A single, valid JSON string conforming to the 'StructuredSummary' model.",
            agent=summarization_agent
        )

        return Crew(
            agents=[summarization_agent],
            tasks=[task_summarize_content],
            process=Process.sequential,
            verbose=self.verbose_level
        )

    def _clean_json_string(self, raw_output: Optional[str]) -> Optional[str]:
        """Cleans the raw LLM output to extract a valid JSON string."""
        if not raw_output:
            return None
        
        match = re.search(r"```(?:json)?\s*({.*})\s*```", raw_output, re.DOTALL)
        content_to_parse = match.group(1).strip() if match else raw_output
        
        start_brace = content_to_parse.find('{')
        end_brace = content_to_parse.rfind('}')
        
        if start_brace != -1 and end_brace > start_brace:
            json_str = content_to_parse[start_brace : end_brace + 1]
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                return None
        return None

    def _find_agent_output(self, result) -> Optional[str]:
        """Finds the relevant agent output from the crew's result."""
        log_extra = {'task_id': self.task_id, 'correlation_id': self.correlation_id}
        if not result or not result.tasks_output:
            logger.warning("Crew result contains no task outputs.", extra=log_extra)
            return None

        task_output = result.tasks_output[0]
        raw_output = getattr(task_output, 'raw', None)

        if not raw_output or not isinstance(raw_output, str):
            logger.warning(f"Task output's 'raw' attribute is empty or not a string.", extra=log_extra)
            return None
        
        return raw_output

    def run(self) -> RewriteContentOutput:
        """Executes the content rewrite crew."""
        start_time = time.time()
        log_extra = {'task_id': self.task_id, 'correlation_id': self.correlation_id}
        logger.info("ContentRewriteCrewManager run method started.", extra=log_extra)

        def _update_progress(stage_message: str, status_code: OrchestrationStatusCodeEnum):
            logger.info(f"Progress: {stage_message}", extra={**log_extra, 'status_code': status_code.value})
            if self.db_connection:
                update_task_progress_stage(self.db_connection, self.task_id, status_code, stage_message)

        try:
            _update_progress("Rewrite process initiated", OrchestrationStatusCodeEnum.REWRITE_STARTED)
            
            concatenated_text = "\n\n".join(b.content for b in self.rewrite_input.content_blocks_to_rewrite if b.content)
            image_metadata_list = [b.image_metadata for b in self.rewrite_input.content_blocks_to_rewrite if b.type == 'image' and b.image_metadata]
            essential_image_metadata_prompt = json.dumps([m.model_dump(include={'image_id_ref', 'gcs_url', 'caption', 'alt_text', 'llm_description'}) for m in image_metadata_list]) if image_metadata_list else "[]"
            
            crew_inputs = {'concatenated_text': concatenated_text, 'essential_image_metadata_for_summarizer_prompt': essential_image_metadata_prompt}

            self.crew = self.setup_crew()
            _update_progress("Summarization agent running", OrchestrationStatusCodeEnum.REWRITE_SUMMARIZATION_AGENT_PROCESSING)
            
            try:
                crew_result = self.crew.kickoff(inputs=crew_inputs)
            except Exception as e:
                return self.finalize_as_failure(OrchestrationStatusCodeEnum.ERROR_CREW_EXECUTION_FAILED, f"Crew kickoff failed: {e}")

            raw_llm_output = self._find_agent_output(crew_result)
            if not raw_llm_output:
                return self.finalize_as_failure(OrchestrationStatusCodeEnum.REWRITE_FAILED_NO_AGENT_OUTPUT, "No output from summarization agent.")

            cleaned_json_str = self._clean_json_string(raw_llm_output)
            if not cleaned_json_str:
                return self.finalize_as_failure(OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_OUTPUT_PARSING, "Failed to extract clean JSON from LLM output.")

            try:
                structured_summary = StructuredSummary.model_validate_json(cleaned_json_str)
            except ValidationError as e:
                return self.finalize_as_failure(OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_OUTPUT_PARSING, f"Agent output failed Pydantic validation: {e}")
            
            _update_progress("Starting content reconstruction", OrchestrationStatusCodeEnum.REWRITE_RECONSTRUCTION_STARTED)
            
            try:
                reconstructed_blocks = self.agents_factory.content_processor_tool.reconstruct_content_from_summary(
                    summary=structured_summary,
                    original_blocks=self.rewrite_input.content_blocks_to_rewrite,
                    target_document_id=self.new_rewritten_document_id
                )
            except Exception as e:
                return self.finalize_as_failure(OrchestrationStatusCodeEnum.REWRITE_FAILED_RECONSTRUCTION, f"Content reconstruction tool failed: {e}")

            return self.finalize_as_success(reconstructed_blocks, crew_result.usage_metrics, time.time() - start_time)

        except Exception as e:
            logger.error(f"Unhandled exception in ContentRewriteCrewManager.run: {e}", exc_info=True, extra=log_extra)
            return self.finalize_as_failure(OrchestrationStatusCodeEnum.REWRITE_FAILED_UNHANDLED_EXCEPTION, f"Unhandled exception: {e}")

    def finalize_as_failure(self, error_code: OrchestrationStatusCodeEnum, error_message: str) -> RewriteContentOutput:
        """Finalizes the execution with a failure status."""
        return RewriteContentOutput(
            status_code=error_code.value,
            error_message=error_message,
            new_rewritten_document_id=self.new_rewritten_document_id,
            user_id=self.user_id_for_rewrite,
            original_document_id=self.original_document_id,
            correlation_id=self.correlation_id,
            rewritten_content_blocks=[]
        )

    def finalize_as_success(self, reconstructed_blocks: List[ContentBlock], usage_metrics: Dict[str, int], processing_time: float) -> RewriteContentOutput:
        """Finalizes the execution with a success status."""
        return RewriteContentOutput(
            status_code=OrchestrationStatusCodeEnum.SUCCESS.value,
            new_rewritten_document_id=self.new_rewritten_document_id,
            rewritten_content_blocks=reconstructed_blocks,
            usage_metrics=usage_metrics,
            user_id=self.user_id_for_rewrite,
            original_document_id=self.original_document_id,
            correlation_id=self.correlation_id,
            processing_time_ms=int(processing_time * 1000)
        )