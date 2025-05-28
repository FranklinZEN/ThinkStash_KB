import sys
from pathlib import Path
import json
import uuid

# Adjust sys.path to include the project root directory (aiservice)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from crewai import Agent, Task, Crew, Process

# --- Model Imports ---
from app.models.orchestration_models import OrchestrationInput, OrchestrationOutput
from app.models.file_acquisition_models import FileAcquisitionInput
from app.models.web_acquisition_models import WebAcquisitionInput
from app.models.pdf_acquisition_models import PDFAcquisitionInput
from app.models.image_processing_models import ImageProcessingInput
from app.models.content_structuring_models import ContentStructuringInput

# --- Tool Imports ---
from app.tools.utility_tools import ContentTypeDetectionTool, DataStoreAccessTool
from app.tools.data_extraction_tools import (
    DocxParserTool, TxtParserTool, MarkdownParserTool,
    PyMuPDFParserTool, NougatPDFParserTool, PDFToImageTool, PDFMinerSixParserTool
)
from app.tools.web_tools import WebContentFetcherTool
from app.tools.content_processing_tools import ImageDownloaderTool, GCSUploadTool, ImageMetadataTool
from app.tools.llm_interaction_tools import MultimodalLLMImageMarkerTool, AdvancedLLMStructuringTool

# --- Custom Crew Tools ---
from crews.crew_tools import (
    InitialTriageTool, RoutingTool,
    PDFAcquisitionCrewTool, GenericFileAcquisitionCrewTool, WebURLAcquisitionCrewTool,
    ImageProcessingCrewTool, ContentStructuringCrewTool,
    ErrorAggregationCrewTool, OutputAggregationCrewTool
)

# --- Agent Imports ---
from app.agents.orchestration_agent import OrchestrationAgent as OrchestrationAgentClass
from app.agents.generic_file_acquisition_agent import GenericFileContentAcquisitionAgent as GenericFileAgentClass
from app.agents.web_url_acquisition_agent import WebURLContentAcquisitionAgent as WebAgentClass
from app.agents.pdf_acquisition_agent import PDFAcquisitionAgent as PDFAgentClass
from app.agents.image_processing_agent import ImageProcessingPersistenceAgent as ImageAgentClass
from app.agents.content_structuring_agent import ContentConsolidationStructuringAgent as StructuringAgentClass

# --- Initialize Shared Tools ---
print("Initializing shared tools for the Crew...")
# For CrewAI, agent methods will be tasks. Direct tool execution by the script is less common.
# Agents will be initialized with their tools.
# The DataStoreAccessTool needs to be shared across agents that use it.
data_store_dict = {} # In-memory data store for this run
shared_data_store_tool = DataStoreAccessTool(data_store=data_store_dict)

# Individual tools that will be passed to agents
content_type_detection_tool = ContentTypeDetectionTool()
docx_parser_tool = DocxParserTool()
txt_parser_tool = TxtParserTool()
markdown_parser_tool = MarkdownParserTool()
pymupdf_parser_tool = PyMuPDFParserTool()
nougat_parser_tool = NougatPDFParserTool()
pdf_to_image_tool = PDFToImageTool()
pdfminer_six_parser_tool = PDFMinerSixParserTool()
web_content_fetcher_tool = WebContentFetcherTool()
image_downloader_tool = ImageDownloaderTool()
gcs_upload_tool = GCSUploadTool()
image_metadata_tool = ImageMetadataTool()
multimodal_llm_marker_tool = MultimodalLLMImageMarkerTool() # Uses global openai_client_instance by default
advanced_llm_structuring_tool = AdvancedLLMStructuringTool() # Uses global openai_client_instance by default
print("Shared tools initialized.")

# --- Initialize Agents ---
# Agents are initialized here with their specific tools.
# The `Agent` class from `crewai` is different from our agent classes.
# Our classes define the logic, and we'll wrap them or call their methods within CrewAI tasks.

print("Initializing Agent Logic Classes (not CrewAI Agents yet)...")
orchestration_agent_logic = OrchestrationAgentClass(
    content_type_detection_tool=content_type_detection_tool,
    data_store_tool=shared_data_store_tool
)
pdf_agent_logic = PDFAgentClass(
    pymupdf_parser_tool=pymupdf_parser_tool,
    pdfminer_six_parser_tool=pdfminer_six_parser_tool,
    nougat_parser_tool=nougat_parser_tool,
    pdf_to_image_tool=pdf_to_image_tool,
    multimodal_llm_marker_tool=multimodal_llm_marker_tool,
    data_store_tool=shared_data_store_tool
)
generic_file_agent_logic = GenericFileAgentClass(
    docx_parser_tool=docx_parser_tool,
    txt_parser_tool=txt_parser_tool,
    markdown_parser_tool=markdown_parser_tool,
    data_store_tool=shared_data_store_tool
)
web_agent_logic = WebAgentClass(
    web_content_fetcher_tool=web_content_fetcher_tool,
    data_store_tool=shared_data_store_tool
)
image_agent_logic = ImageAgentClass(
    image_downloader_tool=image_downloader_tool,
    gcs_upload_tool=gcs_upload_tool,
    image_metadata_tool=image_metadata_tool,
    data_store_tool=shared_data_store_tool
)
structuring_agent_logic = StructuringAgentClass(
    advanced_llm_structuring_tool=advanced_llm_structuring_tool,
    data_store_tool=shared_data_store_tool
)
print("Agent Logic Classes initialized.")

# --- Instantiate Crew Tools with Agent Logic ---
print("Instantiating Crew Tools...")
initial_triage_crew_tool = InitialTriageTool(agent_logic=orchestration_agent_logic)
routing_crew_tool = RoutingTool(agent_logic=orchestration_agent_logic)
pdf_acq_crew_tool = PDFAcquisitionCrewTool(agent_logic=pdf_agent_logic, data_store_tool=shared_data_store_tool)
generic_file_acq_crew_tool = GenericFileAcquisitionCrewTool(agent_logic=generic_file_agent_logic, data_store_tool=shared_data_store_tool)
web_url_acq_crew_tool = WebURLAcquisitionCrewTool(agent_logic=web_agent_logic, data_store_tool=shared_data_store_tool)
image_processing_crew_tool = ImageProcessingCrewTool(agent_logic=image_agent_logic, data_store_tool=shared_data_store_tool)
content_structuring_crew_tool = ContentStructuringCrewTool(agent_logic=structuring_agent_logic)
error_aggregation_crew_tool = ErrorAggregationCrewTool(agent_logic=orchestration_agent_logic)
output_aggregation_crew_tool = OutputAggregationCrewTool(agent_logic=orchestration_agent_logic, data_store_tool=shared_data_store_tool)
print("Crew Tools instantiated.")

# --- Define CrewAI Agents ---
print("Defining CrewAI Agents with enhanced prompts...")

crew_orchestrator = Agent(
    role='Core Reconstruction Orchestrator and Finalizer',
    goal=(
        "Manage the initial triage and routing of a source, and then later aggregate all processing results (including errors) "
        "to produce the final comprehensive OrchestrationOutput for the CoreReconstructionCrew."
    ),
    backstory=(
        "I am the primary coordinator and finalizer for the CoreReconstructionCrew. I first perform triage using the 'Initial Triage Tool'. "
        "Later in the workflow, after all other specialist agents have completed their tasks, I will use the 'Error Aggregation Tool' "
        "and then the 'Output Aggregation Tool' to assemble the complete, final structured output, taking into account all intermediate results and errors."
    ),
    tools=[initial_triage_crew_tool, error_aggregation_crew_tool, output_aggregation_crew_tool],
    verbose=True,
    allow_delegation=False
)

crew_router = Agent(
    role='Content Processing Router',
    goal=(
        "Based on triage results (received as a JSON string from the Triage Specialist), decide the correct downstream "
        "processing path (e.g., 'route_to_pdf_agent', 'route_to_web_agent', 'route_to_generic_file_agent', or 'routing_failed_triage'). "
        "You must use the Routing Tool and output a structured dictionary as a JSON string."
    ),
    backstory=(
        "I am the efficient Content Processing Router. I receive a JSON string of triage results. My task is to parse this JSON, "
        "examine the 'detected_content_type', and use the 'Routing Tool' to determine the precise routing_decision. "
        "My output is a JSON string dictionary that includes this 'routing_decision' and other necessary parameters "
        "(like 'source_identifier', 'processing_level', 'content_type_hint') for the subsequent acquisition agent."
    ),
    tools=[routing_crew_tool],
    verbose=True,
    allow_delegation=False
)

crew_pdf_acquirer = Agent(
    role='PDF Content Acquisition Specialist',
    goal=(
        "If the routing decision (from context) is 'route_to_pdf_agent', extract all relevant content (text, images, metadata) from the specified PDF file. "
        "Use the PDF Acquisition Tool, providing it the JSON string of routing results from the previous task. "
        "Output a JSON string dictionary detailing the PDF acquisition outcome (status, text_ref, image_list_ref, etc.). "
        "If the routing decision is not for PDF, output the exact string: {}"
    ),
    backstory=(
        "I specialize in dissecting PDF documents. When a task is routed for PDF processing, I take the JSON string of routing results, "
        "parse it to get the file_path and processing_level, and then use my 'PDF Acquisition Tool' to perform tiered text parsing, "
        "convert pages to images, and invoke AI for image analysis. All extracted data references are stored, and I output a comprehensive JSON string status dictionary."
    ),
    tools=[pdf_acq_crew_tool],
    verbose=True,
    allow_delegation=False
)

crew_generic_file_acquirer = Agent(
    role='Generic File Content Acquisition Specialist (DOCX, MD, TXT)',
    goal=(
        "If the routing decision (from context) is 'route_to_generic_file_agent', extract content (text, images, code, math) from the specified DOCX, Markdown, or TXT file. "
        "Use the Generic File Acquisition Tool, providing it the JSON string of routing results. "
        "Output a JSON string dictionary detailing the acquisition outcome. "
        "If the routing decision is not for a generic file, output the exact string: {}"
    ),
    backstory=(
        "I am adept at handling common office and text file formats (DOCX, MD, TXT). When a task is routed for generic file processing, "
        "I parse the JSON string of routing results to get file_path, processing_level, and content_type_hint. "
        "I then use my 'Generic File Acquisition Tool' to extract all relevant content. My output is a structured JSON string dictionary of the results."
    ),
    tools=[generic_file_acq_crew_tool],
    verbose=True,
    allow_delegation=False
)

crew_web_acquirer = Agent(
    role='Web Content Acquisition Specialist',
    goal=(
        "If the routing decision (from context) is 'route_to_web_agent', fetch, parse, and extract primary content, images, and metadata from the specified web URL. "
        "Use the Web URL Acquisition Tool, providing it the JSON string of routing results. "
        "Output a JSON string dictionary detailing the web acquisition outcome. "
        "If the routing decision is not for a web URL, output the exact string: {}"
    ),
    backstory=(
        "I am a skilled web crawler and content extractor. When a task is routed for web URL processing, I parse the JSON string of routing results "
        "to get the URL and processing_level. I use my 'Web URL Acquisition Tool' (which internally uses WebContentFetcherTool) to handle fetching, parsing, "
        "PDF redirection, and content/image extraction. My output is a comprehensive JSON string dictionary of the results, including data store references."
    ),
    tools=[web_url_acq_crew_tool],
    verbose=True,
    allow_delegation=False
)

crew_image_processor = Agent(
    role='Image Processing and Persistence Specialist',
    goal=(
        "Process all images identified by the relevant acquisition task. This involves downloading URL-based images, "
        "uploading all valid images to GCS, consolidating metadata (captions, alt-text, dimensions, GCS URL, original ID), "
        "and outputting a JSON string dictionary with the status and a reference to the list of processed image data."
    ),
    backstory=(
        "I am the dedicated image handler. I receive context from routing and all acquisition tasks. "
        "My task description specifies the unique 'job_id' for the run. I must carefully examine the 'routing_decision' from the routing task's output "
        "to identify which acquisition task (PDF, Generic File, or Web URL) output is relevant. "
        "I then formulate the input for my 'Image Processing and Persistence Tool' using this relevant acquisition output JSON string, "
        "the routing results JSON string, and the provided 'job_id'. I ensure all images are processed and their metadata persisted."
    ),
    tools=[image_processing_crew_tool],
    verbose=True,
    allow_delegation=False
)

crew_content_structurer = Agent(
    role='Content Consolidation and Structuring Specialist',
    goal=(
        "Assemble all extracted text (from the relevant acquisition task) and processed image data (from the image processing task) "
        "into a final, well-structured set of content blocks using an LLM. Output a JSON string dictionary of these blocks and an article flag."
    ),
    backstory=(
        "I am the final architect of the reconstructed content. I receive context from routing, all acquisition tasks, and image processing. "
        "I use the 'routing_decision' to select the correct text reference and page title from the relevant acquisition task output. "
        "I use the 'image_processing_output' for the list of processed images. "
        "With this information, I use my 'Content Consolidation and Structuring Tool' to intelligently segment text, integrate image references, "
        "and determine if the content is a long article. My output is a structured JSON string dictionary."
    ),
    tools=[content_structuring_crew_tool],
    verbose=True,
    allow_delegation=False
)

print("CrewAI Agents defined with enhanced prompts.")

# --- Task Definitions ---
# This is where we'll define the tasks.
# We need to figure out how to pass data between tasks.
# CrewAI tasks can have `context` which are outputs of other tasks.
# The `agent` assigned to the task will execute its logic based on the input and context.

# --- Will continue with Task definitions and Crew assembly in the next step ---

if __name__ == '__main__':
    print("\n--- CoreReconstructionCrew Simulation (via CrewAI) ---")
    job_id_for_run = str(uuid.uuid4()) # Generate a job_id for this run
    
    source_input_dict = OrchestrationInput(
        source_type="url",
        source_identifier="https://cloud.google.com/blog/products/ai-machine-learning/build-multilingual-chatbots-with-gemini-gemma-and-mcp",
        processing_level="full_content"
    ).model_dump()

    # --- Task Definitions ---
    task_triage = Task(
        description=f"Perform initial triage for the source: {source_input_dict}. Use the Initial Triage Tool.",
        expected_output="A JSON string dictionary containing triage results: detected_content_type, normalized_identifier, processing_level, validation_status, error_message.",
        agent=crew_orchestrator
    )

    task_routing = Task(
        description="Based on triage results (context from previous task), determine processing route. Use the Routing Tool. The input for your tool is the JSON string from the previous task.",
        expected_output="A JSON string dictionary containing routing decision: routing_decision, source_identifier, processing_level, content_type_hint, error_message, and job_id.",
        agent=crew_router,
        context=[task_triage]
    )

    task_pdf_acquisition = Task(
        description=(
            "CONTEXTUAL INFO: The routing_decision from task_routing (context) determines if this task is relevant. "
            f"The current job ID for this run is '{{job_id_for_run}}'. "
            "If routing_decision is 'route_to_pdf_agent', process the PDF using the PDF Acquisition Tool. "
            "Your Action Input JSON for the tool MUST include: "
            "1. `routing_results_json_str`: The JSON string output from 'task_routing'. "
            "2. `job_id`: The string '{{job_id_for_run}}'."
        ),
        expected_output="If applicable, a JSON string dictionary detailing PDF acquisition outcome. If not applicable (based on routing_decision), output the exact string: {}",
        agent=crew_pdf_acquirer,
        context=[task_routing]
    )

    task_generic_file_acquisition = Task(
        description=(
            "CONTEXTUAL INFO: The routing_decision from task_routing (context) determines if this task is relevant. "
            f"The current job ID for this run is '{{job_id_for_run}}'. "
            "If routing_decision is 'route_to_generic_file_agent', process the file using the Generic File Acquisition Tool. "
            "Your Action Input JSON for the tool MUST include: "
            "1. `routing_results_json_str`: The JSON string output from 'task_routing'. "
            "2. `job_id`: The string '{{job_id_for_run}}'."
        ),
        expected_output="If applicable, a JSON string dictionary detailing generic file outcome. If not applicable (based on routing_decision), output the exact string: {}",
        agent=crew_generic_file_acquirer,
        context=[task_routing]
    )

    task_web_url_acquisition = Task(
        description=(
            "CONTEXTUAL INFO: The routing_decision from task_routing (context) determines if this task is relevant. "
            f"The current job ID for this run is '{{job_id_for_run}}'. "
            "If routing_decision is 'route_to_web_agent', process the URL using the Web URL Acquisition Tool. "
            "Your Action Input JSON for the tool MUST include: "
            "1. `routing_results_json_str`: The JSON string output from 'task_routing'. "
            "2. `job_id`: The string '{{job_id_for_run}}'."
        ),
        expected_output="If applicable, a JSON string dictionary detailing web URL outcome. If not applicable (based on routing_decision), output the exact string: {}",
        agent=crew_web_acquirer,
        context=[task_routing]
    )

    task_image_processing = Task(
        description=(
            f"Your goal is to process images for the current job, identified by job ID '{{job_id_for_run}}'.\n"
            "You MUST use the 'Image Processing and Persistence Tool'.\n"
            "To call this tool, your Action Input JSON object MUST include these exact keys and string values:\n"
            "1. `job_id`: The string '{{job_id_for_run}}'.\n"
            "2. `routing_results_json_str`: This MUST be the direct JSON string output from the task named 'task_routing'."
            "The tool will internally use this information to find all necessary image references from the correct acquisition step."
        ),
        expected_output="A JSON string dictionary detailing image processing outcome (status, processed_image_data_list_ref).",
        agent=crew_image_processor,
        context=[task_routing] # Only needs routing results; tool fetches acquisition output from DataStore
    )

    task_content_structuring = Task(
        description=(
            """Your goal is to finalize content structuring by assembling text and image data. 
            You MUST use the 'Content Consolidation and Structuring Tool'.
            To do this, you first need to determine the `relevant_acquisition_output_json_str`:
            1. Examine the `routing_results_json_str` (output of 'task_routing') to find the `routing_decision`.
            2. If `routing_decision` is 'route_to_pdf_agent', then `relevant_acquisition_output_json_str` is the output of 'task_pdf_acquisition'.
            3. If `routing_decision` is 'route_to_generic_file_agent', then `relevant_acquisition_output_json_str` is the output of 'task_generic_file_acquisition'.
            4. If `routing_decision` is 'route_to_web_agent', then `relevant_acquisition_output_json_str` is the output of 'task_web_url_acquisition'.
            5. If the selected acquisition task's output was the literal string "{{}}" (empty JSON object), or an empty string, or null, then `relevant_acquisition_output_json_str` should be that value (e.g., "{{}}" or null if the tool argument is Optional).

            The tool requires the following arguments, which you must provide as a single JSON object for the Action Input. 
            The values for these arguments are the direct JSON string outputs from specific previous tasks or the one you just determined:
            - `routing_results_json_str`: Use the output of 'task_routing' (it's a JSON string).
            - `image_processing_output_json_str`: Use the output of 'task_image_processing' (it's a JSON string).
            - `relevant_acquisition_output_json_str`: Use the string you determined in steps 1-5.
            
            IMPORTANT: Your Action Input MUST be a single, valid JSON object. It should look EXACTLY like this (fill in the ... parts with the actual JSON strings):
            { 
              "routing_results_json_str": "...", 
              "image_processing_output_json_str": "...", 
              "relevant_acquisition_output_json_str": "..." 
            }
            Do NOT wrap this JSON object in a list ([]). Do NOT add any other text, explanations, or thoughts before or after this single JSON object for the Action Input.
            Ensure all values for the keys are correctly escaped JSON strings where expected by the tool argument types."""
        ),
        expected_output="A JSON string dictionary of the final structured content blocks and article flag, representing the ContentStructuringOutput model.",
        agent=crew_content_structurer,
        context=[
            task_routing, 
            task_pdf_acquisition, 
            task_generic_file_acquisition, 
            task_web_url_acquisition, 
            task_image_processing
        ]
    )
    
    task_error_aggregation = Task(
        description=(
            """Aggregate all errors. You MUST use the Error Aggregation Tool. 
            The tool expects specific JSON string arguments. Map these from initial kickoff inputs AND previous task outputs. 
            If a task output string for an optional argument (like pdf_acquisition_output_json_str) is the literal string "{{}}" (empty JSON object), pass that exact string "{{}}".
            Required arguments:
            1. `initial_input_dict`: Use the dictionary from kickoff_inputs['orchestration_input_dict'] ('{{orchestration_input_dict}}').
            2. `triage_results_json_str`: Output of 'task_triage'.
            3. `pdf_acquisition_output_json_str`: Output of 'task_pdf_acquisition'.
            4. `generic_file_acquisition_output_json_str`: Output of 'task_generic_file_acquisition'.
            5. `web_acquisition_output_json_str`: Output of 'task_web_url_acquisition'.
            6. `image_processing_output_json_str`: Output of 'task_image_processing'.
            7. `structuring_output_json_str`: Output of 'task_content_structuring'.
            Ensure all arguments are passed as strings where the tool expects strings."""
        ),
        expected_output="A JSON string dictionary of aggregated error information.",
        agent=crew_orchestrator,
        context=[
            task_triage, task_routing, 
            task_pdf_acquisition, task_generic_file_acquisition, task_web_url_acquisition, 
            task_image_processing, task_content_structuring
        ]
    )

    task_output_aggregation = Task(
        description=(
            """Assemble the final OrchestrationOutput. You MUST use the Output Aggregation Tool. 
            The tool requires specific JSON string arguments from kickoff inputs and previous task outputs. 
            If a task output string for an optional argument (like pdf_acquisition_output_json_str) is the literal string "{{}}", pass that exact string "{{}}".
            Required arguments:
            1. `initial_input_dict`: Use the dictionary from kickoff_inputs['orchestration_input_dict'] ('{{orchestration_input_dict}}').
            2. `error_aggregation_results_json_str`: Output of 'task_error_aggregation'.
            3. `routing_results_json_str`: Output of 'task_routing'.
            4. `pdf_acquisition_output_json_str`: Output of 'task_pdf_acquisition'.
            5. `generic_file_acquisition_output_json_str`: Output of 'task_generic_file_acquisition'.
            6. `web_acquisition_output_json_str`: Output of 'task_web_url_acquisition'.
            7. `image_processing_output_json_str`: Output of 'task_image_processing'.
            8. `structuring_output_json_str`: Output of 'task_content_structuring'.
            Ensure all arguments are strings where the tool expects strings."""
        ),
        expected_output="A JSON string dictionary representing the complete OrchestrationOutput model.",
        agent=crew_orchestrator,
        context=[
            task_triage, task_routing, 
            task_pdf_acquisition, task_generic_file_acquisition, task_web_url_acquisition, 
            task_image_processing, task_content_structuring, 
            task_error_aggregation
        ]
    )
    
    print("All tasks, including final aggregation, are defined.")

    core_reconstruction_crew = Crew(
        agents=[
            crew_orchestrator, 
            crew_router, 
            crew_pdf_acquirer, 
            crew_generic_file_acquirer,
            crew_web_acquirer, 
            crew_image_processor, 
            crew_content_structurer
        ],
        tasks=[
            task_triage, 
            task_routing, 
            task_pdf_acquisition, 
            task_generic_file_acquisition,
            task_web_url_acquisition, 
            task_image_processing,
            task_content_structuring,
            task_error_aggregation,
            task_output_aggregation
        ],
        process=Process.sequential,
        verbose=True
    )

    print("\nKicking off the full CoreReconstructionCrew for the complete workflow...")
    try:
        kickoff_inputs = {
            'orchestration_input_dict': source_input_dict, # For task_triage
            'initial_input_json_str': json.dumps(source_input_dict), # For task_error_aggregation & task_output_aggregation
            'job_id_for_run': job_id_for_run 
        }
        crew_result = core_reconstruction_crew.kickoff(inputs=kickoff_inputs)
        
        print("\nCoreReconstructionCrew Execution Finished.")
        print("Final Result (Output of Output Aggregation Task - OrchestrationOutput):")
        
        if isinstance(crew_result, str):
            try:
                parsed_result = json.loads(crew_result)
                print("Parsed final result (JSON):")
                print(json.dumps(parsed_result, indent=2))
            except json.JSONDecodeError:
                print("Final result was a string but not parsable JSON:")
                print(crew_result)
        elif isinstance(crew_result, dict):
            print("Final result (already a dictionary):")
            print(json.dumps(crew_result, indent=2))
        else:
            print("Raw final result (unknown type):")
            print(crew_result)

    except Exception as e:
        print(f"Error during crew kickoff: {e}")
        import traceback
        traceback.print_exc()

    # print("\n--- Simulation placeholder: Run the old script for now to test full flow ---")
    # from scripts.run_core_reconstruction_crew import run_crew_simulation as run_manual_simulation
    # run_manual_simulation(
    #     source_type=source_input_dict['source_type'],
    #     source_identifier=source_input_dict['source_identifier'],
    #     processing_level=source_input_dict['processing_level']
    # ) 