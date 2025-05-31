import asyncio
import os
import sys
import uuid
from typing import List, Dict, Any, Optional
import json # Ensure json is imported at the top level
from datetime import datetime # Ensure datetime is imported for the serializer
import argparse # Import argparse
import logging # Add logging import

# Add project root to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

from aiservice.app.config.settings import Settings
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput
from aiservice.app.services.base import ServiceResult

from aiservice.app.services.routing_service import RoutingService
from aiservice.app.services.acquisition.web_service import WebAcquisitionService
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService
from aiservice.app.services.acquisition.file_service import FileAcquisitionService
from aiservice.app.services.processing.image_processing_service import ImageProcessingService
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService
from aiservice.app.services.orchestrator import ParallelOrchestrator

# Datetime serializer for JSON output
def datetime_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# Initialize logger at module level
logger = logging.getLogger(__name__)

async def run_single_e2e_test(orchestrator: ParallelOrchestrator, source_identifier: str, source_type_hint: Optional[str] = None, user_id: Optional[str] = None):
    logger.info(f"\n{'='*30} RUNNING E2E TEST FOR: {source_identifier} ({source_type_hint or 'auto-detect'}) - User: {user_id or 'default_e2e_user'} {'='*30}")
    job_id = f"e2e_job_{uuid.uuid4().hex[:8]}"
    # Define output filename based on source_identifier for clarity, sanitizing it
    sanitized_identifier = "".join(c if c.isalnum() else "_" for c in source_identifier[:50]) # Take first 50 chars
    output_filename = os.path.join(SCRIPT_DIR, f"e2e_test_output_{sanitized_identifier}.json")
    
    orchestrator_input = OrchestrationInput(
        source_identifier=source_identifier,
        source_type=source_type_hint,
        job_id=job_id,
        user_id=user_id or "default_e2e_user",
        processing_level="full_content" # Or other relevant level
    )

    output_to_save = None
    operation_status = "unknown"

    try:
        service_result: ServiceResult[OrchestrationOutput] = await orchestrator.process(orchestrator_input)

        if service_result.is_success():
            logger.info("Orchestration Successful!")
            output_data = service_result.data
            operation_status = "success"
            if output_data: # Ensure output_data is not None
                 output_to_save = output_data.model_dump()
            else: # Should not happen if is_success() is true and data is OrchestrationOutput
                logger.warning("Warning: Orchestration successful but no data returned.")
                output_to_save = {"status_code": "success_no_data", "message": "Orchestration reported success but no data model was returned."}


            logger.info("--- OrchestrationOutput (Preview) --- ")
            if output_data:
                logger.info(f"  Status Code: {output_data.status_code}")
                logger.info(f"  Title: {output_data.extracted_title}")
                logger.info(f"  Blocks: {len(output_data.original_content_blocks) if output_data.original_content_blocks else 0}")
                logger.info(f"  Images: {len(output_data.processed_images_data) if output_data.processed_images_data else 0}")
        else:
            logger.error(f"Orchestration Failed. Error: {service_result.error_message}")
            operation_status = "failure"
            if service_result.error_details:
                output_to_save = service_result.error_details # Already a dict
                logger.error("--- Error Details (OrchestrationOutput on failure - Preview) ---")
                logger.error(f"  Status Code: {service_result.error_details.get('status_code')}")
                logger.error(f"  Error in output: {service_result.error_details.get('error_message')}")
            else: # Handle cases where error_details might be None on failure
                output_to_save = {"status_code": "failure_no_details", "error_message": service_result.error_message or "Unknown error"}
                
    except Exception as e:
        logger.critical(f"!!!!!!!!!! E2E TEST CRASHED for {source_identifier} !!!!!!!!!!", exc_info=True)
        # logger.error(f"Exception type: {type(e)}") # exc_info=True in critical will log this
        # logger.error(f"Exception: {e}") # exc_info=True in critical will log this
        # import traceback # No longer needed, exc_info=True handles it
        # traceback.print_exc() # No longer needed
        operation_status = "crash"
        output_to_save = {"error": "E2E test script crashed", "exception_type": str(type(e)), "message": str(e)}
    
    # Save the output to JSON file
    if output_to_save:
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(output_to_save, f, indent=2, default=datetime_serializer)
            logger.info(f"Successfully wrote output to {output_filename}")
        except Exception as e_write:
            logger.error(f"Error writing output to {output_filename}: {e_write}", exc_info=True)
    else:
        logger.warning(f"No output data to save for {source_identifier} (Status: {operation_status})")

    logger.info(f"{'='*30} E2E TEST COMPLETE FOR: {source_identifier} {'='*30}\n")

async def main():
    # Configure logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler(sys.stdout)]) # Ensure logs go to stdout

    # Specific logger level settings are removed as Settings(debug_mode=True) will handle it.

    parser = argparse.ArgumentParser(description="Run end-to-end tests for the orchestration pipeline.")
    parser.add_argument("source_identifier", type=str, help="The source URL or local file path to process.")
    parser.add_argument("--source_type", type=str, help="Optional: Hint for the source type (e.g., 'url', 'pdf', 'txt', 'md', 'docx'). Auto-detected if not provided.", default=None)
    parser.add_argument("--user_id", type=str, help="Optional: User ID for the test run. Defaults to 'default_e2e_user'.", default="default_e2e_user")
    args = parser.parse_args()

    # --- Instantiate REAL services ---
    settings = Settings(debug_mode=True) # Pass debug_mode=True

    routing_service = RoutingService(settings=settings)
    web_acquisition_service = WebAcquisitionService(settings=settings)
    pdf_acquisition_service = PDFAcquisitionService(settings=settings) 
    file_acquisition_service = FileAcquisitionService(settings=settings)
    image_processing_service = ImageProcessingService(settings=settings) 
    content_structuring_service = ContentStructuringService(settings=settings)

    orchestrator = ParallelOrchestrator(
        routing_service=routing_service,
        web_acquisition_service=web_acquisition_service,
        pdf_acquisition_service=pdf_acquisition_service,
        file_acquisition_service=file_acquisition_service,
        image_processing_service=image_processing_service,
        content_structuring_service=content_structuring_service,
        settings=settings
    )

    # --- Run test based on command-line arguments ---
    source_identifier_arg = args.source_identifier
    source_type_hint_arg = args.source_type
    user_id_arg = args.user_id

    is_url = source_identifier_arg.startswith("http://") or source_identifier_arg.startswith("https://") or source_identifier_arg.startswith("chrome-extension://")
    if not is_url and not os.path.exists(source_identifier_arg):
        logger.error(f"\nERROR: Local file not found: {source_identifier_arg}")
        logger.error(f"Please ensure the file exists or provide a valid URL.")
        sys.exit(1) # Exit if local file not found
        
    # Run the test once
    logger.info("\n--- E2E Test - Single Run ---")
    await run_single_e2e_test(orchestrator, source_identifier_arg, source_type_hint_arg, user_id_arg)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "cannot be called when another loop is running" in str(e):
            # Use logger if available, otherwise print (logger might not be configured if main() failed early)
            if logging.getLogger().hasHandlers():
                logger.error("Asyncio loop already running. This can happen in certain environments (e.g. Jupyter).")
                logger.error("Try running in a standard Python terminal or restart the kernel.")
            else:
                print("Asyncio loop already running. This can happen in certain environments (e.g. Jupyter).")
                print("Try running in a standard Python terminal or restart the kernel.")
        else:
            raise 