import sys
import os
import json

# Add the workspace root to sys.path
# Assumes the script is in aiservice/scripts/ and workspace root is two levels up
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

import asyncio
import time
import os # For potential path manipulation if needed for test files

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
from aiservice.app.tools.llm_tools import ImageAnalysisLLMTool, ContentStructuringLLMHelper
from aiservice.app.crews.minimal_crew import MinimalLLMCrew # Import the crew
from langchain_openai import ChatOpenAI # Ensure this is imported

# --- Test Configuration ---
# Reverted to a hardcoded URL for now to avoid AttributeError
TEST_SOURCE_IDENTIFIER = "https://medium.com/pinterest-engineering/multi-gate-mixture-of-experts-mmoe-model-architecture-and-knowledge-distillation-in-ads-08ec7f4aa857" 
# You can change this to your preferred test URL, e.g.:
# TEST_SOURCE_IDENTIFIER = "https://cloud.google.com/blog/products/ai-machine-learning/build-multilingual-chatbots-with-gemini-gemma-and-mcp"
TEST_SOURCE_TYPE = "url" 
TEST_PROCESSING_LEVEL = "full_content"

# --- Mock Settings Object (as a simple class for now) ---
# class MockSettings: # No longer needed, using actual settings
#     def __init__(self):
#         self.use_llm_for_image_analysis = False 
#         self.gcs_bucket = "your-mock-gcs-bucket" 

async def main():
    print(f"Starting E2E test for: {TEST_SOURCE_IDENTIFIER} (Type: {TEST_SOURCE_TYPE}, Level: {TEST_PROCESSING_LEVEL})\n")

    # Ensure the setting for LLM image analysis is True for this test run
    settings.use_llm_for_image_analysis = True 
    print(f"E2E Test: Forcing use_llm_for_image_analysis = {settings.use_llm_for_image_analysis}")
    if not settings.openai_api_key:
        print("E2E Test: WARNING - OpenAI API key not set in settings, LLM calls will fail!")

    # Create a single LLM instance for the agent and tools if they accept it
    shared_llm_instance = None
    if settings.openai_api_key and settings.default_llm_model:
        try:
            shared_llm_instance = ChatOpenAI(
                api_key=settings.openai_api_key,
                model_name=settings.default_llm_model 
            )
            print(f"E2E Test: Initialized shared LLM instance with model: {settings.default_llm_model}")
        except Exception as e:
            print(f"E2E Test: Failed to initialize shared LLM: {e}. Some components might fail.")
    else:
        print("E2E Test: OpenAI API key or default_llm_model not in settings. Shared LLM not initialized.")

    # 1. Initialize Tools that are passed directly to services
    # ImageAnalysisLLMTool will now attempt real calls if API key is present
    image_analysis_tool = ImageAnalysisLLMTool() 

    # 1.b Initialize Crew 
    minimal_llm_crew = MinimalLLMCrew()

    # 2. Initialize Services (inject tools and settings)
    routing_service = RoutingService(settings=settings)
    web_acquisition_service = WebAcquisitionService(settings=settings)
    pdf_acquisition_service = PDFAcquisitionService(image_analysis_tool=image_analysis_tool, settings=settings)
    file_acquisition_service = FileAcquisitionService(settings=settings)
    # ImageProcessingService will use the updated ImageAnalysisLLMTool and settings.use_llm_for_image_analysis
    image_processing_service = ImageProcessingService(image_analysis_tool=image_analysis_tool, settings=settings)
    content_structuring_service = ContentStructuringService(minimal_llm_crew=minimal_llm_crew, settings=settings)

    # 3. Initialize Orchestrator
    orchestrator = ParallelOrchestrator(
        routing_service=routing_service,
        web_acquisition_service=web_acquisition_service,
        pdf_acquisition_service=pdf_acquisition_service,
        file_acquisition_service=file_acquisition_service,
        image_processing_service=image_processing_service,
        content_structuring_service=content_structuring_service,
        settings=settings
    )

    # 4. Prepare Orchestration Input
    orchestration_input = OrchestrationInput(
        source_identifier=TEST_SOURCE_IDENTIFIER,
        source_type=TEST_SOURCE_TYPE,
        processing_level=TEST_PROCESSING_LEVEL
    )

    # 5. Run and Time the Orchestration
    start_time = time.perf_counter() # More precise for timing short durations
    service_result = await orchestrator.process(orchestration_input)
    end_time = time.perf_counter()
    duration_seconds = end_time - start_time

    # 6. Print Results
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
        # Convert ProcessedImageData to dicts for json.dumps
        images_data_as_dicts = {
            img_id: data.model_dump() for img_id, data in output_data.processed_images_data.items()
        }
        print(json.dumps(images_data_as_dicts, indent=2))

        print(f"\n--- Full Original Content Blocks ({len(output_data.original_content_blocks)}) ---")
        blocks_as_dicts = [block.model_dump() for block in output_data.original_content_blocks]
        print(json.dumps(blocks_as_dicts, indent=2))

        # Save to file for easier inspection
        output_filename = "e2e_test_output.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            full_output_dump = {
                "service_result_status": service_result.status,
                "orchestration_output": output_data.model_dump(),
                "processing_duration_seconds": duration_seconds
            }
            json.dump(full_output_dump, f, indent=2)
        print(f"\nFull OrchestrationOutput (including any errors) saved to: {output_filename}")

    else: # ServiceResult status is 'error'
        print(f"Orchestration Failed (ServiceResult status: {service_result.status}).")
        print(f"Error Message: {service_result.error_message}")
        if service_result.error_details:
            print(f"Error Details (JSON):\n{json.dumps(service_result.error_details, indent=2)}")
            output_filename = "e2e_test_error_output.json"
            with open(output_filename, "w", encoding="utf-8") as f:
                 json.dump(service_result.error_details, f, indent=2)
            print(f"Error details saved to: {output_filename}")

if __name__ == "__main__":
    # Ensure you have a test file at the specified path if testing local files.
    # For URL tests, ensure the URL is accessible.
    asyncio.run(main()) 