from crewai.tools import BaseTool
from typing import Type, Any, Dict, Optional
from pydantic import BaseModel, Field, PrivateAttr
import json

# Import Pydantic models for input/output typing if they are complex
from app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock, ProcessedImageData

# Import our agent logic classes to call their methods
from app.agents.orchestration_agent import OrchestrationAgent
from app.agents.pdf_acquisition_agent import PDFAcquisitionAgent
from app.models.pdf_acquisition_models import PDFAcquisitionInput, PDFAcquisitionOutput
from app.agents.generic_file_acquisition_agent import GenericFileContentAcquisitionAgent
from app.models.file_acquisition_models import FileAcquisitionInput, FileAcquisitionOutput
from app.agents.web_url_acquisition_agent import WebURLContentAcquisitionAgent
from app.models.web_acquisition_models import WebAcquisitionInput, WebAcquisitionOutput
from app.models.image_processing_models import ImageProcessingInput, ImageProcessingOutput
from app.agents.image_processing_agent import ImageProcessingPersistenceAgent
from app.models.content_structuring_models import ContentStructuringInput, ContentStructuringOutput
from app.agents.content_structuring_agent import ContentConsolidationStructuringAgent

# Corrected import for DataStoreAccessTool
from app.tools.utility_tools import DataStoreAccessTool
# ... import other agent logic classes as needed for other tools ...

# --- Tool for OrchestrationAgent.execute_initial_triage ---
class InitialTriageToolInput(BaseModel):
    """Input schema for the InitialTriageTool."""
    orchestration_input_dict: Dict[str, Any] = Field(
        description=(
            "A dictionary representing the OrchestrationInput model. Must contain keys: "
            "'source_identifier' (str: the URL or filepath), "
            "'source_type' (str: e.g., 'url', 'pdf', 'docx'), and "
            "'processing_level' (str: e.g., 'full_content', 'text_only')."
        )
    )

class InitialTriageTool(BaseTool):
    name: str = "Initial Triage Tool"
    description: str = (
        "Performs initial triage on a source input. Validates input and detects content type. "
        "Expects a single argument: 'orchestration_input_dict' which is a dictionary "
        "containing 'source_identifier', 'source_type', and 'processing_level'."
    )
    args_schema: Type[BaseModel] = InitialTriageToolInput
    _agent_logic: OrchestrationAgent = PrivateAttr()

    def __init__(self, agent_logic: OrchestrationAgent, **kwargs: Any):
        super().__init__(**kwargs)
        self._agent_logic = agent_logic

    def _run(self, orchestration_input_dict: Dict[str, Any]) -> Dict[str, Any]:
        print(f"InitialTriageTool: Running with input: {orchestration_input_dict}")
        try:
            # Ensure all required keys are present before Pydantic conversion for better error feedback upstream
            required_keys = ["source_identifier", "source_type", "processing_level"]
            for key in required_keys:
                if key not in orchestration_input_dict:
                    # This error should ideally be caught by the agent forming the input based on args_schema
                    return {"error": f"Missing key '{key}' in orchestration_input_dict for InitialTriageTool.", "validation_status": "failure"}
            
            orchestration_input = OrchestrationInput(**orchestration_input_dict)
            triage_results = self._agent_logic.execute_initial_triage(orchestration_input)
            return triage_results
        except Exception as e:
            print(f"Error in InitialTriageTool: {e}")
            return {"error": str(e), "validation_status": "failure"}

# --- Tool for OrchestrationAgent.execute_routing ---
class RoutingToolInput(BaseModel):
    """Input schema for the RoutingTool."""
    # This will now be a JSON string from the previous task's output
    triage_results_json_str: str = Field(description="JSON string of triage results from InitialTriageTool.")

class RoutingTool(BaseTool):
    name: str = "Routing Tool"
    description: str = "Determines the processing route based on triage results provided as a JSON string."
    args_schema: Type[BaseModel] = RoutingToolInput
    _agent_logic: OrchestrationAgent = PrivateAttr()

    def __init__(self, agent_logic: OrchestrationAgent, **kwargs: Any):
        super().__init__(**kwargs)
        self._agent_logic = agent_logic

    def _run(self, triage_results_json_str: str) -> Dict[str, Any]: # Output is still a Python Dict
        print(f"RoutingTool: Running with triage_results_json_str: {triage_results_json_str}")
        try:
            triage_results_dict = json.loads(triage_results_json_str)
            if not isinstance(triage_results_dict, dict):
                raise ValueError("Parsed triage results is not a dictionary.")
            
            routing_results = self._agent_logic.execute_routing(triage_results_dict)
            return routing_results
        except json.JSONDecodeError as e:
            print(f"Error in RoutingTool decoding JSON: {e}")
            return {"error": f"Invalid JSON input: {e}", "routing_decision": "routing_failed_json_decode"}
        except Exception as e:
            print(f"Error in RoutingTool: {e}")
            return {"error": str(e), "routing_decision": "routing_failed_exception"}

# --- Tool for PDFAcquisitionAgent.execute_pdf_processing ---
class PDFAcquisitionToolInput(BaseModel):
    """Input for PDF Acquisition Tool."""
    # Expects routing_results dict which contains file_path and processing_level
    routing_results_json_str: str = Field(description="JSON string of routing results. Must contain 'source_identifier' (file path) and 'processing_level'.")
    job_id: str = Field(description="The unique job ID for this processing run.")

class PDFAcquisitionCrewTool(BaseTool):
    name: str = "PDF Acquisition Tool"
    description: str = "Processes a PDF file to extract text, identify images, and gather metadata using the PDFAcquisitionAgent logic."
    args_schema: Type[BaseModel] = PDFAcquisitionToolInput
    _agent_logic: PDFAcquisitionAgent = PrivateAttr()
    _data_store_tool: DataStoreAccessTool = PrivateAttr()

    def __init__(self, agent_logic: PDFAcquisitionAgent, data_store_tool: DataStoreAccessTool, **kwargs: Any):
        super().__init__(**kwargs)
        self._agent_logic = agent_logic
        self._data_store_tool = data_store_tool

    def _run(self, routing_results_json_str: str, job_id: str) -> Dict[str, Any]:
        print(f"PDFAcquisitionCrewTool: Running for job_id: {job_id}")
        try:
            routing_results = json.loads(routing_results_json_str)
            pdf_input_args = PDFAcquisitionInput(
                file_path=routing_results["source_identifier"],
                processing_level=routing_results["processing_level"]
            )
            output_model = self._agent_logic.execute_pdf_processing(pdf_input_args, job_id_for_ds_keys=job_id)
            output_json_str = json.dumps(output_model.model_dump())
            
            # Store this full output for ImageProcessingCrewTool and ContentStructuringCrewTool
            ds_key = f"output_of_{routing_results.get('routing_decision')}_for_job_{job_id}"
            self._data_store_tool._run(action="put", key=ds_key, value=output_json_str)
            print(f"PDFAcquisitionCrewTool: Stored full output to DataStore with key: {ds_key}")
            
            return output_json_str
        except Exception as e:
            print(f"Error in PDFAcquisitionCrewTool: {e}")
            return {"error": str(e), "status": "error_pdf_acquisition_tool_failure"}

# --- Tool for GenericFileContentAcquisitionAgent.dispatch_file_processing ---
class GenericFileAcquisitionToolInput(BaseModel):
    """Input for Generic File Acquisition Tool."""
    routing_results_json_str: str = Field(description="JSON string of routing results. Must contain 'source_identifier' (file path), 'processing_level', and 'content_type_hint'.")
    job_id: str = Field(description="The unique job ID for this processing run.")

class GenericFileAcquisitionCrewTool(BaseTool):
    name: str = "Generic File Acquisition Tool"
    description: str = "Processes DOCX, MD, or TXT files using the GenericFileContentAcquisitionAgent logic."
    args_schema: Type[BaseModel] = GenericFileAcquisitionToolInput
    _agent_logic: GenericFileContentAcquisitionAgent = PrivateAttr()
    _data_store_tool: DataStoreAccessTool = PrivateAttr()

    def __init__(self, agent_logic: GenericFileContentAcquisitionAgent, data_store_tool: DataStoreAccessTool, **kwargs: Any):
        super().__init__(**kwargs)
        self._agent_logic = agent_logic
        self._data_store_tool = data_store_tool

    def _run(self, routing_results_json_str: str, job_id: str) -> Dict[str, Any]:
        print(f"GenericFileAcquisitionCrewTool: Running for job_id: {job_id}")
        try:
            routing_results = json.loads(routing_results_json_str)
            file_input_args = FileAcquisitionInput(
                file_path=routing_results["source_identifier"],
                processing_level=routing_results["processing_level"],
                source_content_type=routing_results["content_type_hint"]
            )
            output_model = self._agent_logic.dispatch_file_processing(file_input_args, job_id_for_ds_keys=job_id)
            output_json_str = json.dumps(output_model.model_dump())

            ds_key = f"output_of_{routing_results.get('routing_decision')}_for_job_{job_id}"
            self._data_store_tool._run(action="put", key=ds_key, value=output_json_str)
            print(f"GenericFileAcquisitionCrewTool: Stored full output to DataStore with key: {ds_key}")

            return output_json_str
        except Exception as e:
            print(f"Error in GenericFileAcquisitionCrewTool: {e}")
            return {"error": str(e), "status": "error_generic_file_acquisition_tool_failure"}

# --- Tool for WebURLContentAcquisitionAgent.execute_comprehensive_url_processing ---
class WebURLAcquisitionToolInput(BaseModel):
    """Input for Web URL Acquisition Tool."""
    routing_results_json_str: str = Field(description="JSON string of routing results. Must contain 'source_identifier' (URL) and 'processing_level'.")
    job_id: str = Field(description="The unique job ID for this processing run.")

class WebURLAcquisitionCrewTool(BaseTool):
    name: str = "Web URL Acquisition Tool"
    description: str = "Processes a web URL to fetch content, images, and metadata using the WebURLContentAcquisitionAgent logic."
    args_schema: Type[BaseModel] = WebURLAcquisitionToolInput
    _agent_logic: WebURLContentAcquisitionAgent = PrivateAttr()
    _data_store_tool: DataStoreAccessTool = PrivateAttr()

    def __init__(self, agent_logic: WebURLContentAcquisitionAgent, data_store_tool: DataStoreAccessTool, **kwargs: Any):
        super().__init__(**kwargs)
        self._agent_logic = agent_logic
        self._data_store_tool = data_store_tool

    def _run(self, routing_results_json_str: str, job_id: str) -> Dict[str, Any]:
        print(f"WebURLAcquisitionCrewTool: Running for job_id: {job_id}")
        try:
            routing_results = json.loads(routing_results_json_str)
            web_input_args = WebAcquisitionInput(
                url=routing_results["source_identifier"],
                processing_level=routing_results["processing_level"]
            )
            output_model = self._agent_logic.execute_comprehensive_url_processing(web_input_args, job_id_for_ds_keys=job_id)
            output_json_str = json.dumps(output_model.model_dump())
            
            ds_key = f"output_of_{routing_results.get('routing_decision')}_for_job_{job_id}"
            self._data_store_tool._run(action="put", key=ds_key, value=output_json_str)
            print(f"WebURLAcquisitionCrewTool: Stored full output to DataStore with key: {ds_key}")
            
            return output_json_str
        except Exception as e:
            print(f"Error in WebURLAcquisitionCrewTool: {e}")
            return {"error": str(e), "status": "error_web_acquisition_tool_failure"}

# --- Tool for ImageProcessingPersistenceAgent (Refactored) ---
class ImageProcessingToolInput(BaseModel):
    """Input for the Image Processing Tool."""
    job_id: str = Field(description="The unique job ID for this processing run.")
    routing_results_json_str: str = Field(description="JSON string of routing results, contains routing_decision and source_identifier.")

class ImageProcessingCrewTool(BaseTool):
    name: str = "Image Processing and Persistence Tool"
    description: str = ("Processes images based on prior acquisition. It uses routing results to find the correct image list reference by fetching the relevant acquisition task's output from the DataStore, "
                      "then downloads/processes images, uploads to GCS, and consolidates metadata.")
    args_schema: Type[BaseModel] = ImageProcessingToolInput
    _agent_logic: ImageProcessingPersistenceAgent = PrivateAttr()
    _data_store_tool: DataStoreAccessTool = PrivateAttr()

    def __init__(self, agent_logic: ImageProcessingPersistenceAgent, data_store_tool: DataStoreAccessTool, **kwargs: Any):
        super().__init__(**kwargs)
        self._agent_logic = agent_logic
        self._data_store_tool = data_store_tool

    def _run(self, job_id: str, routing_results_json_str: str) -> str:
        print(f"ImageProcessingCrewTool: Running for job_id: {job_id}")
        try:
            routing_results = json.loads(routing_results_json_str)
            
            routing_decision = routing_results.get("routing_decision")
            source_identifier = routing_results.get("source_identifier") 
            source_content_type_hint = routing_results.get("content_type_hint")

            if not routing_decision or not source_identifier or not source_content_type_hint:
                error_msg = "Critical data (routing_decision, source_identifier, or content_type_hint) missing in routing_results."
                print(f"ImageProcessingCrewTool: Error - {error_msg}")
                return json.dumps({"status": "error_tool_input_missing_routing_data", "error_message": error_msg})

            acq_output_ds_key = f"output_of_{routing_decision}_for_job_{job_id}"
            print(f"ImageProcessingCrewTool: Attempting to fetch full acquisition output from DataStore key: {acq_output_ds_key}")
            acquisition_output_json_str = self._data_store_tool._run(action="get", key=acq_output_ds_key)

            image_processing_agent_input_args = {
                "original_source_identifier": source_identifier,
                "source_type": source_content_type_hint,
                "job_id": job_id,
                "pdf_image_list_ref": None,
                "generic_file_image_list_ref": None,
                "web_image_list_ref": None
            }

            if not acquisition_output_json_str or acquisition_output_json_str == '{}':
                msg = f"No acquisition output found or it was empty in DataStore for key '{acq_output_ds_key}'. Proceeding, assuming no images from acquisition."
                print(f"ImageProcessingCrewTool: {msg}")
            else:
                try:
                    acquisition_output = json.loads(acquisition_output_json_str)
                    if routing_decision == "route_to_pdf_agent":
                        image_processing_agent_input_args["pdf_image_list_ref"] = acquisition_output.get("image_list_ref")
                    elif routing_decision == "route_to_generic_file_agent":
                        image_processing_agent_input_args["generic_file_image_list_ref"] = acquisition_output.get("image_list_ref")
                    elif routing_decision == "route_to_web_agent":
                        image_processing_agent_input_args["web_image_list_ref"] = acquisition_output.get("extracted_image_url_list_with_ids_ref")
                except json.JSONDecodeError as e_acq_parse:
                    error_msg = f"Failed to parse acquisition output from DataStore (key: {acq_output_ds_key}): {str(e_acq_parse)}. Content: '{acquisition_output_json_str[:200]}...'"
                    print(f"ImageProcessingCrewTool: Error - {error_msg}")
                    # Proceed, ImageProcessingPersistenceAgent will handle missing refs
                    
            image_agent_input = ImageProcessingInput(**image_processing_agent_input_args)
            print(f"ImageProcessingCrewTool: Constructed ImageProcessingInput: {image_agent_input.model_dump_json(indent=2)}")
            output: ImageProcessingOutput = self._agent_logic.execute_image_processing_pipeline(image_agent_input)
            output_json_str = json.dumps(output.model_dump())

            # Store this tool's output as well, as ContentStructuring might need its *reference*
            ds_key_img_proc = f"output_of_task_image_processing_for_job_{job_id}"
            self._data_store_tool._run(action="put", key=ds_key_img_proc, value=output_json_str)
            print(f"ImageProcessingCrewTool: Stored own output to DataStore with key: {ds_key_img_proc}")

            return output_json_str

        except json.JSONDecodeError as e_route_parse:
            error_msg = f"Failed to parse routing_results_json_str: {str(e_route_parse)}. Input was: '{routing_results_json_str}'"
            print(f"ImageProcessingCrewTool: JSONDecodeError - {error_msg}")
            return json.dumps({"status": "error_tool_input_parsing_routing", "error_message": error_msg})
        except Exception as e_main:
            print(f"Error in ImageProcessingCrewTool._run: {e_main}")
            import traceback
            traceback.print_exc()
            return json.dumps({"status": "error_image_processing_tool_failure", "error_message": str(e_main)})

# --- Tool for ContentConsolidationStructuringAgent ---
class ContentStructuringToolInput(BaseModel):
    """Input for the Content Structuring Tool."""
    routing_results_json_str: str = Field(description="JSON string of routing results (for title, source type hint).")
    relevant_acquisition_output_json_str: Optional[str] = Field(default=None, description="JSON string of the relevant acquisition output (PDF, Generic, or Web).")
    image_processing_output_json_str: str = Field(description="JSON string of Image Processing output (for processed_image_data_list_ref).")

class ContentStructuringCrewTool(BaseTool):
    name: str = "Content Consolidation and Structuring Tool"
    description: str = "Assembles extracted text and image data into final structured content blocks using an LLM via ContentConsolidationStructuringAgent."
    args_schema: Type[BaseModel] = ContentStructuringToolInput
    _agent_logic: ContentConsolidationStructuringAgent = PrivateAttr()

    def __init__(self, agent_logic: ContentConsolidationStructuringAgent, **kwargs: Any):
        super().__init__(**kwargs)
        self._agent_logic = agent_logic

    def _run(self, 
             routing_results_json_str: str, 
             image_processing_output_json_str: str,
             relevant_acquisition_output_json_str: Optional[str] = None) -> str:
        print("ContentStructuringCrewTool: Running with provided JSON string inputs.")
        try:
            routing_results = json.loads(routing_results_json_str)
            image_processing_output = json.loads(image_processing_output_json_str)

            source_content_type_hint = routing_results.get("content_type_hint")
            processed_image_data_list_ref = image_processing_output.get("processed_image_data_list_ref")
            
            extracted_text_content_ref: Optional[str] = None
            page_title_from_acquisition: Optional[str] = None
            
            active_acq_output = {}
            routing_decision = routing_results.get("routing_decision")

            if relevant_acquisition_output_json_str and relevant_acquisition_output_json_str.strip() and relevant_acquisition_output_json_str != "{{}}": # Check for non-empty and not double-brace
                try:
                    active_acq_output = json.loads(relevant_acquisition_output_json_str)
                except json.JSONDecodeError as je:
                    # If it's specifically the double-brace string that the agent might pass for "empty JSON object"
                    if relevant_acquisition_output_json_str == "{}": # Single brace string is valid JSON
                         active_acq_output = json.loads(relevant_acquisition_output_json_str)
                    else:
                        print(f"ContentStructuringCrewTool: Warning - JSONDecodeError for relevant_acquisition_output_json_str: {je}. Content was: '{relevant_acquisition_output_json_str}'. Proceeding with empty active_acq_output.")
                        active_acq_output = {} # Default to empty if malformed and not the specific double-brace case handled by outer if
            elif relevant_acquisition_output_json_str == "{}": # Explicitly handle the case where agent sends literal {} string for empty object
                 active_acq_output = json.loads(relevant_acquisition_output_json_str)
            else:
                print(f"ContentStructuringCrewTool: relevant_acquisition_output_json_str is 'None', empty, or '{{}}'. Proceeding with empty active_acq_output.")
                active_acq_output = {} # Default to empty
            
            extracted_text_content_ref = active_acq_output.get("extracted_text_content_ref")
            
            if routing_decision == "route_to_web_agent":
                page_title_from_acquisition = active_acq_output.get("page_title_from_web")
            else: 
                page_title_from_acquisition = active_acq_output.get("title") or \
                                              active_acq_output.get("page_title_from_file") or \
                                              active_acq_output.get("extracted_title")


            if not extracted_text_content_ref:
                print(f"ContentStructuringCrewTool: WARNING - No extracted_text_content_ref in relevant acq output ('{routing_decision}'). Will use default.")
            if not source_content_type_hint:
                 print(f"ContentStructuringCrewTool: WARNING - No source_content_type_hint from routing. Will use default.")

            structuring_input_args = {
                "extracted_text_content_ref": extracted_text_content_ref if extracted_text_content_ref else "error_no_text_ref_found_by_tool",
                "processed_image_data_list_ref": processed_image_data_list_ref, 
                "source_content_type_hint": source_content_type_hint if source_content_type_hint else "unknown_type_to_tool",
                "page_title_from_acquisition": page_title_from_acquisition
            }
            
            structuring_input = ContentStructuringInput(**structuring_input_args)
            output: ContentStructuringOutput = self._agent_logic.execute_content_structuring(structuring_input)
            output_json_str = json.dumps(output.model_dump())

            return output_json_str

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse one or more input JSON strings for ContentStructuring: {str(e)}. Routing: '{routing_results_json_str}', ImageProc: '{image_processing_output_json_str}', RelevantAcq: '{relevant_acquisition_output_json_str}'"
            print(f"ContentStructuringCrewTool: JSONDecodeError - {error_msg}")
            return json.dumps({"status": "error_tool_input_parsing", "error_message": error_msg})
        except Exception as e:
            print(f"Error in ContentStructuringCrewTool._run: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps({"status": "error_content_structuring_tool_failure", "error_message": str(e)})

# --- Tool for OrchestrationAgent.execute_error_aggregation ---
class ErrorAggregationToolInput(BaseModel):
    initial_input_dict: Dict[str, Any] = Field(description="Dictionary of the initial OrchestrationInput.")
    triage_results_json_str: str = Field(description="JSON string of triage results.")
    pdf_acquisition_output_json_str: Optional[str] = Field(default=None, description="JSON string of PDF acquisition output, if applicable.")
    generic_file_acquisition_output_json_str: Optional[str] = Field(default=None, description="JSON string of Generic File acquisition output, if applicable.")
    web_acquisition_output_json_str: Optional[str] = Field(default=None, description="JSON string of Web URL acquisition output, if applicable.")
    image_processing_output_json_str: Optional[str] = Field(default=None, description="JSON string of Image Processing output, if applicable.")
    structuring_output_json_str: Optional[str] = Field(default=None, description="JSON string of Content Structuring output, if applicable.")

class ErrorAggregationCrewTool(BaseTool):
    name: str = "Error Aggregation Tool"
    description: str = "Aggregates errors from all preceding steps in the content reconstruction workflow."
    args_schema: Type[BaseModel] = ErrorAggregationToolInput
    _agent_logic: OrchestrationAgent = PrivateAttr()

    def __init__(self, agent_logic: OrchestrationAgent, **kwargs: Any):
        super().__init__(**kwargs)
        self._agent_logic = agent_logic

    def _run(self, **kwargs) -> Dict[str, Any]: # Returns error aggregation results dict
        print(f"ErrorAggregationCrewTool: Running with inputs.")
        try:
            initial_input = OrchestrationInput(**kwargs["initial_input_dict"])
            triage_results = json.loads(kwargs["triage_results_json_str"])
            
            # Safely parse optional JSON string outputs
            def safe_json_load(json_str: Optional[str]) -> Optional[Dict[str, Any]]:
                if json_str and json_str.strip() and json_str != "{}":
                    try: return json.loads(json_str)
                    except json.JSONDecodeError: return {"error": "Failed to parse upstream JSON output."}
                return None

            pdf_acq_out = safe_json_load(kwargs.get("pdf_acquisition_output_json_str"))
            gen_acq_out = safe_json_load(kwargs.get("generic_file_acquisition_output_json_str"))
            web_acq_out = safe_json_load(kwargs.get("web_acquisition_output_json_str"))
            img_proc_out = safe_json_load(kwargs.get("image_processing_output_json_str"))
            struct_out = safe_json_load(kwargs.get("structuring_output_json_str"))
            print(f"ErrorAggregationCrewTool: struct_out before error check: {struct_out}") # DEBUG
            if struct_out:
                print(f"ErrorAggregationCrewTool: struct_out.get('final_original_content_blocks') is None: {struct_out.get('final_original_content_blocks') is None}") # DEBUG
                if struct_out.get('final_original_content_blocks') is not None:
                     print(f"ErrorAggregationCrewTool: len(struct_out.get('final_original_content_blocks')): {len(struct_out.get('final_original_content_blocks'))}") # DEBUG

            # Determine the relevant acquisition output based on routing_decision in triage_results
            # This logic might be better if routing_results itself was passed, but for now, select based on what is not None/empty
            acquisition_output = pdf_acq_out or gen_acq_out or web_acq_out 
            if not acquisition_output and (pdf_acq_out is None and gen_acq_out is None and web_acq_out is None):
                 # if all are None, it means no acquisition path was taken or all returned empty
                 # if routing was successful, one of them should have content or an error
                 pass # allow it, agent logic will handle

            error_agg_results = self._agent_logic.execute_error_aggregation(
                initial_input=initial_input,
                triage_results=triage_results,
                acquisition_output=acquisition_output,
                image_processing_output=img_proc_out,
                structuring_output=struct_out
            )
            return error_agg_results
        except Exception as e:
            print(f"Error in ErrorAggregationCrewTool: {e}")
            return {"final_status_code": "error_aggregation_tool_exception", "aggregated_error_message": str(e)}

# --- Tool for OrchestrationAgent.execute_output_aggregation ---
class OutputAggregationToolInput(BaseModel):
    initial_input_dict: Dict[str, Any] = Field(description="Dictionary of the initial OrchestrationInput.")
    error_aggregation_results_json_str: str = Field(description="JSON string of error aggregation results.")
    routing_results_json_str: str = Field(description="JSON string of routing results (for title, source type hint).")
    pdf_acquisition_output_json_str: Optional[str] = Field(default=None)
    generic_file_acquisition_output_json_str: Optional[str] = Field(default=None)
    web_acquisition_output_json_str: Optional[str] = Field(default=None)
    image_processing_output_json_str: Optional[str] = Field(default=None)
    structuring_output_json_str: Optional[str] = Field(default=None)

class OutputAggregationCrewTool(BaseTool):
    name: str = "Output Aggregation Tool"
    description: str = "Aggregates all processed data and errors into the final OrchestrationOutput format."
    args_schema: Type[BaseModel] = OutputAggregationToolInput
    _agent_logic: OrchestrationAgent = PrivateAttr()
    _data_store_tool: DataStoreAccessTool = PrivateAttr() # To fetch processed_images_data list

    def __init__(self, agent_logic: OrchestrationAgent, data_store_tool: DataStoreAccessTool, **kwargs: Any):
        super().__init__(**kwargs)
        self._agent_logic = agent_logic
        self._data_store_tool = data_store_tool # Store the shared data_store_tool

    def _run(self, **kwargs) -> Dict[str, Any]: # Returns OrchestrationOutput.model_dump()
        print(f"OutputAggregationCrewTool: Running with inputs.")
        initial_input_dict_from_kwargs = kwargs.get("initial_input_dict", {})
        try:
            initial_input = OrchestrationInput(**initial_input_dict_from_kwargs)
            error_aggregation_results = json.loads(kwargs["error_aggregation_results_json_str"])
            routing_results = json.loads(kwargs["routing_results_json_str"])

            def safe_json_load(json_str: Optional[str]) -> Optional[Dict[str, Any]]:
                if json_str and json_str.strip() and json_str != "{}":
                    try: return json.loads(json_str)
                    except json.JSONDecodeError: return {"error": "Failed to parse upstream JSON."}
                return None

            pdf_acq_out = safe_json_load(kwargs.get("pdf_acquisition_output_json_str"))
            gen_acq_out = safe_json_load(kwargs.get("generic_file_acquisition_output_json_str"))
            web_acq_out = safe_json_load(kwargs.get("web_acquisition_output_json_str"))
            img_proc_out = safe_json_load(kwargs.get("image_processing_output_json_str"))
            struct_out = safe_json_load(kwargs.get("structuring_output_json_str"))
            print(f"OutputAggregationCrewTool: web_acq_out: {web_acq_out}") # DEBUG

            extracted_title: Optional[str] = None
            routing_decision = routing_results.get("routing_decision")

            if routing_decision == "route_to_pdf_agent" and pdf_acq_out:
                extracted_title = pdf_acq_out.get("extracted_title")
            elif routing_decision == "route_to_generic_file_agent" and gen_acq_out:
                extracted_title = gen_acq_out.get("extracted_title")
            elif routing_decision == "route_to_web_agent" and web_acq_out:
                extracted_title = web_acq_out.get("page_title_from_web")
            
            print(f"OutputAggregationCrewTool: Determined extracted_title: {extracted_title}") # DEBUG

            is_long_article_flag = struct_out.get("is_long_article_flag", False) if struct_out else False
            final_original_content_blocks_dicts = struct_out.get("final_original_content_blocks", []) if struct_out else []
            processed_image_data_list_ref = img_proc_out.get("processed_image_data_list_ref") if img_proc_out else None

            # Convert list of dicts back to ContentBlock objects if needed by agent logic, though model_dump should be fine
            # For OrchestrationAgent.execute_output_aggregation, it expects List[Dict] for blocks

            final_output_model = self._agent_logic.execute_output_aggregation(
                initial_input=initial_input,
                error_aggregation_results=error_aggregation_results,
                extracted_title=extracted_title,
                is_long_article_flag=is_long_article_flag,
                final_original_content_blocks=final_original_content_blocks_dicts, # Already list of dicts
                processed_image_data_list_ref=processed_image_data_list_ref,
                # Pass the data_store_tool instance for the method to use, not just the ref
                # The method itself will use this tool to fetch the data using the ref
            )
            return final_output_model.model_dump()
        except Exception as e:
            print(f"Error in OutputAggregationCrewTool: {e}")
            # Return a structure similar to OrchestrationOutput for error consistency
            # Ensure all required fields for OrchestrationOutput are present
            return OrchestrationOutput(
                status_code="error_output_aggregation_tool_exception",
                source_identifier=initial_input_dict_from_kwargs.get("source_identifier", "unknown_source_id_in_tool_exc"),
                source_type=initial_input_dict_from_kwargs.get("source_type", "unknown_type_in_tool_exc"),
                processing_level_used=initial_input_dict_from_kwargs.get("processing_level", "unknown_level_in_tool_exc"),
                error_message=str(e)
            ).model_dump()

# --- Add more tools for other agent methods below ---
# Example: PDF Acquirer Tool
# from app.agents.pdf_acquisition_agent import PDFAcquisitionAgent
# from app.models.pdf_acquisition_models import PDFAcquisitionInput
# class PDFAcquisitionToolInput(BaseModel):
#     pdf_acquisition_input_dict: Dict[str, Any]
# class PDFAcquisitionTool(BaseTool):
#     name: str = "PDF Acquisition Tool"
#     description: str = "Processes a PDF file to extract text and image data."
#     args_schema: Type[BaseModel] = PDFAcquisitionToolInput
#     agent_logic: PDFAcquisitionAgent
#     def __init__(self, agent_logic: PDFAcquisitionAgent, **kwargs: Any): super().__init__(**kwargs); self.agent_logic = agent_logic
#     def _run(self, pdf_acquisition_input_dict: Dict[str, Any]) -> Dict[str, Any]:
#         pdf_input = PDFAcquisitionInput(**pdf_acquisition_input_dict)
#         output_model = self.agent_logic.execute_pdf_processing(pdf_input)
#         return output_model.model_dump() 