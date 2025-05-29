import sys
import os
import json
import uuid
import asyncio
import time

# Determine the aiservice package root and the overall project workspace root
AISERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECT_WORKSPACE_ROOT = os.path.abspath(os.path.join(AISERVICE_ROOT, '..'))

if PROJECT_WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_WORKSPACE_ROOT) # For `import aiservice`

# Import the actual settings
from aiservice.app.config.settings import settings

# Orchestrator and its input
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput
from aiservice.app.services.orchestrator import ParallelOrchestrator

# Services
from aiservice.app.services.routing_service import RoutingService
from aiservice.app.services.acquisition.web_service import WebAcquisitionService
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService
from aiservice.app.services.acquisition.file_service import FileAcquisitionService
from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService

# Tools and Crew
from aiservice.app.tools.llm_tools import ImageAnalysisLLMTool
from aiservice.app.crews.minimal_crew import MinimalLLMCrew

# ========= Test Configuration Constants =========
URL_MEDIUM_ARTICLE = "https://medium.com/walmartglobaltech/single-ai-view-of-customer-a-retailers-guide-to-know-your-customer-better-using-customer-6b588ff336bd"
URL_DIRECT_PDF = "chrome-extension://efaidnbmnnnibpcajpcglclefindmkaj/https://www.pwc.com/th/en/press-room/industry-newsletters/market-matters-newsletters/issue-3.pdf"

# Base path for local test input files within aiservice directory
LOCAL_TEST_FILES_DIR = os.path.join(AISERVICE_ROOT, "test_data", "e2e_input_files")

# Base path for test output JSON files within aiservice directory
TEST_RESULTS_DIR = os.path.join(AISERVICE_ROOT, "test_data", "e2e_test_results")

async def run_single_test(input_identifier: str, test_name: str):
    current_job_id = f"job_{test_name.lower().replace(' ', '_').replace('/', '_').replace(':','')}_{uuid.uuid4().hex[:4]}"
    
    print(f"\n--- Starting E2E test: {test_name} ---")
    print(f"Input: {input_identifier}, Job: {current_job_id}")

    if settings.use_llm_for_image_analysis:
        print(f"E2E Test: use_llm_for_image_analysis is True (from settings)")
    else:
        print(f"E2E Test: use_llm_for_image_analysis is False (from settings)")

    image_analysis_tool_instance = ImageAnalysisLLMTool()
    minimal_llm_crew = MinimalLLMCrew()
    routing_service = RoutingService(settings=settings)
    web_acquisition_service = WebAcquisitionService(settings=settings)
    pdf_acquisition_service = PDFAcquisitionService(image_analysis_llm_tool=image_analysis_tool_instance, settings=settings)
    file_acquisition_service = FileAcquisitionService(settings=settings)
    image_processing_service = ImageProcessingService(image_analysis_llm_tool=image_analysis_tool_instance, settings=settings)
    content_structuring_service = ContentStructuringService(crew=minimal_llm_crew, settings=settings)
    
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
        source_identifier=input_identifier,
        job_id=current_job_id,
        content_level="full_content",
        source_type_hint=None 
    )

    start_time = time.perf_counter()
    orchestration_output_obj: Optional[OrchestrationOutput] = None
    service_result_status_for_file = "unknown_failure"
    service_result_error_message = "No error message captured"
    raw_service_result_error_details = None

    try:
        service_result = await orchestrator.process(orchestration_input)
        service_result_error_message = service_result.error_message
        raw_service_result_error_details = service_result.error_details

        if service_result.data and isinstance(service_result.data, OrchestrationOutput):
            orchestration_output_obj = service_result.data
            service_result_status_for_file = orchestration_output_obj.status_code
            if service_result.status != 'success':
                 print(f"E2E Test ServiceResult (with data) indicates issue: {service_result.error_message}")
        elif service_result.error_details and isinstance(service_result.error_details, OrchestrationOutput):
            orchestration_output_obj = service_result.error_details
            service_result_status_for_file = orchestration_output_obj.status_code
            print(f"E2E Test ServiceResult Error (details as OrchestrationOutput): {service_result.error_message}")
        elif service_result.error_details and isinstance(service_result.error_details, dict):
            try:
                orchestration_output_obj = OrchestrationOutput(**service_result.error_details)
                service_result_status_for_file = orchestration_output_obj.status_code
            except Exception as pydantic_err:
                print(f"E2E Test: Could not cast error_details dict to OrchestrationOutput: {pydantic_err}")
                service_result_status_for_file = service_result.status or "dict_cast_error"
            print(f"E2E Test ServiceResult Error (details as dict): {service_result.error_message}")
        else:
            service_result_status_for_file = service_result.status or "error_no_output_data"
            print(f"E2E Test ServiceResult Error: {service_result.error_message}. No detailed OrchestrationOutput.")

    except Exception as e:
        print(f"E2E Test CRITICAL ERROR during orchestrator.process for {test_name}: {e}")
        import traceback
        traceback.print_exc()
        service_result_status_for_file = "critical_exception"
        service_result_error_message = str(e)
    
    end_time = time.perf_counter()
    processing_time = end_time - start_time

    # Ensure TEST_RESULTS_DIR exists
    os.makedirs(TEST_RESULTS_DIR, exist_ok=True)

    print(f"--- Results for: {test_name} ---")
    safe_test_name = test_name.lower().replace(' ', '_').replace('/', '_').replace(':', '') \
                                  .replace('(', '').replace(')', '').replace('.', '')

    if orchestration_output_obj:
        print(f"Total Processing Time: {processing_time:.4f} seconds")
        print(f"Orchestration Status Code: {orchestration_output_obj.status_code}")
        print(f"Source Identifier: {orchestration_output_obj.source_identifier}")
        print(f"Extracted Title: {orchestration_output_obj.extracted_title}")
        if orchestration_output_obj.error_message:
            print(f"Message: {orchestration_output_obj.error_message}")
        
        output_filename = os.path.join(TEST_RESULTS_DIR, f"e2e_output_{safe_test_name}_{current_job_id}.json")
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(orchestration_output_obj.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"Full output saved to: {output_filename}")
    else:
        print(f"E2E Test ERROR: OrchestrationOutput object was not created for {test_name} (status: {service_result_status_for_file}). Processing time: {processing_time:.4f}s.")
        output_filename = os.path.join(TEST_RESULTS_DIR, f"e2e_error_{safe_test_name}_{current_job_id}.json")
        error_info = {
            "test_name": test_name,
            "input_identifier": input_identifier,
            "job_id": current_job_id,
            "status_for_file": service_result_status_for_file,
            "final_error_message_from_service_result": service_result_error_message,
            "raw_error_details_from_service_result": raw_service_result_error_details,
            "processing_time_seconds": processing_time
        }
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(error_info, f, indent=2, ensure_ascii=False)
        print(f"Minimal error info saved to: {output_filename}")

    print(f"--- Finished E2E test: {test_name} ---")

async def main():
    # Create base directory for local test files if it doesn't exist
    if not os.path.exists(LOCAL_TEST_FILES_DIR):
        try:
            os.makedirs(LOCAL_TEST_FILES_DIR)
            print(f"Created directory for local test files: {LOCAL_TEST_FILES_DIR}")
        except OSError as e:
            print(f"Error creating directory {LOCAL_TEST_FILES_DIR}: {e}. Please ensure the base path is writable or create it manually.")
            return
    
    # Define local file paths using LOCAL_TEST_FILES_DIR
    file_pdf_path = os.path.join(LOCAL_TEST_FILES_DIR, "Embedding-Based Retrieval for Airbnb Search.pdf")
    file_docx_path = os.path.join(LOCAL_TEST_FILES_DIR, "Fulfillment Planning Deep Research Paper.docx")
    file_md_path = os.path.join(LOCAL_TEST_FILES_DIR, "Product Requirement Document - Knowledge Card System v3.8.md")
    file_txt_path = os.path.join(LOCAL_TEST_FILES_DIR, "plain_text_example.txt") 
    file_csv_unknown_path = os.path.join(LOCAL_TEST_FILES_DIR, "sample_data.csv") 
    file_py_unknown_path = os.path.join(LOCAL_TEST_FILES_DIR, "some_python_code.py")
    file_zip_binary_path = os.path.join(LOCAL_TEST_FILES_DIR, "small_archive.zip") 
    file_no_ext_path = os.path.join(LOCAL_TEST_FILES_DIR, "filewithnoextension")

    test_files_to_create = {
        file_txt_path: "This is a simple plain text file for testing file acquisition.\nIt has a few lines.",
        file_csv_unknown_path: "header1,header2\ndata1,data2\ndata3,data4",
        file_py_unknown_path: "# This is a python file\nprint(\"Hello world\")\ndef some_func():\n  pass",
        file_no_ext_path: "This is a file with no extension."
    }
    for file_path, content in test_files_to_create.items():
        if not os.path.exists(file_path):
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Created dummy file: {file_path}")
            except IOError as e:
                print(f"Error creating dummy file {file_path}: {e}. Check permissions and path.")
    
    if not os.path.exists(file_zip_binary_path):
        import zipfile
        try:
            with zipfile.ZipFile(file_zip_binary_path, 'w') as zf:
                zf.writestr("dummy.txt", "dummy content")
            print(f"Created dummy file: {file_zip_binary_path}")
        except IOError as e:
            print(f"Error creating dummy zip file {file_zip_binary_path}: {e}. Check permissions and path.")

    test_cases = [
        {"name": "URL Medium Article", "input": URL_MEDIUM_ARTICLE},
        {"name": "URL Direct PDF", "input": URL_DIRECT_PDF},
        {"name": "Local PDF File", "input": file_pdf_path},
        {"name": "Local DOCX File", "input": file_docx_path},
        {"name": "Local MD File", "input": file_md_path},
        {"name": "Local TXT File", "input": file_txt_path},
        {"name": "Local CSV (Unknown Ext)", "input": file_csv_unknown_path},
        {"name": "Local PY (Unknown Ext)", "input": file_py_unknown_path},
        {"name": "Local ZIP (Binary Unknown Ext)", "input": file_zip_binary_path},
        {"name": "Local File No Extension", "input": file_no_ext_path},
    ]

    runnable_test_cases = []
    for tc in test_cases:
        if tc["input"].startswith("http://") or tc["input"].startswith("https://"):
            runnable_test_cases.append(tc)
        elif os.path.exists(tc["input"]):
            runnable_test_cases.append(tc)
        else:
            print(f"Skipping test '{tc['name']}' because input file not found: {tc['input']}")

    for test_case in runnable_test_cases:
        await run_single_test(test_case["input"], test_case["name"])
        print("-----------------------------------------------------")
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main()) 