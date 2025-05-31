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
import dataclasses
import ast

# Agent definitions
from aiservice.app.agents.content_rewrite_agents import ContentRewriteAgents

# Model imports
from aiservice.app.models.orchestration_models import ContentBlock, OrchestrationStatusCodeEnum
from aiservice.app.models.insight_generation_models import RewriteContentInput, RewriteContentOutput


class ContentRewriteCrewManager:
    """Manages the creation and execution of the Content Rewrite Crew."""

    def __init__(self, rewrite_input: RewriteContentInput):
        """
        Initializes the crew manager with the necessary input data.
        Args:
            rewrite_input: The input data containing content_blocks and optional metadata.
        """
        self.rewrite_input = rewrite_input
        # Extract user_id, providing a default if not available
        self.user_id = "default_user_id_manager"
        if self.rewrite_input.document_metadata and self.rewrite_input.document_metadata.user_id:
            self.user_id = self.rewrite_input.document_metadata.user_id
        elif self.rewrite_input.user_id: # Fallback to user_id on RewriteContentInput if present
            self.user_id = self.rewrite_input.user_id
        
        print(f"INFO: ContentRewriteCrewManager initialized with user_id: {self.user_id}") # Retained: Useful high-level info
        self.agents_factory = ContentRewriteAgents(user_id=self.user_id) # Pass user_id

    def setup_crew(self, concatenated_text: str, essential_image_metadata: List[Dict[str, Any]]) -> Crew:
        """
        Defines and configures the Content Rewrite Crew, its agents, and tasks.
        Args:
            concatenated_text: The pre-processed text for summarization.
            essential_image_metadata: The pre-processed list of image metadata.
        """
        # Get agents
        summarization_agent = self.agents_factory.summarization_agent()
        output_constructor_agent = self.agents_factory.output_constructor_agent()

        # Define Tasks
        task_summarize_content = Task(
            description=(
                "You are provided with 'concatenated_text':\\n\\n'{concatenated_text}'\\n\\nAnd 'essential_image_metadata':\\n\\n'{essential_image_metadata}'\\n\\n" # Dynamically injected
                "Generate a concise summary of the 'concatenated_text'. If images from 'essential_image_metadata' "
                "are contextually important for the summary, refer to them using placeholders like '[IMAGE: <image_id_ref_value>]' or '[IMAGE: <gcs_url_value>]'. "
                "The image_id_ref_value or gcs_url_value should correspond to the 'image_id_ref' or 'gcs_url' present in the 'essential_image_metadata'."
                "The summary should be a single string of well-written text. "
                "When using your 'Optimized LLM Interaction Tool' for this task, you MUST set the 'temperature' parameter to 0.0 and the 'max_tokens' parameter to 1000."
            ),
            expected_output=(
                "A single string containing the concise summary of the text, with image placeholders if applicable."
            ),
            agent=summarization_agent,
            tools=[self.agents_factory.optimized_llm_tool]
        )

        task_reconstruct_output = Task(
            description=(
                "CRITICAL INSTRUCTION: You MUST use the 'FastContentBlockProcessorTool'.\n"
                "You have received 'summarized_text' from the previous task. You also have 'essential_image_metadata' from the crew's initial inputs (available as '{essential_image_metadata}').\n"
                "To successfully use the tool, you MUST construct your tool input with these exact argument names and values:"
                "1. 'operation': EXACTLY the string 'reconstruct_content_from_summary'."
                "2. 'summarized_text': The 'summarized_text' content you received."
                "3. 'image_metadata_list': The 'essential_image_metadata' list."
                "Your entire output for this task MUST be the direct, unaltered result from this single tool call. NO OTHER ACTIONS OR OUTPUTS."
            ),
            expected_output=(
                "The direct, unaltered Python list of dictionaries returned by the 'Fast Content Block Processor' tool's 'reconstruct_content_from_summary' operation. "
                "Each dictionary in the list must conform to the Pydantic 'ContentBlock' model structure."
            ),
            agent=output_constructor_agent,
            context=[task_summarize_content],
            tools=[self.agents_factory.content_processor_tool] # Explicitly specifying agent's tools here can sometimes help if implicit isn't working
        )

        content_rewrite_crew = Crew(
            agents=[summarization_agent, output_constructor_agent],
            tasks=[task_summarize_content, task_reconstruct_output],
            process=Process.sequential,
            verbose=True,
        )
        return content_rewrite_crew

    def _try_json_parse(self, data_str: str) -> Any:
        try:
            # Attempt to parse as a Python literal first (handles single quotes, etc.)
            # Safely evaluates if it's a Python literal like list, dict, tuple, string, number, bool, None.
            # print(f"DEBUG: _try_json_parse attempting ast.literal_eval for: {data_str[:200]}...")
            evaluated_data = ast.literal_eval(data_str)
            # print(f"DEBUG: ast.literal_eval successful. Type: {type(evaluated_data)}")
            return evaluated_data
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as e_ast:
            # ast.literal_eval failed, likely not a simple Python literal or too complex.
            # This can happen if it's actual JSON (with null, true, false) or malformed.
            # print(f"DEBUG: ast.literal_eval failed: {e_ast}. Falling back to json.loads for: {data_str[:200]}...")
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                # Try to find JSON array within a potentially larger string
                match = re.search(r'(\\[.*?\\])', data_str, re.DOTALL) # Made regex non-greedy for the content within brackets
                if match:
                    json_like_part = match.group(1)
                    # print(f"DEBUG: Found JSON-like part with regex: {json_like_part[:200]}...")
                    try:
                        return json.loads(json_like_part)
                    except json.JSONDecodeError as e_inner:
                        print(f"WARNING: Found JSON-like part but failed to parse with json.loads: {json_like_part[:200]}. Error: {e_inner}") # Retained: Important warning
                        return None
                print(f"WARNING: Failed to decode with json.loads directly and no parsable array found via regex from string: {data_str[:200]}") # Retained: Important warning
                return None
            except Exception as e_json_other: # Catch other potential errors from json.loads
                print(f"ERROR: Unexpected error during json.loads fallback: {e_json_other}. Data: {data_str[:200]}") # Retained: Important error
                return None
        except Exception as e_outer: # Catch any other unexpected errors
            print(f"ERROR: Unexpected error in _try_json_parse: {e_outer}. Data: {data_str[:200]}") # Retained: Important error
            return None

    def safe_parse_to_content_blocks(self, data: Any, field_name: str) -> List[ContentBlock]:
        """
        Safely parses data (expected to be a list of dicts) into a List[ContentBlock].
        Logs errors if parsing or validation fails.
        Args:
            data: The data to parse, ideally a list of dictionaries.
            field_name: A descriptive name of the field being parsed (for logging).
        Returns:
            A list of ContentBlock objects, or an empty list if parsing/validation fails.
        """
        parsed_blocks: List[ContentBlock] = []
        if not isinstance(data, list):
            print(f"ERROR: Data for '{field_name}' is not a list, but type {type(data)}. Cannot parse into ContentBlocks.") # Retained: Important error
            return []

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                print(f"ERROR: Item {i} in '{field_name}' is not a dictionary, but type {type(item)}. Skipping.") # Retained: Important error
                continue
            try:
                # Ensure block_id is present, generate if missing (as per ContentBlock model default_factory)
                if 'block_id' not in item or item['block_id'] is None:
                    item['block_id'] = str(uuid.uuid4())
                
                # Ensure 'type' is present, default to 'text' if missing and content is present
                if 'type' not in item or item['type'] is None:
                    if 'content' in item and isinstance(item['content'], str):
                         item['type'] = 'text' # Sensible default if text content exists
                    else:
                        print(f"WARNING: Item {i} in '{field_name}' is missing 'type' and cannot infer. Skipping. Item: {str(item)[:100]}") # Retained: Important warning
                        continue


                # Attempt to create ContentBlock, this will validate all fields
                block = ContentBlock(**item)
                parsed_blocks.append(block)
            except Exception as e: # Catch Pydantic ValidationError and other potential errors
                print(f"ERROR: Failed to validate item {i} in '{field_name}' as ContentBlock. Error: {e}. Item: {str(item)[:200]}") # Retained: Important error
        
        if data and not parsed_blocks:
             print(f"WARNING: Input data for '{field_name}' was non-empty but resulted in zero successfully parsed ContentBlocks.") # Retained: Important warning
        elif not data:
             # print(f"INFO: Input data for '{field_name}' was empty or None. Returning empty list of ContentBlocks.") # Optional info, can be removed
             pass

        return parsed_blocks

    def run(self) -> RewriteContentOutput:
        start_time = time.time()
        print(f"INFO: ContentRewriteCrewManager run initiated for user_id: {self.user_id}") # Retained: Useful high-level info

        # 1. Pre-process input: Concatenate text and extract essential image metadata
        concatenated_text = ""
        essential_image_metadata: List[Dict[str, Any]] = []
        text_parts = []
        for block in self.rewrite_input.content_blocks_to_rewrite:
            if block.type == "text" and block.content:
                text_parts.append(block.content)
            elif block.type == "image" and block.image_id_ref:
                # Extract only essential fields for the summarization context to avoid excessive token usage
                essential_meta = {
                    "image_id_ref": block.image_id_ref,
                    "gcs_url": block.gcs_url, # Keep GCS URL for potential reference
                    "alt_text": block.alt_text,
                    "caption": block.caption,
                    "llm_description": block.llm_description, # If available from previous steps
                    "width": block.width,
                    "height": block.height
                }
                # Filter out None values from essential_meta to keep it clean
                essential_image_metadata.append({k: v for k, v in essential_meta.items() if v is not None})
        concatenated_text = "\n\n".join(text_parts)

        # print(f"DEBUG: Preprocessed concatenated text length: {len(concatenated_text)}")
        # print(f"DEBUG: Preprocessed essential image metadata count: {len(essential_image_metadata)}")

        crew_inputs = {
            "concatenated_text": concatenated_text,
            "essential_image_metadata": essential_image_metadata,
            "original_content_blocks_json_string": self.rewrite_input.original_content_blocks_json_string
        }
        # Truncate for logging if too long
        loggable_crew_inputs = {
            k: (v[:500] + '...' if isinstance(v, str) and len(v) > 500 else v)
            for k, v in crew_inputs.items()
        }
        # print(f"DEBUG: Crew Inputs being passed to kickoff: {loggable_crew_inputs}")

        # 2. Setup and run the Crew
        crew = self.setup_crew(concatenated_text, essential_image_metadata)
        crew_result = None
        final_agent_output = None
        parsed_content_blocks: List[ContentBlock] = []
        final_status_code = OrchestrationStatusCodeEnum.ERROR_UNKNOWN # Default to error
        final_error_message = "Crew execution did not start or complete as expected."

        try:
            crew_result = crew.kickoff(inputs=crew_inputs)
        except Exception as e:
            print(f"ERROR: Exception during crew.kickoff(): {e}") # Retained: Important error
            final_status_code = OrchestrationStatusCodeEnum.ERROR_CREW_EXECUTION_FAILED
            final_error_message = f"Exception during crew kickoff: {str(e)}"
            # Construct usage_metrics_dict here as well for the error case
            # as crew object might exist even if kickoff fails partially or metrics are available.
            usage_metrics_dict_error_case: Optional[Dict[str, Any]] = None
            if crew and hasattr(crew, 'usage_metrics') and crew.usage_metrics:
                um_error = crew.usage_metrics
                # print(f"DEBUG: [Error Path] Converting crew.usage_metrics. Type: {type(um_error)}, Value: {um_error}")
                temp_metrics_dict_error = {}
                known_attrs_error = ['total_tokens', 'prompt_tokens', 'completion_tokens', 'successful_requests']
                for attr_err in known_attrs_error:
                    if hasattr(um_error, attr_err):
                        temp_metrics_dict_error[attr_err] = getattr(um_error, attr_err)
                    else:
                        pass # Attribute not found, do nothing
                if isinstance(um_error, dict):
                    usage_metrics_dict_error_case = {**um_error, **temp_metrics_dict_error}
                elif temp_metrics_dict_error:
                    usage_metrics_dict_error_case = temp_metrics_dict_error
                else:
                    try:
                        usage_metrics_dict_error_case = vars(um_error)
                    except TypeError:
                        usage_metrics_dict_error_case = None
                if not isinstance(usage_metrics_dict_error_case, dict) and usage_metrics_dict_error_case is not None:
                    usage_metrics_dict_error_case = None # Ensure it's None if conversion is problematic
            
            end_time_error = time.time()
            processing_time_ms_error = (end_time_error - start_time) * 1000
            return RewriteContentOutput(
                ai_rewritten_content_blocks=[],
                status_code=final_status_code.value if isinstance(final_status_code, OrchestrationStatusCodeEnum) else str(final_status_code),
                error_message=final_error_message,
                usage_metrics=usage_metrics_dict_error_case,
                processing_time_ms=processing_time_ms_error,
                trace_id=str(uuid.uuid4()),
                original_request_data_snippet=str(self.rewrite_input)[:500]
            )

        # --- Start of Moved Usage Metrics Conversion Block ---
        usage_metrics_dict: Optional[Dict[str, Any]] = None
        if crew_result: # Ensure crew_result exists before trying to access usage_metrics from it or its crew
            actual_crew_object_for_metrics = getattr(crew_result, 'crew', crew) # Prefer crew from CrewOutput if available, else fallback to the one we ran
            if actual_crew_object_for_metrics and hasattr(actual_crew_object_for_metrics, 'usage_metrics') and actual_crew_object_for_metrics.usage_metrics:
                um = actual_crew_object_for_metrics.usage_metrics
                # print(f"DEBUG: [Primary Path] Converting crew.usage_metrics. Type: {type(um)}, Value: {um}")
                # print(f"DEBUG: [Primary Path] Attributes of um: {dir(um)}")

                temp_metrics_dict = {}
                known_attrs = ['total_tokens', 'prompt_tokens', 'completion_tokens', 'successful_requests']
                
                for attr in known_attrs:
                    if hasattr(um, attr):
                        value = getattr(um, attr)
                        temp_metrics_dict[attr] = value
                        # print(f"DEBUG: [Primary Path] Added to metrics dict: {{'{attr}': {value} (type: {type(value)})}}")
                    else:
                        # print(f"DEBUG: [Primary Path] Attribute '{attr}' not found in usage_metrics object.")
                        pass # Attribute not found, do nothing
                
                if isinstance(um, dict):
                    # print("DEBUG: [Primary Path] crew.usage_metrics is already a dict. Merging with known_attrs if any were missed.")
                    usage_metrics_dict = {**um, **temp_metrics_dict}
                elif temp_metrics_dict:
                    usage_metrics_dict = temp_metrics_dict
                else:
                    # print(f"WARNING: [Primary Path] Could not convert usage_metrics of type {type(um)} to dict using known attributes or direct dict check. Trying vars().")
                    try:
                        usage_metrics_dict = vars(um)
                        # print(f"DEBUG: [Primary Path] vars(um) result: {usage_metrics_dict}")
                    except TypeError:
                        print(f"ERROR: [Primary Path] vars(um) failed for type {type(um)}. usage_metrics will be None.")
                        usage_metrics_dict = None
                
                # print(f"DEBUG: [Primary Path] Final usage_metrics_dict: {usage_metrics_dict}, Type: {type(usage_metrics_dict)}")
                
                if not isinstance(usage_metrics_dict, dict) and usage_metrics_dict is not None:
                    print(f"CRITICAL WARNING: [Primary Path] usage_metrics_dict is NOT a dict after conversion attempts. Type: {type(usage_metrics_dict)}. Setting to None.") # Retained: Critical warning
                    usage_metrics_dict = None
            else:
                # print("DEBUG: [Primary Path] No usage_metrics found on crew_result.crew or the initial crew object.")
                pass
        else:
            # print("DEBUG: [Primary Path] crew_result is None, skipping usage_metrics conversion.")
            pass
        # --- End of Moved Usage Metrics Conversion Block ---

        if crew_result:
            # print(f"DEBUG: Full crew_result object (type {type(crew_result)}): {str(crew_result)[:1000]}...")
            crew_result_raw = getattr(crew_result, 'raw', None)
            # if crew_result_raw:
                # print(f"DEBUG: crew_result.raw (type {type(crew_result_raw)}): {str(crew_result_raw)[:1000]}...")
            # else:
                # print("DEBUG: crew_result has no .raw attribute or it is empty.")

            # Attempt to get final_agent_output directly from crew_result.raw
            if isinstance(crew_result_raw, list):
                # print("INFO: Using crew_result.raw directly as it is a list.")
                final_agent_output = crew_result_raw
            elif isinstance(crew_result_raw, str):
                # print(f"INFO: crew_result.raw is a string. Attempting to parse: {crew_result_raw[:500]}...")
                parsed_raw_output = self._try_json_parse(crew_result_raw)
                if isinstance(parsed_raw_output, list):
                    final_agent_output = parsed_raw_output
                    # print("INFO: Successfully parsed crew_result.raw string into a list.")
                else:
                    # print(f"WARNING: Failed to parse crew_result.raw string into a list. Parsed data type: {type(parsed_raw_output)}")
                    pass
            
            # Fallback to tasks_output ONLY if crew_result.raw didn't yield a list for final_agent_output
            if final_agent_output is None:
                if crew_result.tasks_output and len(crew_result.tasks_output) > 0:
                    print("INFO: crew_result.raw did not yield a list. Falling back to inspecting tasks_output.") # Retained: Useful info if this path is taken
                    last_task_output = crew_result.tasks_output[-1]
                    # print(f"DEBUG: last_task_output (type {type(last_task_output)}): {str(last_task_output)[:1000]}...")

                    raw_output_data = getattr(last_task_output, 'raw_output', None)
                    pydantic_output_data = getattr(last_task_output, 'pydantic_output', None)
                    exported_output_data = getattr(last_task_output, 'exported_output', None)
                    agent_output_data = getattr(last_task_output, 'agent_output', None)
                    output_data = getattr(last_task_output, 'output', None)

                    # print(f"DEBUG: last_task_output.raw_output type: {type(raw_output_data)}, content (first 200): {str(raw_output_data)[:200]}")
                    # print(f"DEBUG: last_task_output.pydantic_output type: {type(pydantic_output_data)}, content (first 200): {str(pydantic_output_data)[:200]}")
                    # print(f"DEBUG: last_task_output.exported_output type: {type(exported_output_data)}, content (first 200): {str(exported_output_data)[:200]}")
                    # print(f"DEBUG: last_task_output.agent_output type: {type(agent_output_data)}, content (first 200): {str(agent_output_data)[:200]}")
                    # print(f"DEBUG: last_task_output.output type: {type(output_data)}, content (first 200): {str(output_data)[:200]}")

                    if isinstance(pydantic_output_data, list):
                        final_agent_output = pydantic_output_data
                        # print("INFO: Using pydantic_output from last task.")
                    elif isinstance(exported_output_data, list):
                        final_agent_output = exported_output_data
                        # print("INFO: Using exported_output from last task.")
                    elif isinstance(agent_output_data, list):
                        final_agent_output = agent_output_data
                        # print("INFO: Using agent_output from last task.")
                    elif isinstance(raw_output_data, list):
                        final_agent_output = raw_output_data
                        # print("INFO: Using raw_output from last task (as list).")
                    elif isinstance(raw_output_data, str):
                        # print(f"INFO: Attempting to parse raw_output_data (string from last task): {raw_output_data[:500]}...")
                        parsed_data = self._try_json_parse(raw_output_data)
                        if isinstance(parsed_data, list):
                            final_agent_output = parsed_data
                            # print("INFO: Successfully parsed raw_output_data string (from last task) into a list.")
                        else:
                            # print(f"WARNING: Failed to parse raw_output_data string (from last task) into a list. Parsed data type: {type(parsed_data)}")
                            pass
                    elif isinstance(output_data, list):
                        final_agent_output = output_data
                        # print("INFO: Using output_data from last task (as list).")
                    elif isinstance(output_data, str):
                        # print(f"INFO: Attempting to parse output_data (string from last task): {output_data[:500]}...")
                        parsed_data = self._try_json_parse(output_data)
                        if isinstance(parsed_data, list):
                            final_agent_output = parsed_data
                            # print("INFO: Successfully parsed output_data string (from last task) into a list.")
                        else:
                            # print(f"WARNING: Failed to parse output_data string (from last task) into a list. Parsed data type: {type(parsed_data)}")
                            pass
                    else: # Fallback if no specific attribute yielded a list
                        final_output_attr_val = getattr(last_task_output, 'output', None)
                        if isinstance(final_output_attr_val, str):
                            # print(f"INFO: Attempting to parse last_task_output.output (string attribute): {final_output_attr_val[:500]}...")
                            parsed_data = self._try_json_parse(final_output_attr_val)
                            if isinstance(parsed_data, list):
                                final_agent_output = parsed_data
                                # print("INFO: Successfully parsed last_task_output.output string attribute into a list.")
                                pass
                            else:
                                # print(f"WARNING: Failed to parse last_task_output.output string attribute. Parsed data type: {type(parsed_data)}")
                                pass
                        elif isinstance(final_output_attr_val, list):
                            final_agent_output = final_output_attr_val
                            # print("INFO: Using last_task_output.output directly as it is a list attribute.")
                            pass # Added pass
                else: # No crew_result.tasks_output or it's empty, and crew_result.raw processing failed to produce a list
                    # print("INFO: Neither crew_result.raw (after parsing attempts) nor tasks_output yielded a usable list. Cannot determine final agent output.")
                    pass
            # If final_agent_output is still None here, it means no valid output was found through any method.
            # The existing error handling below will catch this.


            if final_agent_output is None or not isinstance(final_agent_output, list):
                final_status_code = OrchestrationStatusCodeEnum.ERROR_UNEXPECTED_OUTPUT_TYPE
                error_msg_detail = (
                    f"Crew finished, but the final processed output was not a list of dictionaries as expected. "
                    f"Final processed output type: {type(final_agent_output)}. Final processed output (first 1000 chars): {str(final_agent_output)[:1000]}. "
                    f"Checked crew_result.raw and relevant attributes of last_task_output if available."
                )
                print(f"ERROR: Error in crew execution: {error_msg_detail}") # Retained: Important error
                final_error_message = error_msg_detail
                # This return was part of the user's snippet, effectively ending processing here on error.
                end_time_task_error = time.time()
                processing_time_ms_task_error = (end_time_task_error - start_time) * 1000
                return RewriteContentOutput(
                    ai_rewritten_content_blocks=[],
                    status_code=final_status_code.value if isinstance(final_status_code, OrchestrationStatusCodeEnum) else str(final_status_code), # Corrected status_code
                    error_message=final_error_message,
                    usage_metrics=usage_metrics_dict, # Use already converted dict
                    processing_time_ms=processing_time_ms_task_error,
                    trace_id=str(uuid.uuid4()),
                    original_request_data_snippet=str(self.rewrite_input)[:500]
                )
            
            # If we reach here, final_agent_output is a list (could be empty)
            # print(f"INFO: Final agent output determined to be a list with {len(final_agent_output)} items.")
            parsed_content_blocks = self.safe_parse_to_content_blocks(final_agent_output, "ai_rewritten_content_blocks")
            
            if not parsed_content_blocks and final_agent_output: # It was a non-empty list, but parsing failed
                final_status_code = OrchestrationStatusCodeEnum.ERROR_CONTENT_BLOCK_VALIDATION
                final_error_message = "Crew output was a list of dictionaries, but failed Pydantic validation into ContentBlocks."
                print(f"ERROR: {final_error_message} Input list (first item): {str(final_agent_output[0])[:500] if final_agent_output else 'Empty List'}") # Retained: Important error
            elif not parsed_content_blocks and not final_agent_output: # It was an empty list, parsing resulted in empty
                 # print("INFO: Crew returned an empty list of content blocks, successfully processed as such.")
                 final_status_code = OrchestrationStatusCodeEnum.SUCCESS
                 final_error_message = None
            elif parsed_content_blocks: # Successfully parsed non-empty list
                # print(f"INFO: Successfully parsed {len(parsed_content_blocks)} content blocks from crew output.")
                final_status_code = OrchestrationStatusCodeEnum.SUCCESS
                final_error_message = None
            else: # Should be covered, but as a fallback
                final_status_code = OrchestrationStatusCodeEnum.ERROR_UNKNOWN 
                final_error_message = "Unknown error after attempting to parse final agent output."
                print(f"ERROR: {final_error_message} Final agent output: {str(final_agent_output)[:500]}") # Retained: Important error

        elif not crew_result: # If crew_result itself is None from the kickoff exception
            # final_status_code and final_error_message are already set by the except block
            pass
        else: # No crew_result.tasks_output or it's empty
            final_status_code = OrchestrationStatusCodeEnum.ERROR_NO_OUTPUT_FROM_CREW
            final_error_message = "Crew execution did not produce any usable task outputs."
            print(f"ERROR: {final_error_message}. Crew Result: {str(crew_result)[:500]}") # Retained: Important error, truncated crew_result
        
        end_time = time.time()
        processing_time_ms = (end_time - start_time) * 1000
        print(f"INFO: ContentRewriteCrewManager run finished in {processing_time_ms/1000:.2f} seconds. Status: {final_status_code}") # Retained: Useful high-level info

        # 4. Construct and return the output Pydantic model
        return RewriteContentOutput(
            ai_rewritten_content_blocks=parsed_content_blocks,
            status_code=final_status_code.value if isinstance(final_status_code, OrchestrationStatusCodeEnum) else str(final_status_code),
            error_message=final_error_message,
            usage_metrics=usage_metrics_dict, # Use the converted dict
            processing_time_ms=processing_time_ms,
            trace_id=str(uuid.uuid4()) # Generate a new trace_id for this operation
        )

# Example Usage (for direct testing if needed)
if __name__ == "__main__":
    from aiservice.app.models.orchestration_models import ContentBlock # For sample data
    from aiservice.app.models.pipeline_models import DocumentMetadata # For sample data
    import datetime

    print("Setting up sample data for ContentRewriteCrewManager...")
    sample_doc_metadata = DocumentMetadata(
        document_id="sample_doc_123",
        source_identifier="internal_sample",
        source_type="text",
        extracted_at=datetime.datetime.utcnow()
    )
    sample_content_blocks = [
        ContentBlock(block_id="cb1", type="text", content="This is the first paragraph of a document we want to summarize. It has some interesting points."),
        ContentBlock(block_id="cb2", type="image", image_id_ref="img1", gcs_url="gs://example/image1.jpg", alt_text="An illustrative image"),
        ContentBlock(block_id="cb3", type="text", content="The second paragraph elaborates further, providing more details and context. We hope the summary captures this."),
        ContentBlock(block_id="cb4", type="list", items=["Point one", "Point two", "Point three"], ordered=False)
    ]

    rewrite_input_data = RewriteContentInput(
        content_blocks_to_rewrite=sample_content_blocks,
        document_metadata=sample_doc_metadata
    )

    print("Initializing ContentRewriteCrewManager...")
    crew_manager = ContentRewriteCrewManager(rewrite_input=rewrite_input_data)

    print("Running ContentRewriteCrew...")
    # Note: Running this will make actual LLM calls if GEMINI_API_KEY is set and valid.
    # Ensure your .env and settings are configured.
    output = crew_manager.run()

    print("\n--- Crew Output ---")
    if output.status_code == "success":
        print("Rewrite successful!")
        for i, block in enumerate(output.ai_rewritten_content_blocks):
            print(f"Block {i+1} (Type: {block.type}):")
            if block.type == "text":
                print(f"  Content: {block.content}")
            elif block.type == "image":
                print(f"  Image GCS URL: {block.gcs_url}")
                print(f"  Alt Text: {block.alt_text}")
            # Add more types as needed
    else:
        print(f"Rewrite failed. Status: {output.status_code}")
        print(f"Error: {output.error_message}")

    print("\n--- Crew Execution Metrics (Example) ---")
    # crew = crew_manager.setup_crew() # Re-setup to access usage_metrics if needed after kickoff
    # print(f"Total Tokens Used: {crew.usage_metrics.get('total_tokens', 'N/A')}") 
    # Note: Accessing usage_metrics might require crew to be run in a way that preserves it or specific versions of CrewAI.
    # The `kickoff` method might consume the crew instance or its metrics in some versions.
    # If detailed metrics are crucial, refer to current CrewAI documentation for best practices. 