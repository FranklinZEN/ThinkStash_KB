# Placeholder for TS-AI-Reconstruct-0: Main Orchestration & Input Triage Agent 

from crewai import Agent, Task
from typing import List, Type, Dict, Any, Optional
from pydantic import BaseModel

# Assuming tools are defined elsewhere and passed in, e.g., ContentTypeDetectionTool
# from app.tools.utility_tools import ContentTypeDetectionTool, DataStoreAccessTool

from app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock
from app.tools.utility_tools import ContentTypeDetectionTool, DataStoreAccessTool # Ensure DataStoreAccessTool is imported if OrchestrationAgent is to use it directly.

class OrchestrationAgent:
    """Manages the overall content processing workflow, including initial triage, routing, error handling, and output aggregation."""
    def __init__(self, content_type_detection_tool: ContentTypeDetectionTool, data_store_tool: DataStoreAccessTool):
        self.content_type_tool = content_type_detection_tool
        self.data_store_tool = data_store_tool # For use in execute_output_aggregation
        
        # Tools generally available to the CrewAI agent instance if it needs to use LLM for decisions
        agent_tools_for_crewai = [self.content_type_tool, self.data_store_tool] 
        self.agent_instance = self._create_agent_instance(agent_tools_for_crewai)

    def _create_agent_instance(self, configured_tools: List[BaseModel]) -> Agent:
        """Creates and returns a CrewAI Agent instance for the main orchestrator."""
        return Agent(
            role='Main Orchestration and Input Triage Agent for V2.4',
            goal='Orchestrate the CoreReconstructionCrew pipeline: validate input, route to acquisition agents based on source type and processing_level, manage data flow, handle errors robustly, and aggregate final output as per V2.4 specification.',
            backstory=(
                "As the central conductor of the V2.4 CoreReconstructionCrew, you are responsible for the seamless processing of diverse content sources (URLs, PDFs, DOCX, TXT, MD). "
                "You meticulously triage inputs, including handling the new 'processing_level' option. You then intelligently route tasks to specialized acquisition agents. "
                "A key part of your role is to ensure robust error handling, allowing for partial success where possible, and to aggregate all processed data into the precise 'reconstruction_output_v2_4' format, including structured content blocks and image gallery data."
            ),
            verbose=True,
            allow_delegation=True, # Will delegate to PDF, GenericFile, WebURL acquisition agents
            tools=configured_tools,
            # llm will be set by the Crew
        )

    def get_agent(self) -> Agent:
        """Returns the configured CrewAI Agent instance."""
        return self.agent_instance

    # --- Agent's Core Logic Methods ---

    def execute_initial_triage(self, input_data: OrchestrationInput) -> Dict[str, Any]:
        """
        Performs initial triage: validates input, normalizes identifier (basic),
        detects content type, and prepares data for routing.
        """
        print(f"OrchestrationAgent: Executing initial triage for {input_data.source_identifier}")
        if not input_data.source_identifier:
            return {
                "detected_content_type": "error",
                "normalized_identifier": None,
                "processing_level": input_data.processing_level,
                "validation_status": "failure",
                "error_message": "Source identifier is missing."
            }

        # Basic normalization (can be expanded)
        normalized_identifier = input_data.source_identifier.strip()
        
        # Determine if it's a file or URL for the tool
        # For simplicity, we'll infer. A more robust check might be needed.
        is_file_input = None # Let the tool infer by default
        if input_data.source_type in ["pdf", "docx", "txt", "md"] and not (normalized_identifier.startswith("http://") or normalized_identifier.startswith("https://")) :
            # If source_type suggests a file and it's not a URL, assume it's a file path
            # This logic might need refinement based on how file paths vs URLs are provided
            is_file_input = True


        print(f"OrchestrationAgent: Calling ContentTypeDetectionTool with identifier='{normalized_identifier}', is_file='{is_file_input}'")
        try:
            detected_content_type = self.content_type_tool._run(
                identifier=normalized_identifier,
                is_file=is_file_input
            )
        except Exception as e:
            print(f"OrchestrationAgent: Error calling ContentTypeDetectionTool: {e}")
            return {
                "detected_content_type": "error_detection_failed",
                "normalized_identifier": normalized_identifier,
                "processing_level": input_data.processing_level,
                "validation_status": "failure",
                "error_message": f"Content type detection failed: {str(e)}"
            }

        print(f"OrchestrationAgent: Detected content type: {detected_content_type}")
        
        validation_status = "success"
        error_message = None
        if "error" in detected_content_type or detected_content_type == "unknown":
            validation_status = "failure" # Or "partial_success" if unknown is sometimes okay
            error_message = f"Content type detected as '{detected_content_type}'."
            if detected_content_type == "unknown":
                 error_message = "Could not determine content type."


        return {
            "detected_content_type": detected_content_type,
            "normalized_identifier": normalized_identifier,
            "processing_level": input_data.processing_level,
            "validation_status": validation_status,
            "error_message": error_message
        }

    def execute_routing(self, triage_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines the routing path based on the detected content type from triage.
        Input: Output dictionary from execute_initial_triage.
        Output: Dictionary with routing_decision and parameters for the next agent.
        """
        print(f"OrchestrationAgent: Executing routing for triage_results: {triage_results}")
        detected_type = triage_results.get("detected_content_type")
        normalized_identifier = triage_results.get("normalized_identifier")
        processing_level = triage_results.get("processing_level")
        validation_status = triage_results.get("validation_status")

        if validation_status == "failure" or not detected_type or detected_type in ["error", "unknown", "unknown_file_type", "error_detection_failed", "error_file_not_found", "error_url_fetch"]: # Added unknown_file_type
            print(f"OrchestrationAgent: Routing failed due to unsuccessful triage. Type: {detected_type}")
            return {
                "routing_decision": "routing_failed_triage",
                "source_identifier": normalized_identifier,
                "processing_level": processing_level,
                "error_message": triage_results.get("error_message", "Routing failed due to triage error.")
            }

        routing_decision = ""
        error_message = None

        if detected_type == "pdf":
            routing_decision = "route_to_pdf_agent"
        elif detected_type in ["docx", "txt", "md"]:
            routing_decision = "route_to_generic_file_agent"
        elif detected_type in ["html", "jpeg", "png", "gif", "svg"]:
            routing_decision = "route_to_web_agent"
        else:
            routing_decision = "routing_failed_unsupported_type"
            error_message = f"Unsupported content type for routing: {detected_type}"
            print(f"OrchestrationAgent: Routing failed, unsupported type: {detected_type}")

        print(f"OrchestrationAgent: Routing decision: {routing_decision} for {normalized_identifier}")
        return {
            "routing_decision": routing_decision,
            "source_identifier": normalized_identifier,
            "processing_level": processing_level,
            "content_type_hint": detected_type, # Pass this to acquisition, then to structuring
            "error_message": error_message
        }

    def execute_error_aggregation(self, 
                                  initial_input: OrchestrationInput,
                                  triage_results: Dict[str, Any],
                                  acquisition_output: Optional[Dict[str, Any]] = None,      # e.g., FileAcquisitionOutput or WebAcquisitionOutput as dict
                                  image_processing_output: Optional[Dict[str, Any]] = None, # e.g., ImageProcessingOutput as dict
                                  structuring_output: Optional[Dict[str, Any]] = None       # e.g., ContentStructuringOutput as dict
                                 ) -> Dict[str, Any]:
        """
        Aggregates errors from all steps and determines a final status_code and error_message.
        This is a simplified version for now. A full CrewAI implementation would collect task outputs.
        """
        print(f"OrchestrationAgent: Executing error aggregation.")
        final_status_code = "success"
        aggregated_error_messages = []

        # Check triage stage
        if triage_results.get("validation_status") == "failure" or \
           triage_results.get("detected_content_type") in ["error", "unknown", "error_detection_failed", "error_file_not_found", "error_url_fetch", "unknown_file_type"]:
            final_status_code = "failure_acquisition" # Or more specific like "unsupported_type"
            if triage_results.get("detected_content_type") == "unknown_file_type":
                 final_status_code = "unsupported_type"
            aggregated_error_messages.append(triage_results.get("error_message", "Error during initial triage or unsupported type."))
            # Early exit if triage failed fundamentally
            return {"final_status_code": final_status_code, "aggregated_error_message": "; ".join(aggregated_error_messages)}

        # Check acquisition stage (conceptual - real output models needed)
        if acquisition_output and acquisition_output.get("status", "").startswith("error_"):
            final_status_code = "failure_acquisition"
            aggregated_error_messages.append(acquisition_output.get("error_message", "Error during content acquisition."))
        
        # Check image processing stage (conceptual)
        # This agent runs conditionally. If it runs and fails, it's a partial success usually.
        if image_processing_output and image_processing_output.get("status", "").startswith("error_"):
            if final_status_code == "success": # Only downgrade if previous steps were okay
                final_status_code = "partial_success" # Or "failure_image_processing"
            aggregated_error_messages.append(image_processing_output.get("error_message", "Error during image processing."))

        # Check structuring stage (conceptual)
        if structuring_output and structuring_output.get("status", "").startswith("error_"):
            if final_status_code == "success":  # Only downgrade if previous major steps were okay
                 final_status_code = "failure_structuring" # This is a more critical failure for content
            elif final_status_code == "partial_success": # If images failed, and now structuring fails
                 final_status_code = "failure_structuring" # Upgrade to a more severe failure
            aggregated_error_messages.append(structuring_output.get("error_message", "Error during content structuring."))
        
        # If all main steps seemed to succeed but no content blocks were produced by structuring (and it was expected to run)
        if final_status_code == "success" and structuring_output and not structuring_output.get("final_original_content_blocks") and acquisition_output and not acquisition_output.get("status", "").startswith("error_") :
            final_status_code = "failure_structuring"
            aggregated_error_messages.append("Content structuring completed but produced no content blocks.")


        # If no errors were added but status is not success, add a generic message
        if not aggregated_error_messages and final_status_code != "success" and final_status_code != "partial_success":
            aggregated_error_messages.append(f"Processing failed with status: {final_status_code}")
        
        return {
            "final_status_code": final_status_code,
            "aggregated_error_message": "; ".join(aggregated_error_messages) if aggregated_error_messages else None
        }

    def execute_output_aggregation(self,
                                   initial_input: OrchestrationInput,
                                   error_aggregation_results: Dict[str, Any], # from execute_error_aggregation
                                   # Data retrieved based on refs from previous agents:
                                   extracted_title: Optional[str],
                                   is_long_article_flag: bool,
                                   final_original_content_blocks: List[Dict[str, Any]], # Directly from structuring agent output model
                                   processed_image_data_list_ref: Optional[str] # Ref from image processing agent
                                  ) -> OrchestrationOutput:
        """
        Aggregates all successful data pieces into the final OrchestrationOutput model.
        """
        print(f"OrchestrationAgent: Executing output aggregation.")
        
        processed_images_list: List[ProcessedImageData] = []
        if processed_image_data_list_ref:
            try:
                # Assume DataStoreAccessTool stores lists of Pydantic models as lists of dicts
                image_list_data = self.data_store_tool._run(action="get", key=processed_image_data_list_ref)
                if isinstance(image_list_data, list):
                    for img_dict in image_list_data:
                        if isinstance(img_dict, dict): # Ensure it's a dict before Pydantic parsing
                            img_data_obj = ProcessedImageData(**img_dict)
                            processed_images_list.append(img_data_obj)
                        else:
                            print(f"Warning: Skipping non-dict item in image list: {img_dict}")
                elif image_list_data: # If it's not None but not a list (e.g. error string from DataStore)
                     print(f"Warning: Expected list from processed_image_data_list_ref, got {type(image_list_data)}. Image gallery might be incomplete.")

            except Exception as e_img_agg:
                print(f"OrchestrationAgent: Error processing image data for final output: {e_img_agg}")
                # Potentially update error_aggregation_results or add to its message
                if error_aggregation_results.get("final_status_code") == "success":
                    error_aggregation_results["final_status_code"] = "partial_success" # Or a specific image aggregation error status
                current_err = error_aggregation_results.get("aggregated_error_message", "")
                error_aggregation_results["aggregated_error_message"] = (current_err + "; " if current_err else "") + f"Failed to aggregate processed image data: {e_img_agg}"


        # Convert final_original_content_blocks from List[Dict] to List[ContentBlock]
        content_blocks_for_output: List[ContentBlock] = []
        for block_dict in final_original_content_blocks:
            try:
                content_blocks_for_output.append(ContentBlock(**block_dict))
            except Exception as e_block_parse:
                print(f"Warning: Could not parse content block, skipping: {block_dict}. Error: {e_block_parse}")
                # Optionally add to aggregated_error_messages if critical


        return OrchestrationOutput(
            status_code=error_aggregation_results.get("final_status_code", "failure_unknown"),
            source_identifier=initial_input.source_identifier,
            source_type=initial_input.source_type,
            processing_level_used=initial_input.processing_level,
            extracted_title=extracted_title,
            is_long_article=is_long_article_flag,
            original_content_blocks=content_blocks_for_output,
            processed_images_data=processed_images_list,
            error_message=error_aggregation_results.get("aggregated_error_message")
        )

    # --- Task Definitions for OrchestrationAgent --- 

    def task_initial_triage(self, input_data: OrchestrationInput) -> Task:
        """Task: Validate input, normalize identifier, detect content type, and handle processing_level."""
        # In a real CrewAI setup, the 'agent' parameter for the task would be self.agent_instance
        # and the task's 'action' could directly be self.execute_initial_triage if its signature matches
        # or it would use tools associated with the agent.
        # For direct method execution, the method signature must match what CrewAI expects for a task action,
        # typically taking a single 'context' dictionary or specific string inputs.
        # Here, we illustrate how the task *could* use the agent's method conceptually.
        # The actual execution would depend on how the Crew is structured.

        return Task(
            description=f"Perform initial triage for source: {input_data.source_identifier} of type {input_data.source_type} with processing level {input_data.processing_level}. "
                        f"This involves validating the input, normalizing the source identifier, and accurately detecting the content type using the ContentTypeDetectionTool. The processing_level ({input_data.processing_level}) must be noted and passed on.",
            expected_output="A dictionary containing 'detected_content_type' (e.g., 'pdf', 'html', 'docx', 'txt', 'md', 'unsupported', or 'error'), 'normalized_identifier', 'processing_level', and 'validation_status' (e.g., 'success', 'failure') with an 'error_message' if validation failed.",
            agent=self.agent_instance, # Assign the agent instance
            # One way to link to the method (if the method is designed as a tool or direct action):
            # tool=[self.content_type_tool] # Or make execute_initial_triage a tool itself.
            # For now, the agent is responsible, and its tools would be used by an LLM if no direct action is specified.
            # To directly call `execute_initial_triage`, it might need to be wrapped or the task configured
            # to call a specific method with context. Let's assume for now the agent's LLM uses its tools.
            # arguments={'input_data_dict': input_data.model_dump()} # Pass data to the task context
        )

    def task_routing(self, agent_to_use: Agent, context: Dict[str, Any]) -> Task: # Context comes from previous task
        """Task: Select and invoke the appropriate acquisition agent based on content type."""
        detected_type = context.get('detected_content_type', 'unknown')
        source_identifier = context.get('normalized_identifier', 'unknown')
        processing_level = context.get('processing_level', 'full_content')

        return Task(
            description=f"Route the request for '{source_identifier}' (detected as {detected_type}) with processing level '{processing_level}' to the correct content acquisition agent. "
                        f"This involves selecting one of: PDFContentAcquisitionAgent, GenericFileContentAcquisitionAgent, or WebURLContentAcquisitionAgent.",
            expected_output="A dictionary containing 'routing_decision' (e.g., 'route_to_pdf_agent', 'route_to_generic_file_agent', 'route_to_web_agent', 'routing_failed_unsupported_type') "
                            "and any necessary parameters for the chosen agent (e.g., 'source_identifier', 'processing_level').",
            agent=agent_to_use,
            context=context # Pass context to this task
        )

    def task_error_aggregation(self, agent_to_use: Agent, context: List[Dict[str, Any]]) -> Task: # Context from all relevant tasks
        """Task: Consolidate errors from any step and determine overall status."""
        return Task(
            description="Aggregate error information from all preceding tasks in the pipeline (acquisition, image processing, content structuring). "
                        "Identify if any critical failures occurred and determine an overall status. Implement fallback strategies to return partial content if feasible.",
            expected_output="A dictionary containing 'overall_status' (e.g., 'success', 'partial_success', 'failure_critical'), 'aggregated_errors' (a list of error messages or codes), and 'fallback_content_available' (boolean).",
            agent=agent_to_use,
            context=context # Pass context to this task
        )
    
    def task_output_aggregation(self, agent_to_use: Agent, context: Dict[str, Any]) -> Task: # Context from all pipeline results
        """Task: Compile the final response in OrchestrationOutput format."""
        return Task(
            description="Compile the final 'reconstruction_output_v2_4' JSON object. This includes gathering the status code, source details, processing level used, extracted title, long article flag, "
                        "the main content blocks (text/math/code with image placeholders), the processed image gallery data, and any error messages. "
                        "Ensure the output strictly adheres to the OrchestrationOutput Pydantic model.",
            expected_output="A fully populated OrchestrationOutput Pydantic model or a dictionary that can be parsed into it. This is the final API response body.",
            agent=agent_to_use,
            context=context # Pass context to this task
        )

    # --- Placeholder for actual execution logic --- 
    # In a real CrewAI setup, you'd define a Crew and then kick off its tasks.
    # The OrchestrationAgent's methods above define the tasks, but the agent itself
    # would typically have methods that are called *by* a Task's `action` 
    # (if not using a tool directly for the action).
    # For now, these task definitions serve to outline the agent's responsibilities.

    # Example of how a task execution method might look if not using a tool directly:
    # def execute_triage(self, input_data: OrchestrationInput) -> Dict[str, Any]:
    #     # ... actual logic for triage ...
    #     # detected_type = self.content_type_tool.detect(input_data.source_identifier)
    #     return {
    #         "detected_content_type": "pdf", # Example
    #         "normalized_identifier": input_data.source_identifier,
    #         "processing_level": input_data.processing_level,
    #         "validation_status": "success",
    #         "error_message": None
    #     }

# The V2.4 documentation mentions tools:
# - ContentTypeDetectionTool (from aiservice/app/tools/utility_tools.py)
# - DataStoreAccessTool (from aiservice/app/tools/utility_tools.py)

# Further development would involve:
# 1. Implementing the actual logic for `execute_routing`, `execute_error_aggregation`, `execute_output_aggregation`.
# 2. Defining how data is passed between tasks (e.g., via CrewAI context, or using DataStoreAccessTool for larger data pieces).
#    The `context` parameter in task definitions is crucial here. Task output automatically feeds into the context for the next task by default.
# 3. Integrating the actual acquisition agents once they are developed.
# 4. Building the Crew that uses this OrchestrationAgent and its tasks, and defining the task sequence.
# Add other specific methods related to input validation, content type detection, routing etc.
# based on TS-AI-Reconstruct-0 details as we develop further. 