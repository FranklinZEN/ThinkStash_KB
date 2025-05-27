# Main file to define and orchestrate Crews
from crewai import Crew, Process, Agent, Task # Keep these core crewai imports
from typing import Any # Keep basic typing
from langchain_openai import ChatOpenAI

# --- Step 1: Uncomment Agent Imports ---
# Import Agents
from aiservice.app.agents.orchestration_agent import OrchestrationAgent
from aiservice.app.agents.pdf_acquisition_agent import PDFContentAcquisitionAgent
from aiservice.app.agents.generic_file_acquisition_agent import GenericFileContentAcquisitionAgent
from aiservice.app.agents.web_url_acquisition_agent import WebURLContentAcquisitionAgent
from aiservice.app.agents.image_processing_agent import ImageProcessingPersistenceAgent
from aiservice.app.agents.content_structuring_agent import ContentConsolidationStructuringAgent

# --- Step 2: Uncomment Task Imports ---
# Import Tasks
from aiservice.app.tasks.orchestration_tasks import OrchestrationTasks
from aiservice.app.tasks.pdf_acquisition_tasks import PDFAcquisitionTasks
from aiservice.app.tasks.generic_file_acquisition_tasks import GenericFileAcquisitionTasks
from aiservice.app.tasks.web_url_acquisition_tasks import WebURLAcquisitionTasks
from aiservice.app.tasks.image_processing_tasks import ImageProcessingTasks
from aiservice.app.tasks.content_structuring_tasks import ContentStructuringTasks

# --- Step 3: Uncomment Utility Tool & its Init, GCS related parts ---
from aiservice.app.tools.utility_tools import ContentTypeDetectionTool 

# --- Step 4: Re-activate Data Extraction Tools ---
from aiservice.app.tools.data_extraction_tools import (
    PyMuPDFParserTool, NougatPDFParserTool, PDFToImageTool,
    DocxParserTool, TxtParserTool, MarkdownParserTool, PDFMinerSixParserTool
)

# --- Step 5: Updated Web Tool Import ---
from aiservice.app.tools.web_tools import WebContentFetcherTool # Changed import

# --- Step 6: Re-activate ALL Content Processing Tools ---
from aiservice.app.tools.content_processing_tools import (
    ImageDownloaderTool, 
    GCSUploadTool, 
    ImageMetadataTool 
)
from aiservice.app.config import get_gcs_bucket_name, get_openai_api_key

from aiservice.app.tools.llm_interaction_tools import (
    MultimodalLLMImageMarkerTool, AdvancedLLMStructuringTool,
    openai_client_instance
)

class CrewFactory:
    """Factory class to create and configure different crews."""

    # --- LLM Configuration --- #
    DEFAULT_LLM_NAME = "gpt-4o-mini" # Standard, fast, cost-effective
    # DEFAULT_LLM_NAME = "models/gemini-2.0-flash" # Changed as per user request
    # DEFAULT_LLM_NAME = "gpt-4-turbo" # For tasks requiring more power
    # DEFAULT_LLM_NAME = "gpt-3.5-turbo" # For very simple, fast tasks

    def __init__(self):
        """Initializes the factory, loads configurations, and instantiates tools and agents."""
        print("CrewFactory: Initializing...")
        try:
            self.default_llm = ChatOpenAI(model=self.DEFAULT_LLM_NAME, temperature=0.2)
            print(f"CrewFactory: Default LLM ({self.DEFAULT_LLM_NAME}) initialized.")
        except Exception as e:
            print(f"CrewFactory: Failed to initialize default LLM: {e}. Ensure OPENAI_API_KEY is set.")
            self.default_llm = None

        # --- ALL TOOL INITIALIZATIONS MUST HAPPEN FIRST ---
        print("CrewFactory: Initializing Tools...")
        self.content_type_tool = ContentTypeDetectionTool()
        self.web_content_fetcher_tool = WebContentFetcherTool()

        self.pymupdf_parser_tool = PyMuPDFParserTool()
        self.nougat_parser_tool = NougatPDFParserTool()
        self.pdf_to_image_tool = PDFToImageTool()
        # self.pdfminer_tool = PDFMinerSixParserTool() # Keep commented unless needed
        
        self.docx_parser_tool = DocxParserTool()
        self.txt_parser_tool = TxtParserTool()
        self.md_parser_tool = MarkdownParserTool()

        self.image_downloader_tool = ImageDownloaderTool()
        self.gcs_upload_tool = GCSUploadTool(gcs_bucket_name=get_gcs_bucket_name())
        self.image_metadata_tool = ImageMetadataTool()
        
        self.multimodal_marker_tool = MultimodalLLMImageMarkerTool(client=openai_client_instance)
        self.advanced_structuring_tool = AdvancedLLMStructuringTool(client=openai_client_instance)
        print("CrewFactory: All standard tools initialized.")

        # --- Initialize Agent Creators, passing specific tools ---
        print("CrewFactory: Initializing Agent Creators...")
        self.orchestration_agent_creator = OrchestrationAgent(tools=[self.content_type_tool])
        self.pdf_agent_creator = PDFContentAcquisitionAgent(tools=[
            self.pymupdf_parser_tool, self.nougat_parser_tool, 
            self.pdf_to_image_tool, self.multimodal_marker_tool
        ])
        self.web_url_agent_creator = WebURLContentAcquisitionAgent(tools=[self.web_content_fetcher_tool])
        self.generic_file_agent_creator = GenericFileContentAcquisitionAgent(tools=[
            self.docx_parser_tool, self.txt_parser_tool, self.md_parser_tool
        ])
        self.image_processing_agent_creator = ImageProcessingPersistenceAgent(tools=[
            self.image_downloader_tool, self.gcs_upload_tool, self.image_metadata_tool
        ])
        self.content_structuring_agent_creator = ContentConsolidationStructuringAgent(tools=[
            self.advanced_structuring_tool
        ])
        
        # Instantiate Agents
        print("CrewFactory: Instantiating Agents...")
        self.main_orchestrator = self.orchestration_agent_creator.main_orchestration_agent()
        self.pdf_acquirer = self.pdf_agent_creator.pdf_acquisition_agent()
        self.web_url_acquirer = self.web_url_agent_creator.web_url_acquisition_agent()
        self.generic_file_acquirer = self.generic_file_agent_creator.generic_file_acquisition_agent()
        self.image_processor = self.image_processing_agent_creator.image_processing_agent()
        self.content_structurer = self.content_structuring_agent_creator.content_structuring_agent()

        # Initialize Task Definition Helpers
        print("CrewFactory: Initializing Task Definition Helpers...")
        self.orch_tasks_def = OrchestrationTasks()
        self.pdf_tasks_def = PDFAcquisitionTasks()
        self.web_tasks_def = WebURLAcquisitionTasks()
        self.generic_tasks_def = GenericFileAcquisitionTasks()
        self.img_proc_tasks_def = ImageProcessingTasks()
        self.struct_tasks_def = ContentStructuringTasks()
        print("CrewFactory: Initialization complete.")

    def create_core_reconstruction_crew(self, crew_input: dict = None) -> Crew:
        """Creates and configures the CoreReconstructionCrew with tasks based on input."""
        print("CrewFactory: Creating CoreReconstructionCrew...")
        if crew_input is None:
            crew_input = {} 
            
        initial_tasks = []

        # Add initial tasks if input is present and task defs are available
        if crew_input.get("source_type") and crew_input.get("source_identifier"):
            triage_task = self.orch_tasks_def.initial_content_triage_task(
                agent=self.main_orchestrator,
                source_type=crew_input['source_type'],
                source_identifier=crew_input['source_identifier']
            )
            initial_tasks.append(triage_task)

            if crew_input.get("source_type") == "url":
                # The output of triage_task (specifically normalized_identifier) is needed for paywall_check_task
                # We rely on the tasks list in run_crew_directly.py to set up the full sequence and context.
                # For crew creation with just initial tasks, the paywall check might be added here if it doesn't rely
                # on an output that isn't immediately available from the first task alone without execution.
                # For a robust setup, the main script calling kickoff should build the full task sequence.
                # Here, we only add triage; the paywall check is part of the sequence built in run_crew_directly.py.
                print(f"CrewFactory: Added initial_content_triage_task for URL: {crew_input['source_identifier']}")
            else:
                print(f"CrewFactory: Added initial_content_triage_task for File: {crew_input['source_identifier']}")

        # The agents list should contain all agents that might be used by any task sequence.
        all_agents = [
            self.main_orchestrator, self.pdf_acquirer, self.web_url_acquirer,
            self.generic_file_acquirer, self.image_processor, self.content_structurer
        ]

        crew = Crew(
            agents=all_agents, 
            tasks=initial_tasks, # Typically, this will be overridden by the calling script (e.g., run_crew_directly.py)
            process=Process.sequential, 
            verbose=True,
            llm=self.default_llm
        )
        print(f"CrewFactory: CoreReconstructionCrew created. Initial tasks: {len(crew.tasks)}")
        return crew
    
if __name__ == '__main__':
    print("Running CrewFactory main...")
    factory = CrewFactory()
    # Example: Create crew (will have 1 or 2 initial tasks depending on input)
    # core_crew_instance = factory.create_core_reconstruction_crew(crew_input={
    #     "source_type": "url", 
    #     "source_identifier": "https://example.com"
    # })
    # print(f"Created crew with {len(core_crew_instance.tasks)} initial tasks.")
    print("CrewFactory main finished.") 