#!/usr/bin/env python
# coding: utf-8
"""
Defines the GeneralPurposeTitleGenerationCrewManager, responsible for orchestrating
agents to generate a title for a given list of content blocks.
Following V2.6 Development Plan - Iteration 1.2.
"""

from crewai import Crew, Process, Task
from typing import List, Dict, Any, Optional
import json
import time
import uuid
from textwrap import dedent

# Agent definitions
from aiservice.app.agents.title_generation_agents import TitleGenerationAgents

# Model imports
from aiservice.app.models.orchestration_models import ContentBlock, OrchestrationStatusCodeEnum, DocumentMetadata # Added DocumentMetadata
from aiservice.app.models.insight_generation_models import GenerateTitleInput, GenerateTitleOutput 

class GeneralPurposeTitleGenerationCrewManager:
    """Manages the creation and execution of the General Purpose Title Generation Crew."""

    def __init__(self, title_input: GenerateTitleInput, verbose_level: int = 0):
        """
        Initializes the crew manager with the necessary input data.
        Args:
            title_input: The input data containing content_blocks.
            verbose_level: Integer to control verbosity of logs. 0 = minimal.
        """
        self.title_input = title_input
        self.verbose_level = verbose_level
        
        self.user_id: Optional[str] = "default_user_id_title_manager" # Default
        if hasattr(self.title_input, 'user_id') and self.title_input.user_id:
            self.user_id = self.title_input.user_id
        elif isinstance(self.title_input.document_metadata, DocumentMetadata) and self.title_input.document_metadata.user_id:
            self.user_id = self.title_input.document_metadata.user_id
        # If GenerateTitleInput is updated to directly include user_id or document_metadata, adjust access accordingly.
        # For now, GenerateTitleInput from models.py doesn't explicitly have user_id or document_metadata yet.
        # Let's assume for now GenerateTitleInput might be augmented or user_id is passed differently in a real scenario.
        # For the purpose of this class, we'll use a placeholder if not found directly on title_input for now.
        # This will be refined once GenerateTitleInput is finalized in models.py or FastAPI layer handles user_id propagation.

        print(f"INFO: GeneralPurposeTitleGenerationCrewManager initialized with user_id: {self.user_id}")
        self.agents_factory = TitleGenerationAgents(user_id=self.user_id)
        self.crew: Optional[Crew] = None

    def setup_crew(self) -> Crew:
        """
        Defines and configures the General Purpose Title Generation Crew, its agent, and task.
        """
        title_crafting_agent = self.agents_factory.title_crafting_agent()

        # Task for TitleCraftingAgent
        # The agent itself has the tools. The task description guides it on how to use them implicitly.
        task_generate_title = Task(
            description=dedent(f"""Analyze the provided '{{{{content_extract}}}}' to generate a title.
            The content extract is a string derived from a list of content blocks.
            Your goal is to produce a concise, informative, and engaging title suitable for a knowledge card.
            Focus on the main topic of the content.
            
            When using your 'Optimized LLM Interaction Tool' for this task, you MUST set the 'temperature' parameter to {self.agents_factory.title_crafter_temperature} and the 'max_tokens' parameter to {self.agents_factory.title_crafter_max_tokens}.
            The 'FastContentBlockProcessorTool' is available if you need to perform specific block operations, but for title generation from an extract, the LLM tool is primary.
            """),
            expected_output="A single string representing the suggested title. Example: 'The Future of AI in Healthcare'",
            agent=title_crafting_agent,
            # No specific tools needed here if the agent is correctly configured with its default tools.
        )

        title_generation_crew = Crew(
            agents=[title_crafting_agent],
            tasks=[task_generate_title],
            process=Process.sequential,
            verbose=True if self.verbose_level > 0 else False,
            # memory=False, # Default for Crew is False, explicit if needed
            # embedder= # Not using an embedder for this simple crew
        )
        self.crew = title_generation_crew # Assign to instance variable
        return self.crew

    def run(self) -> GenerateTitleOutput: 
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        print(f"INFO: [{trace_id}] GeneralPurposeTitleGenerationCrewManager run initiated for user_id: {self.user_id}")

        # Initialize default return values
        suggested_title: Optional[str] = None
        usage_metrics_dict: Optional[Dict[str, Any]] = None
        final_status_code: OrchestrationStatusCodeEnum = OrchestrationStatusCodeEnum.ERROR_UNKNOWN
        final_error_message: Optional[str] = "Title generation process did not complete successfully or was not initiated."
        processing_time_ms: float = 0.0

        try:
            # 1. Prepare content extract
            print(f"DEBUG: [{trace_id}] Validating input. self.title_input is None: {self.title_input is None}")
            if self.title_input:
                print(f"DEBUG: [{trace_id}] self.title_input.content_blocks is None: {self.title_input.content_blocks is None}")
                if self.title_input.content_blocks is not None:
                    print(f"DEBUG: [{trace_id}] len(self.title_input.content_blocks): {len(self.title_input.content_blocks)}")

            if not self.title_input or not self.title_input.content_blocks:
                final_error_message = "Input error: No content blocks provided for title generation."
                final_status_code = OrchestrationStatusCodeEnum.ERROR_INPUT_VALIDATION
                print(f"ERROR VAL1: [{trace_id}] {final_error_message}") # Changed print prefix
                processing_time_ms = (time.time() - start_time) * 1000
                return GenerateTitleOutput(
                    suggested_title=None,
                    status_code=final_status_code.value,
                    error_message=final_error_message,
                    usage_metrics=None,
                    processing_time_ms=processing_time_ms,
                    trace_id=trace_id
                )

            text_parts = []
            for block in self.title_input.content_blocks:
                if block.type == "text" and block.content:
                    text_parts.append(block.content.strip())
            
            concatenated_text = "\n\n".join(text_parts)

            print(f"DEBUG: [{trace_id}] concatenated_text.strip() is empty: {not concatenated_text.strip()}")
            print(f"DEBUG: [{trace_id}] concatenated_text (first 50): '{concatenated_text[:50]}'")

            if not concatenated_text.strip():
                final_error_message = "Input error: Provided content blocks contain no textual content for title generation."
                final_status_code = OrchestrationStatusCodeEnum.ERROR_INPUT_VALIDATION
                print(f"ERROR VAL2: [{trace_id}] {final_error_message}") # Changed print prefix
                processing_time_ms = (time.time() - start_time) * 1000
                return GenerateTitleOutput(
                    suggested_title=None,
                    status_code=final_status_code.value,
                    error_message=final_error_message,
                    usage_metrics=None,
                    processing_time_ms=processing_time_ms,
                    trace_id=trace_id
                )
            
            # Truncate to a maximum length (e.g., 4000 characters) as per plan
            # This is a simple truncation. More sophisticated methods could be used if needed.
            MAX_CONTENT_EXTRACT_LENGTH = 4000 
            content_extract = concatenated_text[:MAX_CONTENT_EXTRACT_LENGTH]

            if self.verbose_level > 1:
                print(f"DEBUG: [{trace_id}] Original concatenated text length: {len(concatenated_text)}, Truncated extract length for title generation: {len(content_extract)}, First 200 chars: {content_extract[:200]}...")

            # 2. Setup the crew (already assigned to self.crew in setup_crew, called by __init__ is not ideal, let's call it here)
            if not self.crew:
                 self.setup_crew() # Ensure crew is set up if not already

            # 3. Prepare kickoff inputs
            crew_kickoff_inputs = {
                'content_extract': content_extract
            }
            
            if self.verbose_level > 0:
                print(f"INFO: [{trace_id}] Kicking off title generation crew.")

            # 4. Kick off crew
            # Note: CrewAI kickoff can return a CrewOutput object or the raw string from the last task
            crew_result_raw: Any = self.crew.kickoff(inputs=crew_kickoff_inputs)

            # 5. Process usage metrics
            if self.crew and hasattr(self.crew, 'usage_metrics') and self.crew.usage_metrics:
                # CrewAI usage_metrics is a list of dicts for each agent, or a dict if only one LLM call.
                # We need to aggregate or decide how to represent this.
                # For a single agent crew, it might be simpler.
                # Let's assume it's a list and we take the first one or sum totals if available.
                # Or, if it conforms to a dict like {'total_tokens': X, ...}, we can use it directly.
                # Based on ContentRewriteCrew, it seems to be a dict like object by the end.
                if isinstance(self.crew.usage_metrics, list) and self.crew.usage_metrics:
                     # Simplistic aggregation: sum relevant fields if they exist in dicts within list
                    total_tokens = sum(m.get('total_tokens', 0) for m in self.crew.usage_metrics if isinstance(m, dict))
                    prompt_tokens = sum(m.get('prompt_tokens', 0) for m in self.crew.usage_metrics if isinstance(m, dict))
                    completion_tokens = sum(m.get('completion_tokens', 0) for m in self.crew.usage_metrics if isinstance(m, dict))
                    successful_requests = sum(m.get('successful_requests', 0) for m in self.crew.usage_metrics if isinstance(m, dict))
                    usage_metrics_dict = {
                        'total_tokens': total_tokens,
                        'prompt_tokens': prompt_tokens,
                        'completion_tokens': completion_tokens,
                        'successful_requests': successful_requests
                    }
                    # If crew.usage_metrics is already a dict with these keys, this will just re-wrap it.
                elif isinstance(self.crew.usage_metrics, dict):
                    usage_metrics_dict = self.crew.usage_metrics
                if self.verbose_level > 0 and usage_metrics_dict:
                     print(f"DEBUG: [{trace_id}] Usage Metrics: {usage_metrics_dict}")

            # 6. Extract final result
            # The result of a sequential crew with one task is typically the output of that task.
            # If crew_result_raw is a CrewOutput object, its .raw attribute often holds the string.
            # If it's already a string, that's the title.
            if crew_result_raw:
                if hasattr(crew_result_raw, 'raw_output') and isinstance(crew_result_raw.raw_output, str): # CrewAI >=0.29.0 often uses raw_output
                    suggested_title = crew_result_raw.raw_output.strip()
                elif hasattr(crew_result_raw, 'result') and isinstance(crew_result_raw.result, str): # Older CrewAI versions
                     suggested_title = crew_result_raw.result.strip()
                elif isinstance(crew_result_raw, str):
                    suggested_title = crew_result_raw.strip()
                else:
                    # Fallback, try to convert to string if it's some other object from the task.
                    try:
                        suggested_title = str(crew_result_raw).strip()
                        print(f"WARNING: [{trace_id}] Crew result was not a string or standard CrewOutput, converted to string: {suggested_title[:100]}...")
                    except Exception as str_e:
                        final_error_message = f"Crew execution returned an unparsable result type: {type(crew_result_raw)}. Error during str conversion: {str_e}"
                        final_status_code = OrchestrationStatusCodeEnum.ERROR_UNEXPECTED_OUTPUT_FROM_CREW
                        print(f"ERROR: [{trace_id}] {final_error_message}")
                        suggested_title = None # Ensure it's None if parsing failed

                if suggested_title: # If title extraction was successful
                    # Clean up potential quoting if LLM wraps output in quotes
                    if (suggested_title.startswith('"') and suggested_title.endswith('"')) or \
                       (suggested_title.startswith("'") and suggested_title.endswith("'")):
                        suggested_title = suggested_title[1:-1]
                    
                    final_status_code = OrchestrationStatusCodeEnum.SUCCESS
                    final_error_message = None
                    if self.verbose_level > 0:
                        print(f"INFO: [{trace_id}] Suggested title: {suggested_title}")
                else: # If string conversion led to empty or still None
                    if final_status_code == OrchestrationStatusCodeEnum.ERROR_UNKNOWN: # Only override if not already set by parsing error
                        final_error_message = "Crew execution resulted in an empty title."
                        final_status_code = OrchestrationStatusCodeEnum.ERROR_EMPTY_RESULT_FROM_CREW
                    print(f"WARNING: [{trace_id}] {final_error_message}")

            else: # crew_result_raw is None or empty
                final_error_message = "Crew execution returned no result (None or empty)."
                final_status_code = OrchestrationStatusCodeEnum.ERROR_NO_RESULT_FROM_CREW
                print(f"ERROR: [{trace_id}] {final_error_message}")

        except Exception as e:
            import traceback
            error_stack = traceback.format_exc()
            
            # Check if a specific validation error was already set and this is a subsequent failure
            # This logic is complex; for now, assume any exception here is a new problem unless status is already SUCCESS
            if final_status_code == OrchestrationStatusCodeEnum.SUCCESS:
                # This case should ideally not happen if success means no errors
                pass # Or log an anomaly
            
            # If a validation error was supposed to be returned but code flowed here due to an issue IN the return path:
            # This is hard to detect perfectly. The print(f"ERROR VAL... didn't appear, so it's not this.

            # Default to a general crew execution error if no specific validation error was about to be returned.
            # The initial value of final_status_code is ERROR_UNKNOWN.
            current_error_type_name = type(e).__name__
            current_error_str = str(e)

            # If a previous status was set by validation (which means we should not have reached here)
            # we might want to log that. But the print logs suggest validation blocks were not entered.
            # So, it's a new error.
            final_error_message = f"Crew execution failed. Type: {current_error_type_name}, Msg: {current_error_str}"
            # Only update status if it's still the default unknown, otherwise a more specific error might have been set by kickoff processing.
            if final_status_code == OrchestrationStatusCodeEnum.ERROR_UNKNOWN:
                 final_status_code = OrchestrationStatusCodeEnum.ERROR_CREW_EXECUTION
            
            print(f"ERROR CAUGHT: [{trace_id}] {final_error_message}\nStack trace:\n{error_stack}")
        
        finally:
            processing_time_ms = (time.time() - start_time) * 1000
            print(f"INFO: [{trace_id}] GeneralPurposeTitleGenerationCrewManager run finished in {processing_time_ms/1000.0:.3f} seconds. Status: {final_status_code.value}")
            
            return GenerateTitleOutput(
                suggested_title=suggested_title,
                status_code=final_status_code.value,
                error_message=final_error_message,
                usage_metrics=usage_metrics_dict,
                processing_time_ms=processing_time_ms,
                trace_id=trace_id
            )

if __name__ == '__main__':
    print("--- GeneralPurposeTitleGenerationCrewManager: Local Test Run --- ")
    
    # Ensure necessary model imports for the test
    from aiservice.app.models.orchestration_models import ContentBlock, DocumentMetadata
    from aiservice.app.models.insight_generation_models import GenerateTitleInput 

    print("Simulating input data...")
    sample_doc_metadata = DocumentMetadata(
        document_id="doc_title_test_001",
        source_uri="local/test_document.txt",
        user_id="test_user_for_title_crew",
        status_code="processed_successfully",
        source_identifier="test_doc_title_001",
        source_type="text_file"
    )

    sample_blocks = [
        ContentBlock(block_id="b1", type="text", content="The Rise of Quantum Computing: A New Era of Calculation.", order_index=0, user_id=sample_doc_metadata.user_id, document_id=sample_doc_metadata.document_id),
        ContentBlock(block_id="b2", type="text", content="Quantum computers leverage the principles of quantum mechanics to perform complex calculations that are intractable for classical computers. This includes superposition and entanglement, allowing them to explore vast computational spaces.", order_index=1, user_id=sample_doc_metadata.user_id, document_id=sample_doc_metadata.document_id),
        ContentBlock(block_id="b3", type="text", content="Potential applications span drug discovery, materials science, financial modeling, and cryptography. While still in early stages, the progress is rapid.", order_index=2, user_id=sample_doc_metadata.user_id, document_id=sample_doc_metadata.document_id),
        ContentBlock(block_id="b4", type="text", content="Challenges remain in building stable, large-scale quantum computers and developing robust quantum algorithms.", order_index=3, user_id=sample_doc_metadata.user_id, document_id=sample_doc_metadata.document_id)
    ]
    
    title_input_data = GenerateTitleInput(
        content_blocks=sample_blocks,
        document_metadata=sample_doc_metadata,
        # user_id can be explicitly set if not in document_metadata or to override
        # user_id="explicit_user_id_for_title_test"
    )

    print(f"Initializing GeneralPurposeTitleGenerationCrewManager with user_id: {sample_doc_metadata.user_id} (from metadata)...")
    # Set verbose_level to 2 for detailed crew output, 0 or 1 for less.
    manager = GeneralPurposeTitleGenerationCrewManager(title_input=title_input_data, verbose_level=2)

    print("\n--- Running Title Generation Crew ---")
    result = manager.run()
    print("--- Title Generation Crew Finished ---")

    print("\n--- Crew Output --- ")
    print(f"Suggested Title: {result.suggested_title}")
    print(f"Status Code: {result.status_code}")
    if result.error_message:
        print(f"Error Message: {result.error_message}")
    if result.usage_metrics:
        print(f"Usage Metrics: {result.usage_metrics}")
    print(f"Processing Time (ms): {result.processing_time_ms}")
    print(f"Trace ID: {result.trace_id}")

    print("\n--- Testing with Empty Content --- ")
    empty_blocks_input = GenerateTitleInput(
        content_blocks=[ContentBlock(block_id="eb1", type="text", content="  ", order_index=0)],
        document_metadata=sample_doc_metadata
    )
    manager_empty = GeneralPurposeTitleGenerationCrewManager(title_input=empty_blocks_input, verbose_level=0)
    result_empty = manager_empty.run()
    print(f"Empty Content - Suggested Title: {result_empty.suggested_title}")
    print(f"Empty Content - Status Code: {result_empty.status_code}")
    print(f"Empty Content - Error Message: {result_empty.error_message}")

    print("\n--- Testing with No Content Blocks --- ")
    no_blocks_input = GenerateTitleInput(
        content_blocks=[],
        document_metadata=sample_doc_metadata
    )
    manager_no_blocks = GeneralPurposeTitleGenerationCrewManager(title_input=no_blocks_input, verbose_level=0)
    result_no_blocks = manager_no_blocks.run()
    print(f"No Blocks - Suggested Title: {result_no_blocks.suggested_title}")
    print(f"No Blocks - Status Code: {result_no_blocks.status_code}")
    print(f"No Blocks - Error Message: {result_no_blocks.error_message}")
    print("\n--- End of Local Test Run --- ") 