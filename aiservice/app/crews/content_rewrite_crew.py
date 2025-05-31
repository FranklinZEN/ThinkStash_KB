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
        # Extract user_id, providing a default if not available
        self.user_id = "default_user_id_manager"
        if self.rewrite_input.document_metadata and self.rewrite_input.document_metadata.user_id:
            self.user_id = self.rewrite_input.document_metadata.user_id
        elif hasattr(self.rewrite_input, 'user_id') and self.rewrite_input.user_id: # Fallback to user_id on RewriteContentInput if present
            self.user_id = self.rewrite_input.user_id
        
        print(f"INFO: ContentRewriteCrewManager initialized with user_id: {self.user_id}, document_id: {self.document_id_to_pass}")
        self.agents_factory = ContentRewriteAgents(user_id=self.user_id) # Pass user_id
        self.crew: Optional[Crew] = None # To store the initialized crew

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
                The summary should be a single string of well-written text.
                When using your 'Optimized LLM Interaction Tool' for this task, you MUST set the 'temperature' parameter to {self.agents_factory.summarizer_temperature} and the 'max_tokens' parameter to {self.agents_factory.summarizer_max_tokens}.
                """),
            expected_output="A concise textual summary of the input content, potentially including image references like '[IMAGE: <image_id_ref>]'.",
            agent=summarization_agent,
            tools=[self.agents_factory.optimized_llm_tool]
        )

        task_reconstruct_output = Task(
            description=(
                "Reconstruct content blocks using the 'FastContentBlockProcessorTool'.\\n"
                "Operation: 'reconstruct_content_from_summary'.\\n"
                "Summarized text: Use the output from the 'task_summarize_content'.\\n"
                "Image metadata list (JSON string): {{reconstructor_image_metadata_list_json}}\\n"
                "Document ID: {{reconstructor_document_id}}\\n"
                "Your output for this task MUST be the direct, unaltered result from the tool call."
            ),
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
        print(f"INFO: ContentRewriteCrewManager run initiated for user_id: {self.user_id}") # Retained

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
                essential_meta = {
                    "image_id_ref": block.image_id_ref,
                    "gcs_url": block.gcs_url,
                    "alt_text": block.alt_text,
                    "caption": block.caption,
                    "llm_description": block.llm_description,
                    "width": block.width,
                    "height": block.height
                }
                essential_image_metadata.append({k: v for k, v in essential_meta.items() if v is not None})
        concatenated_text = "\\n\\n".join(text_parts)

        current_document_id = (
            self.rewrite_input.document_metadata.document_id
            if self.rewrite_input.document_metadata and self.rewrite_input.document_metadata.document_id
            else str(uuid.uuid4())
        )
        if not (self.rewrite_input.document_metadata and self.rewrite_input.document_metadata.document_id):
            print(f"WARNING: document_id not found in rewrite_input.document_metadata.document_id, using generated UUID: {current_document_id}")


        # 2. Setup the crew
        self.crew = self.setup_crew()

        # 3. Prepare the inputs for the crew.kickoff()
        crew_kickoff_inputs = {
            'concatenated_text': concatenated_text,
            'essential_image_metadata_for_summarizer_prompt': json.dumps(essential_image_metadata), # Use locally processed metadata
            'reconstructor_image_metadata_list_json': json.dumps(essential_image_metadata), # Use locally processed metadata, as JSON string
            'reconstructor_document_id': current_document_id
        }
        
        if self.verbose_level > 1:
            print(f"DEBUG ContentRewriteCrewManager: Kicking off crew with inputs (metadata potentially truncated for log):")
            print(f"  concatenated_text length: {len(crew_kickoff_inputs['concatenated_text'])}")
            print(f"  essential_image_metadata_for_summarizer_prompt: {crew_kickoff_inputs['essential_image_metadata_for_summarizer_prompt'][:200] if crew_kickoff_inputs['essential_image_metadata_for_summarizer_prompt'] else '[]'}...")
            # Log the new JSON string key
            print(f"  reconstructor_image_metadata_list_json: {crew_kickoff_inputs['reconstructor_image_metadata_list_json'][:200] if crew_kickoff_inputs.get('reconstructor_image_metadata_list_json') else '[]'}...")
            print(f"  reconstructor_document_id: {crew_kickoff_inputs['reconstructor_document_id']}")

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
            if crew_result_raw:
                if isinstance(crew_result_raw, list):
                    final_agent_output = crew_result_raw
                elif isinstance(crew_result_raw, str):
                    parsed_raw_output = self._try_json_parse(crew_result_raw)
                    if isinstance(parsed_raw_output, list):
                        final_agent_output = parsed_raw_output
                
                # Fallback to tasks_output if crew_result_raw didn't yield a list
                if (final_agent_output is None and 
                    hasattr(self.crew, 'tasks_output') and 
                    self.crew.tasks_output and 
                    len(self.crew.tasks_output) > 0):
                    print("INFO: crew_result_raw did not yield a list. Falling back to inspecting tasks_output.") # Retained
                    last_task_output = self.crew.tasks_output[-1]
                    
                    # Prioritize attributes that are more likely to contain the desired list structure
                    potential_outputs = [
                        getattr(last_task_output, 'pydantic_output', None),
                        getattr(last_task_output, 'exported_output', None),
                        getattr(last_task_output, 'agent_output', None),
                        getattr(last_task_output, 'raw_output', None), # Raw might be string or list
                        getattr(last_task_output, 'output', None)    # Generic output
                    ]

                    for out_candidate in potential_outputs:
                        if isinstance(out_candidate, list):
                            final_agent_output = out_candidate
                            break
                        elif isinstance(out_candidate, str):
                            parsed_data = self._try_json_parse(out_candidate)
                            if isinstance(parsed_data, list):
                                final_agent_output = parsed_data
                                break
                    
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
            else: # crew_result_raw is None or empty
                final_status_code = OrchestrationStatusCodeEnum.ERROR_NO_OUTPUT_FROM_CREW
                final_error_message = "Crew execution did not produce any raw result."
                print(f"ERROR: {final_error_message}") # Retained

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