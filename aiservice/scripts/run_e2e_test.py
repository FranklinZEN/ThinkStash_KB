import sys
import os
import json
import uuid
import asyncio
import time

# Add the workspace root to sys.path
# Assumes the script is in aiservice/scripts/ and workspace root is two levels up
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

# Redundant imports removed for clarity below, assuming they are covered by the first set
# import asyncio
# import time
# import os 

# Import the actual settings
from aiservice.app.config.settings import settings

# Orchestrator and its input
from aiservice.app.models.orchestration_models import OrchestrationInput
from aiservice.app.services.orchestrator import ParallelOrchestrator

# Services (import all that ParallelOrchestrator needs)
from aiservice.app.services.routing_service import RoutingService
from aiservice.app.services.acquisition.web_service import WebAcquisitionService
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService
from aiservice.app.services.acquisition.file_service import FileAcquisitionService
from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService

# Tools (import tools that services need)
from aiservice.app.tools.llm_tools import ImageAnalysisLLMTool # ContentStructuringLLMHelper is used by MinimalLLMCrew
from aiservice.app.crews.minimal_crew import MinimalLLMCrew # Import the crew
from langchain_openai import ChatOpenAI # Ensure this is imported

# --- Test Configuration ---
# Reverted to a hardcoded URL for now to avoid AttributeError
# TEST_SOURCE_IDENTIFIER = "https://medium.com/walmartglobaltech/single-ai-view-of-customer-a-retailers-guide-to-know-your-customer-better-using-customer-6b588ff336bd" 
# You can change this to your preferred test URL, e.g.:
# TEST_SOURCE_IDENTIFIER = "https://cloud.google.com/blog/products/ai-machine-learning/build-multilingual-chatbots-with-gemini-gemma-and-mcp"
# TEST_SOURCE_TYPE = "url" 
# TEST_PROCESSING_LEVEL = "full_content"

# --- Mock Settings Object (as a simple class for now) ---
# class MockSettings: # No longer needed, using actual settings
#     def __init__(self):
#         self.use_llm_for_image_analysis = False 
#         self.gcs_bucket = "your-mock-gcs-bucket" 


async def main():
    # --- Test Configuration ---
    pdf_file_path = r"E:\ThinkStash\documentation\AI Agents Testing File\Embedding-Based Retrieval for Airbnb Search.pdf"
    docx_file_path = r"E:\ThinkStash\documentation\AI Agents Testing File\Fulfillment Planning Deep Research Paper.docx"
    md_file_path = r"E:\ThinkStash\documentation\AI Agents Testing File\Product Requirement Document - Knowledge Card System v3.8.md"
    # url_test_identifier = "https://medium.com/walmartglobaltech/single-ai-view-of-customer-a-retailers-guide-to-know-your-customer-better-using-customer-6b588ff336bd"
    # TEST_SOURCE_IDENTIFIER = "https://cloud.google.com/blog/products/ai-machine-learning/build-multilingual-chatbots-with-gemini-gemma-and-mcp"

    # --- Select the test case ---
    current_test_identifier = docx_file_path  # CHANGED TO DOCX
    current_test_type = "docx"              # CHANGED TO DOCX
    # --- End Test Case Selection ---
    
    current_processing_level = "full_content"
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    print(f"Starting E2E test for: {current_test_identifier} (Type: {current_test_type}, Level: {current_processing_level}, Job: {job_id})\n")

    settings.use_llm_for_image_analysis = True 
    print(f"E2E Test: Forcing use_llm_for_image_analysis = {settings.use_llm_for_image_analysis}")
    if not settings.openai_api_key:
        print("E2E Test: WARNING - OpenAI API key not set in settings, LLM calls will fail!")

    # MOVED INITIALIZATIONS AND PROCESSING LOGIC INSIDE main()
    image_analysis_tool = ImageAnalysisLLMTool()
    minimal_llm_crew = MinimalLLMCrew()
    routing_service = RoutingService(settings=settings)
    web_acquisition_service = WebAcquisitionService(settings=settings)
    pdf_acquisition_service = PDFAcquisitionService(image_analysis_tool=image_analysis_tool, settings=settings)
    file_acquisition_service = FileAcquisitionService(settings=settings)
    image_processing_service = ImageProcessingService(image_analysis_tool=image_analysis_tool, settings=settings)
    content_structuring_service = ContentStructuringService(minimal_llm_crew=minimal_llm_crew, settings=settings)

    orchestrator = ParallelOrchestrator(
        routing_service=routing_service,
        web_acquisition_service=web_acquisition_service,
        pdf_acquisition_service=pdf_acquisition_service,
        file_acquisition_service=file_acquisition_service,
        image_processing_service=image_processing_service,
        content_structuring_service=content_structuring_service,
        settings=settings
    )

    orchestration_input = OrchestrationInput(
        source_identifier=current_test_identifier,
        source_type=current_test_type,
        processing_level=current_processing_level,
        job_id=job_id
    )

    test_start_time = time.perf_counter()
    service_result = await orchestrator.process(orchestration_input)
    test_end_time = time.perf_counter()
    duration_seconds = test_end_time - test_start_time

    print(f"\n--- E2E Test Results ---")
    print(f"Total Processing Time: {duration_seconds:.4f} seconds")

    if service_result.data:
        output_data = service_result.data
        print(f"Orchestration Status Code: {output_data.status_code}")
        print(f"Source Identifier: {output_data.source_identifier}")
        print(f"Extracted Title: {output_data.extracted_title}")
        
        if output_data.error_message:
            print(f"Orchestration Error Message: {output_data.error_message}")

        print(f"\n--- Full Processed Images Data ({len(output_data.processed_images_data)} images) ---")
        images_data_as_dicts = {
            img_id: data.model_dump(exclude_none=True) for img_id, data in output_data.processed_images_data.items()
        }
        print(json.dumps(images_data_as_dicts, indent=2))

        print(f"\n--- Full Original Content Blocks ({len(output_data.original_content_blocks)}) ---")
        blocks_as_dicts = [block.model_dump(exclude_none=True) for block in output_data.original_content_blocks]
        print(json.dumps(blocks_as_dicts, indent=2))

        output_filename = "e2e_test_output.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            full_output_dump = {
                "service_result_status": service_result.status,
                "orchestration_output": output_data.model_dump(exclude_none=True),
                "processing_duration_seconds": duration_seconds
            }
            json.dump(full_output_dump, f, indent=2)
        print(f"\nFull OrchestrationOutput (including any errors) saved to: {output_filename}")

    else:
        print(f"Orchestration Failed (ServiceResult status: {service_result.status}).")
        print(f"Error Message: {service_result.error_message}")
        if service_result.error_details:
            print(f"Error Details (JSON):\n{json.dumps(service_result.error_details, indent=2)}")
            output_filename = "e2e_test_error_output.json"
            with open(output_filename, "w", encoding="utf-8") as f:
                 json.dump(service_result.error_details, f, indent=2)
            print(f"Error details saved to: {output_filename}")

if __name__ == "__main__":
    asyncio.run(main()) 