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

# Agent definitions
from aiservice.app.agents.content_rewrite_agents import ContentRewriteAgents

# Model imports
from aiservice.app.models.orchestration_models import ContentBlock, OrchestrationStatusCodeEnum
from aiservice.app.models.insight_generation_models import RewriteContentInput, RewriteContentOutput
from aiservice.app.models.task_output_models import SummarizerTaskOutput


class ContentRewriteCrewManager:
    """Manages the creation and execution of the Content Rewrite Crew."""

    def __init__(self, rewrite_input: RewriteContentInput, verbose_level: int = 0):
        """
        Initializes the crew manager with the necessary input data.
        Args:
            rewrite_input: The input data containing content_blocks and optional metadata.
            verbose_level: Integer to control verbosity of logs. 0 = minimal.
        """
        self.rewrite_input = rewrite_input
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
        output_constructor_agent = self.agents_factory.output_constructor_agent()

        # Define Tasks
        # Note: CrewAI's {{variable_name}} syntax will be used in descriptions for kickoff inputs.
        # Constants like temperature are embedded directly using f-string from agents_factory.
        task_summarize_content = Task(
            description=dedent(f"""
                You are provided with 'concatenated_text':
                {{{{concatenated_text}}}}

                And 'essential_image_metadata' (a list of image information):
                {{{{essential_image_metadata_for_summarizer_prompt}}}}

                Generate a concise summary of the 'concatenated_text'.
                If images from 'essential_image_metadata' are contextually important for the summary,
                refer to them using placeholders like '[IMAGE: <image_id_ref_value>]' or '[IMAGE: <gcs_url_value>]'.
                The image_id_ref_value or gcs_url_value should correspond to the 'image_id_ref' or 'gcs_url' present in the 'essential_image_metadata'.
                The summary should be a single string of well-written text, which will be wrapped in the 'SummarizerTaskOutput' model under the 'summary_text' field.
                When using your 'Optimized LLM Interaction Tool' for this task, you MUST set the 'temperature' parameter to {self.agents_factory.summarizer_temperature} and the 'max_tokens' parameter to {self.agents_factory.summarizer_max_tokens}.
                Your final output for this task MUST be a valid JSON object that conforms to the 'SummarizerTaskOutput' Pydantic model.
                Specifically, it should be a dictionary with a single key 'summary_text' holding the generated summary string.
                Example: {{"summary_text": "This is the generated summary."}}
                """),
            expected_output=(
                "The single string summary, encapsulated within a 'SummarizerTaskOutput' Pydantic object. "
                "This output is produced DIRECTLY and SOLELY by the 'Optimized LLM Interaction Tool' "
                "during its FIRST successful execution for this task. Upon receiving this structured tool output, "
                "the agent's work for this task is considered ABSOLUTELY COMPLETE. No further thoughts, actions, "
                "or tool calls are required or permitted for this specific summarization task."
            ),
            agent=summarization_agent,
            tools=[self.agents_factory.optimized_llm_tool],
            output_pydantic=SummarizerTaskOutput
        )

        task_reconstruct_output = Task(
            description=dedent("""
                CRITICAL INSTRUCTION: Your ONLY function is to use the 'FastContentBlockProcessorTool' ONCE and IMMEDIATELY return its exact output.
                DO NOT add any commentary, explanation, or any text other than the direct tool output.
                
                Tool Call Parameters:
                1. 'operation': Use the exact string 'reconstruct_content_from_summary'.
                2. 'summarized_text': Use the 'summarized_text' you received from the 'task_summarize_content' output.
                3. 'image_metadata_list_json': Use the exact JSON string provided in the '{{reconstructor_image_metadata_list_json}}' crew kickoff input variable.
                4. 'document_id': Use the exact string value provided in the '{{reconstructor_document_id}}' crew kickoff input variable.
                
                Your final answer for this task MUST be the direct, unaltered, raw output from the 'FastContentBlockProcessorTool'.
                """),
            expected_output="A list of ContentBlock dictionaries, reconstructed from the summary and image metadata, as returned by the FastContentBlockProcessorTool.",
            agent=output_constructor_agent, # Agent has the tool
            context=[task_summarize_content]
        )

        content_rewrite_crew = Crew(
            agents=[summarization_agent, output_constructor_agent],
            tasks=[task_summarize_content, task_reconstruct_output],
            process=Process.sequential,
            verbose=True, # Controls CrewAI's internal verbosity. Could be linked to self.verbose_level if needed.
        )
        return content_rewrite_crew

    def _try_json_parse(self, data_str: str) -> Any:
        try:
            return ast.literal_eval(data_str)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as e_ast:
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                # Corrected regex: remove unnecessary backslashes before brackets
                match = re.search(r'(\[.*?\])', data_str, re.DOTALL) # Non-greedy match for content within brackets
                if match:
                    json_like_part = match.group(1)
                    try:
                        return json.loads(json_like_part)
                    except json.JSONDecodeError as e_inner:
                        print(f"WARNING: Found JSON-like part but failed to parse with json.loads: {json_like_part[:200]}. Error: {e_inner}") # Retained
                        return None
                print(f"WARNING: Failed to decode with json.loads directly and no parsable array found via regex from string: {data_str[:200]}") # Retained
                return None
            except Exception as e_json_other:
                print(f"ERROR: Unexpected error during json.loads fallback: {e_json_other}. Data: {data_str[:200]}") # Retained
                return None
        except Exception as e_outer:
            print(f"ERROR: Unexpected error in _try_json_parse: {e_outer}. Data: {data_str[:200]}") # Retained
            return None

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
        # Use self.user_id_for_rewrite and self.new_rewritten_document_id established in __init__
        print(f"INFO: ContentRewriteCrewManager run initiated. User ID: {self.user_id_for_rewrite}, Rewritten Document ID: {self.new_rewritten_document_id}")

        # Initialize default return values
        parsed_content_blocks: List[ContentBlock] = []
        final_agent_output: Any = None # Using Any as it can be diverse before parsing
        usage_metrics_dict: Optional[Dict[str, Any]] = None
        final_status_code: OrchestrationStatusCodeEnum = OrchestrationStatusCodeEnum.ERROR_UNKNOWN # Default status
        final_error_message: Optional[str] = "Rewrite process did not complete successfully." # Default error

        # 1. Pre-process input: Concatenate text and extract essential image metadata
        concatenated_text = ""
        essential_image_metadata: List[Dict[str, Any]] = []
        text_parts = []
        for block in self.rewrite_input.content_blocks_to_rewrite:
            if block.type == "text" and block.content:
                text_parts.append(block.content)
            elif block.type == "image" and block.image_id_ref:
                # Normalize gcs_url: replace backslashes with forward slashes
                normalized_gcs_url = block.gcs_url.replace("\\", "/") if block.gcs_url else None
                essential_meta = {
                    "image_id_ref": block.image_id_ref,
                    "gcs_url": normalized_gcs_url, # Use normalized URL
                    "alt_text": block.alt_text,
                    "caption": block.caption,
                    "llm_description": block.llm_description,
                    "width": block.width,
                    "height": block.height
                }
                essential_image_metadata.append({k: v for k, v in essential_meta.items() if v is not None})
        concatenated_text = "\\n\\n".join(text_parts)

        # current_document_id is no longer needed here as new_rewritten_document_id is used.
        # We can log the original one if needed for context.
        if not (self.rewrite_input.document_metadata and self.rewrite_input.document_metadata.document_id):
            print(f"WARNING: Original document_id not found in rewrite_input.document_metadata.document_id. Original was: {self.original_document_id}")


        # 2. Setup the crew
        # Agents factory is already initialized with the correct user_id and new_rewritten_document_id
        self.crew = self.setup_crew()

        # 3. Prepare the inputs for the crew.kickoff()
        crew_kickoff_inputs = {
            'concatenated_text': concatenated_text,
            'essential_image_metadata_for_summarizer_prompt': json.dumps(essential_image_metadata),
            'reconstructor_image_metadata_list_json': json.dumps(essential_image_metadata),
            'reconstructor_document_id': self.new_rewritten_document_id # Pass the new ID here
        }
        
        if self.verbose_level > 1:
            print(f"DEBUG ContentRewriteCrewManager: Kicking off crew with inputs (metadata potentially truncated for log):")
            print(f"  concatenated_text length: {len(crew_kickoff_inputs['concatenated_text'])}")
            print(f"  essential_image_metadata_for_summarizer_prompt: {crew_kickoff_inputs['essential_image_metadata_for_summarizer_prompt'][:200] if crew_kickoff_inputs['essential_image_metadata_for_summarizer_prompt'] else '[]'}...")
            print(f"  reconstructor_image_metadata_list_json: {crew_kickoff_inputs['reconstructor_image_metadata_list_json'][:200] if crew_kickoff_inputs.get('reconstructor_image_metadata_list_json') else '[]'}...")
            print(f"  reconstructor_document_id (for new blocks): {crew_kickoff_inputs['reconstructor_document_id']}")

        crew_result_raw: Any = None
        try:
            # 4. Kick off the crew execution
            crew_result_raw = self.crew.kickoff(inputs=crew_kickoff_inputs)

            # 5. Process usage metrics (attempt this regardless of main output success)
            if crew_result_raw and hasattr(self.crew, 'usage_metrics') and self.crew.usage_metrics:
                um = self.crew.usage_metrics
                temp_metrics_dict = {}
                known_attrs = ['total_tokens', 'prompt_tokens', 'completion_tokens', 'successful_requests']
                for attr in known_attrs:
                    if hasattr(um, attr):
                        value = getattr(um, attr)
                        temp_metrics_dict[attr] = value
                
                if isinstance(um, dict):
                    usage_metrics_dict = {**um, **temp_metrics_dict}
                elif temp_metrics_dict:
                    usage_metrics_dict = temp_metrics_dict
                else:
                    try:
                        usage_metrics_dict = vars(um)
                    except TypeError:
                        print(f"ERROR: [Primary Path] vars(um) failed for type {type(um)}. usage_metrics will be None.") # Retained (adjusted)
                        usage_metrics_dict = None
                
                if not isinstance(usage_metrics_dict, dict) and usage_metrics_dict is not None:
                    print(f"CRITICAL WARNING: [Primary Path] usage_metrics_dict is NOT a dict after conversion attempts. Type: {type(usage_metrics_dict)}. Setting to None.") # Retained
                    usage_metrics_dict = None
            
            # 6. Process crew output
            if crew_result_raw: # crew.kickoff() should ideally return the last task's output directly
                if isinstance(crew_result_raw, list):
                    final_agent_output = crew_result_raw
                elif isinstance(crew_result_raw, str):
                    # If it's a string, it might be a JSON representation of the list
                    parsed_raw_output = self._try_json_parse(crew_result_raw)
                    if isinstance(parsed_raw_output, list):
                        final_agent_output = parsed_raw_output
                    else:
                        print(f"WARNING: crew_result_raw was a string but did not parse to a list: {crew_result_raw[:500]}") # Retained
                # Check if crew_result_raw is a CrewOutput object and try to extract from tasks_output
                elif hasattr(crew_result_raw, 'tasks_output') and crew_result_raw.tasks_output:
                    print("INFO: crew_result_raw is a CrewOutput object. Attempting to extract from the last task's output.") # Retained
                    last_task_output_obj = crew_result_raw.tasks_output[-1]
                    candidate_data = None
                    if hasattr(last_task_output_obj, 'output') and last_task_output_obj.output is not None:
                        candidate_data = last_task_output_obj.output
                        print(f"INFO: Found last_task_output_obj.output. Type: {type(candidate_data)}") # Retained
                    elif hasattr(last_task_output_obj, 'exported_output') and last_task_output_obj.exported_output is not None:
                        candidate_data = last_task_output_obj.exported_output
                        print(f"INFO: Found last_task_output_obj.exported_output. Type: {type(candidate_data)}") # Retained
                    elif hasattr(last_task_output_obj, 'raw_output') and last_task_output_obj.raw_output is not None:
                        candidate_data = last_task_output_obj.raw_output
                        print(f"INFO: Found last_task_output_obj.raw_output. Type: {type(candidate_data)}") # Retained
                    # Fallback: Try converting the TaskOutput object itself to string if other attributes are None
                    elif last_task_output_obj is not None: # Check if the object itself exists
                        print(f"INFO: Trying str(last_task_output_obj) as candidate. Current type of last_task_output_obj: {type(last_task_output_obj)}") # Retained
                        try:
                            candidate_data = str(last_task_output_obj) # The __str__ method of TaskOutput might return the raw output string
                            print(f"INFO: str(last_task_output_obj) successful. Type: {type(candidate_data)}") # Retained
                        except Exception as e_str_conv:
                            print(f"WARNING: str(last_task_output_obj) failed: {e_str_conv}") # Retained

                    if candidate_data is not None:
                        if isinstance(candidate_data, list):
                            final_agent_output = candidate_data
                        elif isinstance(candidate_data, str):
                            parsed_candidate = self._try_json_parse(candidate_data)
                            if isinstance(parsed_candidate, list):
                                final_agent_output = parsed_candidate
                            else:
                                print(f"WARNING: Last task's output candidate was a string but did not parse to a list: {candidate_data[:500]}") # Retained
                        else:
                            print(f"WARNING: Last task's output candidate was not a list or string. Type: {type(candidate_data)}. Value: {str(candidate_data)[:500]}") # Retained
                    else:
                        print("WARNING: Could not find a suitable output attribute (output, exported_output, raw_output) on the last task object.") # Retained
                # Fallback: if crew_result_raw is a CrewOutput object and has a 'raw' attribute which is a string
                elif hasattr(crew_result_raw, 'raw') and isinstance(crew_result_raw.raw, str):
                    print("INFO: crew_result_raw is a CrewOutput object. Attempting to parse crew_result_raw.raw") # Retained
                    parsed_raw_output = self._try_json_parse(crew_result_raw.raw)
                    if isinstance(parsed_raw_output, list):
                        final_agent_output = parsed_raw_output
                    else:
                        print(f"WARNING: crew_result_raw.raw was a string but did not parse to a list: {crew_result_raw.raw[:500]}") # Retained
                else:
                    print(f"WARNING: crew_result_raw was not a list, string, or CrewOutput object with usable attributes, type: {type(crew_result_raw)}. Value: {str(crew_result_raw)[:500]}") # Retained
            
            # Fallback: If final_agent_output is still None (e.g. if crew_result_raw itself was None or previous checks failed)
            # and self.crew (the Crew object itself) exists and has tasks_output
            if final_agent_output is None and self.crew and hasattr(self.crew, 'tasks_output') and self.crew.tasks_output:
                print("INFO: final_agent_output still None. Attempting to extract from self.crew.tasks_output[-1].") # Retained
                last_task_output_obj = self.crew.tasks_output[-1]
                
                # The .output attribute of a TaskOutput often holds the final result from the agent.
                # For agents that are supposed to return direct tool output, this should be the raw tool output.
                # CrewAI might also place it in 'exported_output' or 'raw_output'
                # Let's prioritize .output, then .exported_output, then .raw_output
                
                candidate_data = None
                if hasattr(last_task_output_obj, 'output') and last_task_output_obj.output is not None:
                    candidate_data = last_task_output_obj.output
                    print(f"INFO: Found last_task_output_obj.output. Type: {type(candidate_data)}") # Retained
                elif hasattr(last_task_output_obj, 'exported_output') and last_task_output_obj.exported_output is not None:
                    candidate_data = last_task_output_obj.exported_output
                    print(f"INFO: Found last_task_output_obj.exported_output. Type: {type(candidate_data)}") # Retained
                elif hasattr(last_task_output_obj, 'raw_output') and last_task_output_obj.raw_output is not None:
                    candidate_data = last_task_output_obj.raw_output
                    print(f"INFO: Found last_task_output_obj.raw_output. Type: {type(candidate_data)}") # Retained
                # Fallback: Try converting the TaskOutput object itself to string if other attributes are None
                elif last_task_output_obj is not None: # Check if the object itself exists
                    print(f"INFO: Trying str(last_task_output_obj) as candidate. Current type of last_task_output_obj: {type(last_task_output_obj)}") # Retained
                    try:
                        candidate_data = str(last_task_output_obj) # The __str__ method of TaskOutput might return the raw output string
                        print(f"INFO: str(last_task_output_obj) successful. Type: {type(candidate_data)}") # Retained
                    except Exception as e_str_conv:
                        print(f"WARNING: str(last_task_output_obj) failed: {e_str_conv}") # Retained

                if candidate_data is not None:
                    if isinstance(candidate_data, list):
                        final_agent_output = candidate_data
                    elif isinstance(candidate_data, str):
                        parsed_candidate = self._try_json_parse(candidate_data)
                        if isinstance(parsed_candidate, list):
                            final_agent_output = parsed_candidate
                        else:
                            print(f"WARNING: Last task's output candidate was a string but did not parse to a list: {candidate_data[:500]}") # Retained
                    else:
                        print(f"WARNING: Last task's output candidate was not a list or string. Type: {type(candidate_data)}. Value: {str(candidate_data)[:500]}") # Retained
                else:
                    print("WARNING: Could not find a suitable output attribute (output, exported_output, raw_output) on the last task object.") # Retained

            if final_agent_output is None or not isinstance(final_agent_output, list):
                final_status_code = OrchestrationStatusCodeEnum.ERROR_UNEXPECTED_OUTPUT_TYPE
                error_msg_detail = (
                    f"Crew finished, but the final processed output was not a list as expected. "
                    f"Output type: {type(final_agent_output)}. Output (first 1000 chars): {str(final_agent_output)[:1000]}."
                )
                print(f"ERROR: Error in crew execution: {error_msg_detail}") # Retained
                final_error_message = error_msg_detail
            else:
                parsed_content_blocks = self.safe_parse_to_content_blocks(final_agent_output, "ai_rewritten_content_blocks")
                if not parsed_content_blocks and final_agent_output: # Non-empty list, but parsing failed
                    final_status_code = OrchestrationStatusCodeEnum.ERROR_CONTENT_BLOCK_VALIDATION
                    final_error_message = "Crew output was a list, but failed Pydantic validation into ContentBlocks."
                    print(f"ERROR: {final_error_message} Input list (first item): {str(final_agent_output[0])[:500] if final_agent_output else 'Empty List'}") # Retained
                elif parsed_content_blocks or not final_agent_output: # Successfully parsed or empty list output
                    final_status_code = OrchestrationStatusCodeEnum.SUCCESS
                    final_error_message = None
        except Exception as e:
            final_status_code = OrchestrationStatusCodeEnum.ERROR_CREW_EXECUTION_FAILED
            final_error_message = f"An exception occurred during crew kickoff or processing: {str(e)}"
            print(f"CRITICAL ERROR: Crew execution failed: {final_error_message}") # Retained as critical
            # Also capture usage metrics if available even on exception, if crew object exists
            if self.crew and hasattr(self.crew, 'usage_metrics') and self.crew.usage_metrics:
                # (Simplified metrics extraction for brevity in except block, could be more robust)
                usage_metrics_dict = self.crew.usage_metrics if isinstance(self.crew.usage_metrics, dict) else vars(self.crew.usage_metrics)


        end_time = time.time()
        processing_time_ms = (end_time - start_time) * 1000
        status_value = final_status_code.value if isinstance(final_status_code, OrchestrationStatusCodeEnum) else str(final_status_code)
        print(f"INFO: ContentRewriteCrewManager run finished in {processing_time_ms/1000:.2f} seconds. Status: {status_value}") # Retained

        return RewriteContentOutput(
            ai_rewritten_content_blocks=parsed_content_blocks,
            status_code=status_value,
            error_message=final_error_message,
            usage_metrics=usage_metrics_dict,
            processing_time_ms=processing_time_ms,
            trace_id=str(uuid.uuid4()), # Consider if a trace_id should be passed in or linked to rewrite_input
            original_request_data_snippet=str(self.rewrite_input)[:500] if self.rewrite_input else "N/A"
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