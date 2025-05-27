# Main file to define and orchestrate Crews
from crewai import Crew, Process, Agent, Task

# Import Agents
from aiservice.app.agents.orchestration_agent import OrchestrationAgent
from aiservice.app.agents.pdf_acquisition_agent import PDFContentAcquisitionAgent
from aiservice.app.agents.generic_file_acquisition_agent import GenericFileContentAcquisitionAgent
from aiservice.app.agents.web_url_acquisition_agent import WebURLContentAcquisitionAgent
from aiservice.app.agents.image_processing_agent import ImageProcessingPersistenceAgent
from aiservice.app.agents.content_structuring_agent import ContentConsolidationStructuringAgent

# Import Tasks
from aiservice.app.tasks.orchestration_tasks import OrchestrationTasks
from aiservice.app.tasks.pdf_acquisition_tasks import PDFAcquisitionTasks
from aiservice.app.tasks.generic_file_acquisition_tasks import GenericFileAcquisitionTasks
from aiservice.app.tasks.web_url_acquisition_tasks import WebURLAcquisitionTasks
from aiservice.app.tasks.image_processing_tasks import ImageProcessingTasks
from aiservice.app.tasks.content_structuring_tasks import ContentStructuringTasks

# Import Tools
from aiservice.app.tools.utility_tools import ContentTypeDetectionTool
from aiservice.app.tools.data_extraction_tools import (
    PyMuPDFParserTool, NougatPDFParserTool, PDFToImageTool,
    DocxParserTool, TxtParserTool, MarkdownParserTool, PDFMinerSixParserTool
)
from aiservice.app.tools.web_tools import (
    HTTPFetchingTool, TrafilaturaContentExtractorTool, 
    BeautifulSoupImageExtractorTool, PaywallDetectionTool
)
from aiservice.app.tools.content_processing_tools import (
    ImageDownloaderTool, GCSUploadTool, ImageMetadataTool
)
from aiservice.app.tools.llm_interaction_tools import (
    MultimodalLLMImageMarkerTool, AdvancedLLMStructuringTool,
    openai_client # Import the globally initialized client
)

# Import Config
from aiservice.app.config import get_gcs_bucket_name, get_openai_api_key
from typing import Any # For type hinting openai_client if needed

from langchain_openai import ChatOpenAI # Add this import

class CrewFactory:
    """Factory class to create and configure different crews."""

    def __init__(self):
        """Initializes the factory, loads configurations, and instantiates tools and agents."""
        # --- Initialize LLM --- 
        # Ensure OPENAI_API_KEY is set in your environment or .env file
        try:
            self.default_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
            print("CrewFactory: Default LLM (gpt-4o-mini) initialized.")
        except Exception as e:
            print(f"CrewFactory: Failed to initialize default LLM. Error: {e}")
            print("Please ensure OPENAI_API_KEY is set and the openai package is correctly installed.")
            self.default_llm = None

        # --- Initialize Tools --- 
        self.content_type_tool = ContentTypeDetectionTool()
        self.pymupdf_parser_tool = PyMuPDFParserTool()
        self.nougat_parser_tool = NougatPDFParserTool() 
        self.pdfminer_tool = PDFMinerSixParserTool()
        self.pdf_to_image_tool = PDFToImageTool()
        self.docx_parser_tool = DocxParserTool()
        self.txt_parser_tool = TxtParserTool()
        self.md_parser_tool = MarkdownParserTool()
        self.http_fetching_tool = HTTPFetchingTool()
        self.trafilatura_tool = TrafilaturaContentExtractorTool()
        self.bs_image_tool = BeautifulSoupImageExtractorTool()
        self.paywall_tool = PaywallDetectionTool()
        self.image_downloader_tool = ImageDownloaderTool()
        self.gcs_upload_tool = GCSUploadTool(gcs_bucket_name=get_gcs_bucket_name())
        self.image_metadata_tool = ImageMetadataTool()
        self.multimodal_marker_tool = MultimodalLLMImageMarkerTool(client=openai_client)
        self.advanced_structuring_tool = AdvancedLLMStructuringTool(client=openai_client)

        # --- Initialize Agent Creators --- 
        self.orchestration_agent_creator = OrchestrationAgent()
        self.pdf_agent_creator = PDFContentAcquisitionAgent(tools=[
            self.pymupdf_parser_tool,
            self.nougat_parser_tool,
            self.pdf_to_image_tool,
            self.multimodal_marker_tool
        ])
        self.generic_file_agent_creator = GenericFileContentAcquisitionAgent()
        self.web_url_agent_creator = WebURLContentAcquisitionAgent(tools=[
            self.http_fetching_tool,
            self.trafilatura_tool,
            self.bs_image_tool,
            self.paywall_tool
        ])
        self.image_processing_agent_creator = ImageProcessingPersistenceAgent()
        self.content_structuring_agent_creator = ContentConsolidationStructuringAgent(tools=[
            self.advanced_structuring_tool
        ])
        
        # --- Instantiate Agents for CoreReconstructionCrew ---
        self.main_orchestrator = self.orchestration_agent_creator.main_orchestration_agent()
        self.pdf_acquirer = self.pdf_agent_creator.pdf_acquisition_agent()
        self.generic_file_acquirer = self.generic_file_agent_creator.generic_file_acquisition_agent()
        self.web_url_acquirer = self.web_url_agent_creator.web_url_acquisition_agent()
        self.image_processor = self.image_processing_agent_creator.image_processing_agent()
        self.content_structurer = self.content_structuring_agent_creator.content_structuring_agent()

        # --- Initialize Task Definition Helpers --- 
        self.orch_tasks_def = OrchestrationTasks()
        self.pdf_tasks_def = PDFAcquisitionTasks()
        self.generic_tasks_def = GenericFileAcquisitionTasks()
        self.web_tasks_def = WebURLAcquisitionTasks()
        self.img_proc_tasks_def = ImageProcessingTasks()
        self.struct_tasks_def = ContentStructuringTasks()

    def create_core_reconstruction_crew(self, crew_input: dict = None) -> Crew:
        """Creates and configures the CoreReconstructionCrew with tasks based on input."""
        if crew_input is None:
            crew_input = {} # Default to empty dict if no input provided
            
        initial_tasks = []
        
        # Conditionally add the initial triage task if relevant input is present
        if crew_input.get("source_type") and crew_input.get("source_identifier"):
            triage_task = self.orch_tasks_def.initial_content_triage_task(
                agent=self.main_orchestrator,
                source_type=crew_input['source_type'],
                source_identifier=crew_input['source_identifier']
            )
            initial_tasks.append(triage_task)

        return Crew(
            agents=[
                self.main_orchestrator,
                self.pdf_acquirer,
                self.generic_file_acquirer,
                self.web_url_acquirer,
                self.image_processor,
                self.content_structurer
            ],
            tasks=initial_tasks, 
            process=Process.sequential, 
            verbose=2,
            llm=self.default_llm # Set the default LLM for the crew
        )
    
    # --- Placeholder for AIRewriteSummarizeCrew ---
    # def create_ai_rewrite_summarize_crew(self):
    #     pass

if __name__ == '__main__':
    factory = CrewFactory()
    core_crew_instance = factory.create_core_reconstruction_crew(inputs={
        "source_type": "file", 
        "source_identifier": "./dummy.pdf"
    })
    print("CoreReconstructionCrew created with initial tasks.")
    print(f"Agents in crew: {[agent.role for agent in core_crew_instance.agents]}")
    print(f"Initial tasks: {[task.description for task in core_crew_instance.tasks]}")
    
    # A more complete kickoff example would be in the actual test file or API handler,
    # where the full task list is constructed based on detected content type. 