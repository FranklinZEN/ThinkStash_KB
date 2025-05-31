import asyncio
import time
import uuid
from typing import Optional, Any, Dict, List, Union, Tuple
import sys

from aiservice.app.config.settings import Settings # Import the specific Settings class
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock, EnrichedImageMetadata
# Remove the old WebAcquisitionInput import from models
# from aiservice.app.models.web_acquisition_models import WebAcquisitionInput 
from aiservice.app.models.pipeline_models import EnrichedImageMetadata, DocumentMetadata, PreliminaryBlock, RawImageInput
from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.services.routing_service import RoutingService, RoutingInput
# Import the correct WebAcquisitionServiceInput from the service file
from aiservice.app.services.acquisition.web_service import WebAcquisitionService, WebAcquisitionServiceInput
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput
from aiservice.app.services.acquisition.file_service import FileAcquisitionService, FileAcquisitionServiceInput
from aiservice.app.services.processing.image_processing_service import ImageProcessingService, ImageProcessingServiceInput
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService, ContentStructuringServiceInput

# Placeholder for actual settings, data_store, and monitor when implemented
# from aiservice.app.config.settings import Settings # When available
# from aiservice.app.core.data_store import get_data_store # When available
# from aiservice.app.core.monitoring import PerformanceMonitor # When available

class ParallelOrchestrator(BaseService):
    """
    Manages the end-to-end processing flow, invoking other services in sequence or parallel.
    Integrates logic for routing, acquisition, processing, and structuring.
    """

    def __init__(self,
                 routing_service: RoutingService,
                 web_acquisition_service: WebAcquisitionService,
                 pdf_acquisition_service: PDFAcquisitionService,
                 file_acquisition_service: FileAcquisitionService,
                 image_processing_service: ImageProcessingService,
                 content_structuring_service: ContentStructuringService,
                 settings: Settings): # Use the specific Settings type
        super().__init__(settings) # BaseService now receives the typed Settings object
        self.routing_service = routing_service
        self.web_acquisition_service = web_acquisition_service
        self.pdf_acquisition_service = pdf_acquisition_service
        self.file_acquisition_service = file_acquisition_service
        self.image_processing_service = image_processing_service
        self.content_structuring_service = content_structuring_service
        self.settings: Settings = settings # Store for typed access if needed directly by orchestrator logic
        # self.data_store = get_data_store(settings) # Pass settings if data_store needs it
        # self.monitor = PerformanceMonitor(settings) # Pass settings if monitor needs it

    # @monitor.track_operation() # Add when monitor is implemented
    async def process(self, orchestrator_input: OrchestrationInput) -> ServiceResult[OrchestrationOutput]:
        """
        Main processing method for the orchestrator.
        """
        start_time = time.time()
        job_id = orchestrator_input.job_id or f"job_{uuid.uuid4().hex[:8]}"

        # Variables to hold data through the pipeline
        preliminary_blocks: List[PreliminaryBlock] = []
        document_metadata_obj: Optional[DocumentMetadata] = None
        raw_images_from_acquisition: List[RawImageInput] = []
        
        enriched_images_list: List[EnrichedImageMetadata] = []
        processed_images_data_dict: Dict[str, EnrichedImageMetadata] = {}
        final_content_blocks: List[ContentBlock] = []
        
        # final_status_code will be updated based on outcomes. Start with assumption of overall success until a failure.
        # Let specific failure points set specific failure codes.
        # If all main steps (acq, img, struct) complete, it's 'success'.
        # If a non-critical step like image processing fails but others succeed, it will be a partial success.
        final_status_code = "success" # Initialize to success, will be changed on any failure
        error_message: Optional[str] = None
        accumulated_warnings: List[str] = [] # To store non-critical error messages
        
        # Initial values from input or defaults
        page_title: Optional[str] = orchestrator_input.source_identifier 
        final_url: Optional[str] = orchestrator_input.source_identifier
        determined_final_source_type: Optional[str] = orchestrator_input.source_type

        # 1. Routing
        initial_source_type_for_routing = orchestrator_input.source_type or RoutingService.get_source_type(orchestrator_input.source_identifier)
        if not determined_final_source_type: # If not provided in input, use routed one initially
            determined_final_source_type = initial_source_type_for_routing
        
        routing_input_obj = RoutingInput(
            source_identifier=orchestrator_input.source_identifier,
            source_type=initial_source_type_for_routing
        )
        routing_result = await self.routing_service.execute(routing_input_obj)

        if not routing_result.is_success() or not routing_result.data:
            error_message = f"Routing failed: {routing_result.error_message}"
            final_status_code = "failure_routing"
            output_obj = self._prepare_final_output(orchestrator_input, final_status_code, page_title, final_content_blocks, processed_images_data_dict, error_message, final_url, determined_final_source_type, document_metadata_obj)
            return ServiceResult.failure(error_message=error_message, error_details=output_obj.model_dump())

        determined_service_name = routing_result.data.determined_service

        # 2. Acquisition
        # All acquisition services now return ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]
        acq_result: Optional[ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]] = None

        if determined_service_name == "WebAcquisitionService":
            web_acq_input = WebAcquisitionServiceInput(
                url=orchestrator_input.source_identifier,
                processing_level=orchestrator_input.processing_level,
                job_id=job_id,
                user_id=orchestrator_input.user_id
            )
            acq_result = await self.web_acquisition_service.execute(web_acq_input)
        elif determined_service_name == "PDFAcquisitionService":
            pdf_acq_input = PDFAcquisitionServiceInput(
                file_path=orchestrator_input.source_identifier, # Can be path or URL if service handles downloads
                processing_level=orchestrator_input.processing_level,
                job_id=job_id,
                user_id=orchestrator_input.user_id
            )
            acq_result = await self.pdf_acquisition_service.execute(pdf_acq_input)
        elif determined_service_name == "FileAcquisitionService":
            file_acq_input = FileAcquisitionServiceInput(
                file_path=orchestrator_input.source_identifier,
                source_content_type=initial_source_type_for_routing, # file service might refine this
                processing_level=orchestrator_input.processing_level,
                job_id=job_id,
                user_id=orchestrator_input.user_id
            )
            acq_result = await self.file_acquisition_service.execute(file_acq_input)
        else:
            error_message = f"Unknown or unsupported service determined by router: {determined_service_name}"
            final_status_code = "failure_routing"
            acq_result = ServiceResult.failure(error_message=error_message) # type: ignore

        # Process Acquisition Result
        if not acq_result or not acq_result.is_success() or not acq_result.data:
            error_message = f"{determined_service_name} failed: {acq_result.error_message if acq_result else 'Acquisition service not called'}"
            final_status_code = "failure_acquisition"
            # Try to get DocumentMetadata even on failure if it's available in error_details
            if acq_result and acq_result.error_details and isinstance(acq_result.error_details, dict):
                original_data_on_fail = acq_result.error_details.get("original_data")
                if isinstance(original_data_on_fail, tuple) and len(original_data_on_fail) == 3 and isinstance(original_data_on_fail[1], DocumentMetadata):
                    document_metadata_obj = original_data_on_fail[1]
                    page_title = document_metadata_obj.title or page_title
                    final_url = document_metadata_obj.final_url or final_url
                    determined_final_source_type = document_metadata_obj.source_type or determined_final_source_type
                    
            output_obj = self._prepare_final_output(orchestrator_input, final_status_code, page_title, final_content_blocks, processed_images_data_dict, error_message, final_url, determined_final_source_type, document_metadata_obj)
            return ServiceResult.failure(error_message=error_message, error_details=output_obj.model_dump())
        
        # Successfully got data from acquisition service
        preliminary_blocks, document_metadata_obj, raw_images_from_acquisition = acq_result.data
        
        # Update orchestrator's view of metadata based on what acquisition returned
        page_title = document_metadata_obj.title or page_title
        final_url = document_metadata_obj.final_url or final_url
        determined_final_source_type = document_metadata_obj.source_type # This is the most authoritative source_type

        # 3. Image Processing (if images were acquired)
        if raw_images_from_acquisition:
            img_processing_input = ImageProcessingServiceInput(images_to_process=raw_images_from_acquisition)
            img_processing_result = await self.image_processing_service.execute(img_processing_input)

            if not img_processing_result.is_success() or not img_processing_result.data:
                warning_msg = f"ImageProcessingService failed: {img_processing_result.error_message}"
                accumulated_warnings.append(warning_msg)
                print(f"Orchestrator Warning: {warning_msg}") # Or use self.logger
                if final_status_code == "success": 
                    final_status_code = "partial_success_image_processing_failed"
            else:
                enriched_images_list = img_processing_result.data
                processed_images_data_dict = {img.image_id: img for img in enriched_images_list}
        
        # 4. Content Structuring
        if not self.content_structuring_service:
            # This case should ideally not happen if DI is correct and service is mandatory.
            print("ERROR Orchestrator: self.content_structuring_service IS NONE.", file=sys.stderr) # Keep this critical error log
            output_obj = self._prepare_final_output(orchestrator_input, "failure_system_configuration", page_title, final_content_blocks, processed_images_data_dict, "ContentStructuringService not available", final_url, determined_final_source_type, document_metadata_obj)
            return ServiceResult.failure(error_message="ContentStructuringService not available", error_details=output_obj.model_dump())

        structuring_input = ContentStructuringServiceInput(
            preliminary_blocks=preliminary_blocks,
            enriched_images=enriched_images_list, 
            document_metadata=document_metadata_obj,
            job_id=job_id,
            user_id=orchestrator_input.user_id
        )

        structuring_result = await self.content_structuring_service.execute(structuring_input)

        if not structuring_result.is_success() or not structuring_result.data:
            error_message = f"ContentStructuringService failed: {structuring_result.error_message}" 
            final_status_code = "failure_structuring"
            # Even if structuring fails, we might have partial data (e.g., metadata, images)
            # So, we still prepare output but mark as failure.
        else:
            final_content_blocks = structuring_result.data
            # If structuring succeeded, final_status_code remains what it was before this step
            # (e.g., "success" or "partial_success_image_processing_failed")
            pass # No change to final_status_code if it was already success or partial_success

        # Consolidate error_message for the final output if it was from a warning (partial success)
        if final_status_code.startswith("partial_success") and not error_message and accumulated_warnings:
            error_message = "; ".join(accumulated_warnings)

        # If acquisition had an issue but we tried to proceed, ensure status reflects that if no other critical error occurred
        # This check is a bit redundant now with how final_status_code is managed but kept for safety.
        # if final_status_code == "success" and acq_result and not acq_result.is_success():
        # final_status_code = "partial_success_acquisition_had_issues"


        # 5. Prepare Final Output
        duration = time.time() - start_time
        print(f"Orchestrator: Job {job_id} completed in {duration:.2f}s with status: {final_status_code}")

        output_obj = self._prepare_final_output(
            orchestrator_input, 
            final_status_code, 
            page_title, 
            final_content_blocks, 
            processed_images_data_dict, 
            error_message, 
            final_url, 
            determined_final_source_type,
            document_metadata_obj # Pass the complete DocumentMetadata object
        )
        
        if final_status_code == "success" or final_status_code.startswith("partial_success"):
            return ServiceResult.success(data=output_obj)
        else:
            # For critical failures, error_message should already be set.
            # The output_obj contains all data gathered up to the point of failure.
            return ServiceResult.failure(error_message=error_message or "Orchestration failed with no specific message.", error_details=output_obj.model_dump())
    
    def _prepare_final_output(self, 
                              inp: OrchestrationInput, 
                              status: str, 
                              title: Optional[str],
                              blocks: List[ContentBlock],
                              images_data: Dict[str, EnrichedImageMetadata],
                              err_msg: Optional[str],
                              final_url_val: Optional[str],
                              actual_source_type: Optional[str],
                              doc_meta: Optional[DocumentMetadata] # Ensure this is DocumentMetadata
                              ) -> OrchestrationOutput:
        
        # Ensure doc_meta is used if available, otherwise construct a minimal one
        # This part might need refinement if doc_meta from acquisition is guaranteed on success
        # and a placeholder is needed on acquisition failure.
        
        # If doc_meta is provided (i.e., acquisition was at least partially successful to yield it), use it.
        # Otherwise, the OrchestrationOutput.document_metadata will be None or a minimal default.
        # The current structure passes document_metadata_obj which could be None if acquisition fully failed early.

        output_user_id = None
        output_document_id = None
        if doc_meta:
            output_user_id = doc_meta.user_id
            output_document_id = doc_meta.document_id
        elif inp: # Fallback to input if doc_meta is not available
            output_user_id = inp.user_id
            # document_id might be inp.job_id if doc_meta is not there
            output_document_id = inp.job_id 

        return OrchestrationOutput(
            status_code=status,
            source_identifier=inp.source_identifier,
            # Use actual_source_type if available, otherwise fallback or keep as is from input
            source_type=actual_source_type or inp.source_type or "unknown", 
            user_id=output_user_id, # Populate top-level user_id
            document_id=output_document_id, # Populate top-level document_id
            processing_level_used=inp.processing_level,
            extracted_title=title,
            is_long_article=False, # Placeholder: Implement logic if needed
            original_content_blocks=blocks,
            processed_images_data=images_data,
            document_metadata=doc_meta, # Pass the full DocumentMetadata object
            error_message=err_msg
        )

    async def execute(self, *args: Any, **kwargs: Any) -> ServiceResult[Any]:
        # Ensure BaseService's abstract method is implemented.
        # The main entry point for this orchestrator is process().
        if 'orchestrator_input' in kwargs and isinstance(kwargs['orchestrator_input'], OrchestrationInput):
            return await self.process(kwargs['orchestrator_input'])
        elif args and isinstance(args[0], OrchestrationInput):
            return await self.process(args[0])
        return ServiceResult.failure(error_message="Invalid input for ParallelOrchestrator.execute. Use process() method with OrchestrationInput.")

# Removed redundant import uuid that was here 