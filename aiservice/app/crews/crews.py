# Main file to define and orchestrate Crews
from crewai import Crew, Process, Agent, Task # Keep these core crewai imports
from typing import Any # Keep basic typing

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

# --- Step 5: Re-activate Web Tools ---
from aiservice.app.tools.web_tools import (
    HTTPFetchingTool, TrafilaturaContentExtractorTool, 
    BeautifulSoupImageExtractorTool, PaywallDetectionTool
)

# --- Step 6: Re-activate ALL Content Processing Tools ---
from aiservice.app.tools.content_processing_tools import (
    ImageDownloaderTool, 
    GCSUploadTool, 
    ImageMetadataTool 
)
from aiservice.app.config import get_gcs_bucket_name 

from aiservice.app.tools.llm_interaction_tools import (
    MultimodalLLMImageMarkerTool, AdvancedLLMStructuringTool,
    openai_client_instance 
)

class CrewFactory:
    """Factory class to create and configure different crews."""

    def __init__(self):
        """Initializes the factory, loads configurations, and instantiates tools and agents."""
        print("CrewFactory: Initializing... (Re-activating ALL Content Processing Tools)")
        
        # --- LLM Tool Initializations (Active) ---
        self.multimodal_marker_tool = MultimodalLLMImageMarkerTool(client=openai_client_instance)
        # print("CrewFactory: MultimodalLLMImageMarkerTool initialized.") # Reduce noise
        self.advanced_structuring_tool = AdvancedLLMStructuringTool(client=openai_client_instance)
        # print("CrewFactory: AdvancedLLMStructuringTool initialized.")

        # --- Initialize Agent Creators & Core Agents (Active) ---
        self.orchestration_agent_creator = OrchestrationAgent()
        self.pdf_agent_creator = PDFContentAcquisitionAgent()
        self.generic_file_agent_creator = GenericFileContentAcquisitionAgent()
        self.web_url_agent_creator = WebURLContentAcquisitionAgent()
        self.image_processing_agent_creator = ImageProcessingPersistenceAgent()
        self.content_structuring_agent_creator = ContentConsolidationStructuringAgent()
        # print("CrewFactory: Agent creators initialized.")
        
        self.main_orchestrator = self.orchestration_agent_creator.main_orchestration_agent()
        self.pdf_acquirer = self.pdf_agent_creator.pdf_acquisition_agent()
        self.generic_file_acquirer = self.generic_file_agent_creator.generic_file_acquisition_agent()
        self.web_url_acquirer = self.web_url_agent_creator.web_url_acquisition_agent()
        self.image_processor = self.image_processing_agent_creator.image_processing_agent()
        self.content_structurer = self.content_structuring_agent_creator.content_structuring_agent()
        # print("CrewFactory: Core agents instantiated.")

        # --- Initialize Task Definition Helpers (Now active) --- 
        self.orch_tasks_def = OrchestrationTasks()
        self.pdf_tasks_def = PDFAcquisitionTasks()
        self.generic_tasks_def = GenericFileAcquisitionTasks()
        self.web_tasks_def = WebURLAcquisitionTasks()
        self.img_proc_tasks_def = ImageProcessingTasks()
        self.struct_tasks_def = ContentStructuringTasks()
        print("CrewFactory: Task definition helpers initialized.")

        # --- Initialize ContentTypeDetectionTool --- (Re-activating)
        self.content_type_tool = ContentTypeDetectionTool()
        print("CrewFactory: ContentTypeDetectionTool initialized.")

        # --- GCSUploadTool Initialization (Re-activating) ---
        self.gcs_upload_tool = GCSUploadTool(gcs_bucket_name=get_gcs_bucket_name()) 
        print("CrewFactory: GCSUploadTool initialized.")

        # --- Initialize Data Extraction Tools (Re-activating) ---
        self.pymupdf_parser_tool = PyMuPDFParserTool()
        self.nougat_parser_tool = NougatPDFParserTool() # Placeholder, requires setup for actual use
        self.pdf_to_image_tool = PDFToImageTool()
        self.pdfminer_tool = PDFMinerSixParserTool() 
        self.docx_parser_tool = DocxParserTool()
        self.txt_parser_tool = TxtParserTool()
        self.md_parser_tool = MarkdownParserTool()
        print("CrewFactory: Data Extraction Tools initialized.")

        # --- Initialize Web Tools (Re-activating) ---
        self.http_fetching_tool = HTTPFetchingTool()
        self.trafilatura_tool = TrafilaturaContentExtractorTool()
        self.bs_image_tool = BeautifulSoupImageExtractorTool()
        self.paywall_tool = PaywallDetectionTool()
        print("CrewFactory: Web Tools initialized.")

        # --- Initialize ALL Content Processing Tools (Re-activating) ---
        self.image_downloader_tool = ImageDownloaderTool()
        self.image_metadata_tool = ImageMetadataTool()
        print("CrewFactory: ALL Content Processing Tools initialized.")

        print("CrewFactory: Initialization complete (ALL Tools Active).")

    def create_core_reconstruction_crew(self, crew_input: dict = None) -> Crew:
        """Creates and configures the CoreReconstructionCrew with tasks based on input."""
        print("CrewFactory: Creating CoreReconstructionCrew... (ALL Tools Active)")
        if crew_input is None:
            crew_input = {} 
            
        agents_list_for_crew = [
            self.main_orchestrator,
            self.pdf_acquirer,
            self.generic_file_acquirer,
            self.web_url_acquirer,
            self.image_processor,
            self.content_structurer
        ]
        initial_tasks_for_crew = []

        # Add initial tasks if input is present and task defs are available
        if crew_input.get("source_type") and crew_input.get("source_identifier"):
            validate_input_task = self.orch_tasks_def.input_validation_task(
                agent=self.main_orchestrator,
                source_type=crew_input['source_type'],
                source_identifier=crew_input['source_identifier']
            )
            initial_tasks_for_crew.append(validate_input_task)

            detect_content_type_task = self.orch_tasks_def.content_type_detection_task(
                agent=self.main_orchestrator, 
                validated_identifier=crew_input['source_identifier'],
                source_type=crew_input['source_type']
            )
            initial_tasks_for_crew.append(detect_content_type_task)
            print(f"CrewFactory: Added initial validation and detection tasks for {crew_input['source_identifier']}")

        # Assign tools to relevant agents
        self.main_orchestrator.tools = [self.content_type_tool]
        self.pdf_acquirer.tools = [
            self.pymupdf_parser_tool, self.nougat_parser_tool, 
            self.pdf_to_image_tool, self.pdfminer_tool,
            self.multimodal_marker_tool # LLM tool for PDF images
        ]
        self.generic_file_acquirer.tools = [
            self.docx_parser_tool, self.txt_parser_tool, self.md_parser_tool
        ]
        self.web_url_acquirer.tools = [
            self.http_fetching_tool, self.trafilatura_tool,
            self.bs_image_tool, self.paywall_tool
        ]
        self.image_processor.tools = [
            self.image_downloader_tool, self.gcs_upload_tool, self.image_metadata_tool
        ] 
        self.content_structurer.tools = [self.advanced_structuring_tool] # Assign explicitly

        print(f"CrewFactory: Proceeding with {len(agents_list_for_crew)} agents and {len(initial_tasks_for_crew)} tasks.")

        crew = Crew(
            agents=agents_list_for_crew, 
            tasks=initial_tasks_for_crew,  
            process=Process.sequential, 
            verbose=True,
        )
        print(f"CrewFactory: CoreReconstructionCrew created. Agents: {len(crew.agents)}, Tasks: {len(crew.tasks)}")
        return crew
    
if __name__ == '__main__':
    print("Running CrewFactory main... (ALL Tools Active)")
    factory = CrewFactory()
    # core_crew_instance = factory.create_core_reconstruction_crew(inputs={
    #     "source_type": "file", 
    #     "source_identifier": "./dummy.pdf" 
    # })
    # print("CoreReconstructionCrew created with initial tasks.")
    print("CrewFactory main finished (ALL Tools Active).") 