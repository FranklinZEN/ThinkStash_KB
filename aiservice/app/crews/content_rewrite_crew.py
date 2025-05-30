#!/usr/bin/env python
# coding: utf-8
"""
Defines the ContentRewriteCrew, responsible for orchestrating agents
to rewrite/summarize content based on the V2.6 plan.
"""

from crewai import Crew, Process, Task
from typing import List, Dict, Any, Optional

# Agent definitions
from aiservice.app.agents.content_rewrite_agents import ContentRewriteAgents

# Model imports
from aiservice.app.models.orchestration_models import ContentBlock # For reconstruction
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
        self.agents_factory = ContentRewriteAgents()

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
                "When using your 'Optimized LLM Interaction Tool' for this task, you MUST set the 'temperature' parameter to 0.3 and the 'max_tokens' parameter to 1000."
            ),
            expected_output=(
                "A single string containing the concise summary of the text, with image placeholders if applicable."
            ),
            agent=summarization_agent,
            tools=[self.agents_factory.optimized_llm_tool]
        )

        task_reconstruct_output = Task(
            description=(
                "Your SOLE and ONLY task is to use the 'Fast Content Block Processor' tool. You MUST NOT attempt to generate the list of dictionaries yourself. "
                "The tool will handle the entire reconstruction process. "
                "To do this, you need to correctly identify and pass the required inputs to the tool: "
                "1. 'operation': You MUST set this to 'reconstruct_content_from_summary'. "
                "2. 'summarized_text': This is the direct string output you received as input from the 'Expert Summarizer' task (the previous task's result). "
                "3. 'image_metadata_list': This is the 'essential_image_metadata' list of dictionaries, which was provided as an initial input to the crew and is available to you as:\n\n'{essential_image_metadata}'\n\n "
                "4. 'content_blocks': You MUST pass an empty list ([]) for this argument. "
                "Your action MUST be to call this tool with these exact parameters. The tool's direct return value will be the final output for this task. Do not add, remove, or modify anything from the tool's output."
            ),
            expected_output=(
                "The direct, unaltered Python list of dictionaries returned by the 'Fast Content Block Processor' tool's 'reconstruct_content_from_summary' operation. "
                "Each dictionary in the list must conform to the Pydantic 'ContentBlock' model structure."
            ),
            agent=output_constructor_agent,
            context=[task_summarize_content],
            # tools=[self.agents_factory.content_processor_tool] # Explicitly specifying agent's tools here can sometimes help if implicit isn't working
        )

        content_rewrite_crew = Crew(
            agents=[summarization_agent, output_constructor_agent],
            tasks=[task_summarize_content, task_reconstruct_output],
            process=Process.sequential,
            verbose=True,
        )
        return content_rewrite_crew

    def run(self) -> RewriteContentOutput:
        """Runs the Content Rewrite Crew and returns the structured output."""

        # --- Direct Data Preparation --- 
        all_text_parts = []
        essential_image_metadata_list = []
        for block in self.rewrite_input.content_blocks_to_rewrite:
            if block.type == "text" and block.content:
                all_text_parts.append(block.content)
            elif block.type == "list" and block.items: # Assuming items in a list are strings for now
                for item in block.items:
                    if isinstance(item, str):
                        all_text_parts.append(item)
            elif block.type == "image":
                # Extract necessary image metadata for the SummarizationAgent and OutputConstructorAgent
                # The OutputConstructorAgent's tool will need enough to reconstruct the image block
                img_meta = {
                    "image_id_ref": block.image_id_ref,
                    "gcs_url": block.gcs_url,
                    "alt_text": block.alt_text,
                    "caption": block.caption,
                    "llm_description": block.llm_description, # Though likely None at this stage for original blocks
                    "width": block.width,
                    "height": block.height
                    # Add any other fields from ContentBlock that are essential for reconstruction by the tool
                }
                essential_image_metadata_list.append(img_meta)
        
        concatenated_text_for_summarization = "\n\n".join(all_text_parts)
        print(f"DEBUG: Preprocessed concatenated text length: {len(concatenated_text_for_summarization)}")
        print(f"DEBUG: Preprocessed essential image metadata count: {len(essential_image_metadata_list)}")
        # --- End Direct Data Preparation ---

        crew = self.setup_crew(concatenated_text_for_summarization, essential_image_metadata_list)
        
        # The crew_inputs should now directly map to what the first task (task_summarize_content) expects,
        # plus any inputs needed by subsequent tasks that aren't outputs of previous tasks.
        crew_inputs = {
            'concatenated_text': concatenated_text_for_summarization,          # For task_summarize_content
            'essential_image_metadata': essential_image_metadata_list,      # For task_summarize_content & task_reconstruct_output
        }

        print(f"DEBUG: Crew Inputs being passed to kickoff: {crew_inputs}")

        # The result of crew.kickoff() should be the output of the *last* task in a sequential crew.
        # In our case, task_reconstruct_output should return a list of dicts.
        crew_result = crew.kickoff(inputs=crew_inputs)

        raw_output_from_last_task = None # Initialize
        if crew_result and crew_result.tasks_output and len(crew_result.tasks_output) > 0:
            last_task_output = crew_result.tasks_output[-1]
            
            # Try agent_output first, as it might hold the direct structured output from the agent's execution
            if hasattr(last_task_output, 'agent_output') and last_task_output.agent_output is not None:
                raw_output_from_last_task = last_task_output.agent_output
            # Else, try exported_output (for structured data like list/dict)
            elif hasattr(last_task_output, 'exported_output') and last_task_output.exported_output is not None:
                raw_output_from_last_task = last_task_output.exported_output
            # Else, try raw_output (often a string, potentially JSON)
            elif hasattr(last_task_output, 'raw_output') and last_task_output.raw_output is not None:
                raw_output_from_last_task = last_task_output.raw_output
            # Else, try the 'output' attribute as another common place for the final result
            elif hasattr(last_task_output, 'output') and last_task_output.output is not None:
                raw_output_from_last_task = last_task_output.output
            # If none of the above yielded a result, raw_output_from_last_task remains None.

        # Ensure raw_output_from_last_task is what we expect (list of dicts)
        if isinstance(raw_output_from_last_task, list) and all(isinstance(item, dict) for item in raw_output_from_last_task):
            final_content_blocks = []
            for item_dict in raw_output_from_last_task:
                try:
                    # The tool's reconstruct operation already returns model_dump(mode='json'),
                    # so these items should be dicts that ContentBlock can parse.
                    final_content_blocks.append(ContentBlock(**item_dict))
                except Exception as e:
                    print(f"Warning: Could not convert item dictionary to ContentBlock: {item_dict}. Error: {e}")
            
            return RewriteContentOutput(
                ai_rewritten_content_blocks=final_content_blocks,
                status_code="success"
            )
        # Handling cases where the output might be a string (e.g. if agent returns raw string instead of parsed list)
        # or other unexpected types.
        elif isinstance(raw_output_from_last_task, str):
            # Attempt to parse if it's a JSON string list of dicts
            import json
            try:
                parsed_list = json.loads(raw_output_from_last_task)
                if isinstance(parsed_list, list) and all(isinstance(item, dict) for item in parsed_list):
                    final_content_blocks = []
                    for item_dict in parsed_list:
                        try:
                            final_content_blocks.append(ContentBlock(**item_dict))
                        except Exception as e:
                            print(f"Warning: Could not convert item dictionary (from JSON string) to ContentBlock: {item_dict}. Error: {e}")
                    return RewriteContentOutput(
                        ai_rewritten_content_blocks=final_content_blocks,
                        status_code="success_parsed_json_string"
                    )
                else:
                    error_msg = f"Crew finished. Output was a string, but not a valid JSON list of dictionaries. Output: {raw_output_from_last_task}"
                    print(error_msg)
                    return RewriteContentOutput(
                        ai_rewritten_content_blocks=[],
                        status_code="error_string_not_parsable_list",
                        error_message=error_msg
                    )
            except json.JSONDecodeError:
                error_msg = f"Crew finished. Output was a string, but not valid JSON. Output: {raw_output_from_last_task}"
                print(error_msg)
                return RewriteContentOutput(
                    ai_rewritten_content_blocks=[],
                    status_code="error_string_not_json",
                    error_message=error_msg
                )
        else:
            error_msg = (
                f"Crew finished, but the final output from the last task was not a list of dictionaries as expected. "
                f"Type received: {type(raw_output_from_last_task)}. "
                f"Last Task Output object: {last_task_output if 'last_task_output' in locals() else 'Not available'}. "
                f"CrewOutput object: {crew_result}"
            )
            print(error_msg)
            return RewriteContentOutput(
                ai_rewritten_content_blocks=[],
                status_code="error_unexpected_output_type",
                error_message=error_msg
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