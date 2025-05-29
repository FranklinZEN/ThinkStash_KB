import asyncio
import time
import uuid
from typing import Optional, Any, Dict, List, Union

from aiservice.app.config.settings import Settings # Import the specific Settings class
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock, ProcessedImageData
# Remove the old WebAcquisitionInput import from models
# from aiservice.app.models.web_acquisition_models import WebAcquisitionInput 
from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.services.routing_service import RoutingService, RoutingInput, RoutingOutput
# Import the correct WebAcquisitionServiceInput from the service file
from aiservice.app.services.acquisition.web_service import WebAcquisitionService, WebAcquisitionServiceOutput, ProcessedWebImage, WebAcquisitionServiceInput
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput, PDFAcquisitionServiceOutput, ProcessedPDFImage
from aiservice.app.services.acquisition.file_service import FileAcquisitionService, FileAcquisitionServiceInput, FileAcquisitionServiceOutput, ProcessedFileImage
from aiservice.app.services.processing.image_processing_service import ImageProcessingService, ImageProcessingServiceInput, RawImageInput
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

    def _map_to_raw_image_input(self, acq_output: Any, job_id: str, source_identifier: str, source_type: str) -> List[RawImageInput]:
        raw_image_inputs: List[RawImageInput] = []
        images_from_acq: List[Union[ProcessedWebImage, ProcessedPDFImage, ProcessedFileImage]] = []

        if isinstance(acq_output, WebAcquisitionServiceOutput):
            images_from_acq = acq_output.images or []
        elif isinstance(acq_output, PDFAcquisitionServiceOutput):
            images_from_acq = acq_output.images or []
        elif isinstance(acq_output, FileAcquisitionServiceOutput):
            images_from_acq = acq_output.images or []

        for img in images_from_acq:
            # Correctly access image_url for ProcessedWebImage
            # For PDF/File images, image_bytes should be present if extraction was successful
            img_bytes = getattr(img, 'image_bytes', None)
            src_url = None
            if isinstance(img, ProcessedWebImage):
                src_url = img.image_url # ProcessedWebImage has image_url
            else: # For ProcessedPDFImage, ProcessedFileImage
                src_url = getattr(img, 'source_url', None) # File images might have a source_url too

            raw_image_inputs.append(RawImageInput(
                image_id=img.image_id,
                image_bytes=img_bytes,
                source_url=src_url,
                alt_text=getattr(img, 'alt_text', None),
                caption=getattr(img, 'caption', None),
                original_source_identifier_for_gcs_path=source_identifier,
                source_type_for_gcs_path=source_type,
                job_id_for_gcs_path=job_id
            ))
        print(f"Orchestrator._map_to_raw_image_input: Mapped {len(raw_image_inputs)} images for ImageProcessingService.") # DEBUG PRINT
        return raw_image_inputs

    # @monitor.track_operation() # Add when monitor is implemented
    async def process(self, orchestrator_input: OrchestrationInput) -> ServiceResult[OrchestrationOutput]:
        """
        Main processing method for the orchestrator.
        """
        start_time = time.time()
        job_id = f"job_{uuid.uuid4().hex[:8]}" # Generate a unique job ID for this run

        extracted_text: Optional[str] = None
        page_title: Optional[str] = orchestrator_input.source_identifier # Default to source_id
        processed_images_data_dict: Dict[str, ProcessedImageData] = {}
        final_content_blocks: List[ContentBlock] = []
        final_status_code = "failure_orchestration"
        error_message: Optional[str] = None
        final_url: Optional[str] = orchestrator_input.source_identifier
        
        acquisition_service_output_data: Any = None # To hold data from the called acquisition service
        raw_images_for_processing: List[RawImageInput] = []
        determined_final_source_type: Optional[str] = None # ADDED: To store the actual source type

        # 1. Routing
        # Determine initial routing based on the primary identifier (URL or file path)
        # The source_type in orchestrator_input can be a hint or None
        initial_source_type_for_routing = orchestrator_input.source_type or RoutingService.get_source_type(orchestrator_input.source_identifier)
        determined_final_source_type = initial_source_type_for_routing # Initialize with routing input type
        
        routing_input_obj = RoutingInput(
            source_identifier=orchestrator_input.source_identifier,
            source_type=initial_source_type_for_routing # Use the determined/hinted type
        )
        routing_result = await self.routing_service.execute(routing_input_obj)

        if routing_result.status == 'error' or not routing_result.data:
            error_message = f"Routing failed: {routing_result.error_message}"
            final_status_code = "failure_routing"
            # Early exit if routing fails
            output_obj = self._prepare_final_output(orchestrator_input, final_status_code, page_title, final_content_blocks, processed_images_data_dict, error_message, final_url, determined_final_source_type) # MODIFIED
            return ServiceResult.failure(error_message=error_message, error_details=output_obj.model_dump())

        determined_service_name = routing_result.data.determined_service
        # If RoutingOutput includes the determined source type, prefer that.
        # For now, we'll infer based on service or explicitly set it, e.g., for PDF redirect.
        # Example: determined_final_source_type = routing_result.data.source_type_used_for_routing

        # 2. Acquisition
        if determined_service_name == "WebAcquisitionService":
            # Use the correct WebAcquisitionServiceInput from web_service.py
            web_acq_input = WebAcquisitionServiceInput(
                url=orchestrator_input.source_identifier,
                processing_level=orchestrator_input.processing_level,
                job_id=job_id
            )
            acq_result = await self.web_acquisition_service.execute(web_acq_input)
            if acq_result.data: acquisition_service_output_data = acq_result.data
        elif determined_service_name == "PDFAcquisitionService":
            determined_final_source_type = 'pdf' # Set based on service
            pdf_acq_input = PDFAcquisitionServiceInput(
                file_path=orchestrator_input.source_identifier,
                processing_level=orchestrator_input.processing_level,
                job_id=job_id
            )
            acq_result = await self.pdf_acquisition_service.execute(pdf_acq_input)
            if acq_result.data: acquisition_service_output_data = acq_result.data
        elif determined_service_name == "FileAcquisitionService":
            # For FileAcquisitionService, source_type might be more specific (e.g., "docx", "txt")
            # We will use initial_source_type_for_routing for now, but ideally, FileAcquisitionServiceOutput
            # could provide a more precise 'file_type_processed'.
            determined_final_source_type = initial_source_type_for_routing # Or a more specific type from FileAcquisitionService if available
            file_acq_input = FileAcquisitionServiceInput(
                file_path=orchestrator_input.source_identifier,
                source_content_type=orchestrator_input.source_type, # Assuming source_type maps correctly
                processing_level=orchestrator_input.processing_level,
                job_id=job_id
            )
            acq_result = await self.file_acquisition_service.execute(file_acq_input)
            if acq_result.data: acquisition_service_output_data = acq_result.data
        else:
            error_message = f"Unknown or unsupported service determined by router: {determined_service_name}"
            final_status_code = "failure_routing"
            acq_result = ServiceResult.failure(error_message=error_message)

        # Process Acquisition Result
        if acq_result.status == 'error' or not acquisition_service_output_data:
            error_message = f"{determined_service_name} failed: {acq_result.error_message or 'Unknown error'}"
            final_status_code = "failure_acquisition"
        elif acquisition_service_output_data.status.startswith("error"): # Check status within the data model
            error_message = f"{determined_service_name} issue: {acquisition_service_output_data.status} - {acquisition_service_output_data.error_message or 'No specific message'}"
            final_status_code = f"failure_{acquisition_service_output_data.status.replace('error_', '')}" # e.g. failure_paywall
            if acquisition_service_output_data.status == "error_unsupported_content_type": final_status_code = "unsupported_type"

        # PDF Redirection Logic (New)
        elif isinstance(acquisition_service_output_data, WebAcquisitionServiceOutput) and \
             acquisition_service_output_data.status == "pdf_content_detected" and \
             acquisition_service_output_data.pdf_content_bytes:
            
            print(f"Orchestrator: PDF content detected from URL {acquisition_service_output_data.final_url}. Redirecting to PDFAcquisitionService.")
            determined_final_source_type = 'pdf' # MODIFIED: Crucial update for PDF redirect
            # Original URL/final URL from web acquisition becomes the identifier for PDF processing
            pdf_identifier = acquisition_service_output_data.final_url or orchestrator_input.source_identifier

            pdf_acq_input_redirect = PDFAcquisitionServiceInput(
                file_path=pdf_identifier, # Use URL as identifier, bytes are primary
                pdf_bytes=acquisition_service_output_data.pdf_content_bytes,
                processing_level=orchestrator_input.processing_level,
                job_id=job_id,
                # Pass original URL to PDFAcquisitionService if needed for context or ID generation.
                # This might require adding a field to PDFAcquisitionServiceInput if not already present.
                # For now, file_path (which is the URL here) serves as the main identifier.
            )
            # Overwrite acq_result and acquisition_service_output_data with PDF service results
            acq_result = await self.pdf_acquisition_service.execute(pdf_acq_input_redirect)
            determined_service_name = "PDFAcquisitionService (redirected)" # Update for logging

            if acq_result.status == 'error' or not acq_result.data:
                error_message = f"{determined_service_name} failed after redirect: {acq_result.error_message or 'Unknown error'}"
                final_status_code = "failure_acquisition_pdf_redirect"
                acquisition_service_output_data = None # Ensure it's None so subsequent steps don't use stale web data
            elif acq_result.data.status.startswith("error"): # Check status within the PDF service output data model
                error_message = f"{determined_service_name} issue after redirect: {acq_result.data.status} - {acq_result.data.error_message or 'No specific message'}"
                final_status_code = f"failure_acquisition_pdf_redirect_{acq_result.data.status.replace('error_', '')}"
                acquisition_service_output_data = None
            else:
                acquisition_service_output_data = acq_result.data # Successfully processed by PDF service
                # Now, proceed as if it was a PDF from the start
                page_title = getattr(acquisition_service_output_data, 'page_title', page_title) or page_title
                extracted_text = getattr(acquisition_service_output_data, 'extracted_text', None)
                raw_images_for_processing = self._map_to_raw_image_input(
                    acquisition_service_output_data, 
                    job_id, 
                    pdf_identifier, # Use the URL as the source identifier for GCS path
                    determined_final_source_type # MODIFIED: Use the updated type
                )
                final_status_code = "success" # Tentative success after PDF redirect and processing

        # Original success path for non-redirected acquisition services
        elif acquisition_service_output_data: # Ensure it's not None from a failed PDF redirect
            page_title = getattr(acquisition_service_output_data, 'page_title', page_title) or page_title
            final_url = getattr(acquisition_service_output_data, 'final_url', final_url) or final_url # For web
            extracted_text = getattr(acquisition_service_output_data, 'extracted_text', None)
            
            # Determine source_type for GCS path based on the service that successfully ran
            # AND update determined_final_source_type for the OrchestrationOutput
            source_type_for_gcs = initial_source_type_for_routing # Default
            if isinstance(acquisition_service_output_data, PDFAcquisitionServiceOutput):
                source_type_for_gcs = 'pdf'
                determined_final_source_type = 'pdf'
            elif isinstance(acquisition_service_output_data, FileAcquisitionServiceOutput):
                # Assuming FileAcquisitionServiceOutput might have a more specific file_type if available
                source_type_for_gcs = getattr(acquisition_service_output_data, 'file_type', initial_source_type_for_routing)
                determined_final_source_type = source_type_for_gcs # Update with potentially more specific type
            elif isinstance(acquisition_service_output_data, WebAcquisitionServiceOutput):
                source_type_for_gcs = 'url' # Web content is type 'url' for GCS path
                determined_final_source_type = 'url'

            raw_images_for_processing = self._map_to_raw_image_input(
                acquisition_service_output_data, 
                job_id, 
                orchestrator_input.source_identifier, # Original identifier for GCS path consistency
                source_type_for_gcs
            )
            final_status_code = "success" # Tentative success after acquisition
        # This else should ideally not be reached if all prior conditions (error, PDF redirect, success) are handled.
        # It implies acquisition_service_output_data is None without a prior error status being set.
        else: 
            if not error_message: # If no error message was set by previous specific checks
                 error_message = f"Acquisition resulted in no data from {determined_service_name}."
            final_status_code = "failure_acquisition_no_data"

        # Debug print for raw images before further processing (moved from inside the if/else block)
        print(f"Orchestrator.process: Number of raw images for processing (post-acquisition/redirect): {len(raw_images_for_processing)}")
        for i, raw_img in enumerate(raw_images_for_processing):
            print(f"Orchestrator.process: Raw image {i+1} for IPS: ID={raw_img.image_id}, HasBytes={bool(raw_img.image_bytes)}, URL={raw_img.source_url}")

        # If acquisition failed or resulted in a state that stops processing
        if final_status_code.startswith("failure") or final_status_code == "unsupported_type":
            if extracted_text and not final_content_blocks : final_content_blocks.append(ContentBlock(type="text", content=extracted_text))
            # Use determined_final_source_type, defaulting to initial if somehow not set
            output_source_type = determined_final_source_type if determined_final_source_type else initial_source_type_for_routing
            output_obj = self._prepare_final_output(orchestrator_input, final_status_code, page_title, final_content_blocks, processed_images_data_dict, error_message, final_url, output_source_type) # MODIFIED
            if final_status_code.startswith("failure"):
                return ServiceResult.failure(error_message=error_message or "Orchestration failed at acquisition.", error_details=output_obj.model_dump())
            return ServiceResult.success(data=output_obj) # e.g. for unsupported_type or pdf_unhandled

        # 3. Parallel Processing: Image Processing and Content Structuring
        image_processing_service_input = ImageProcessingServiceInput(images_to_process=raw_images_for_processing)
        image_processing_task = self.image_processing_service.execute(image_processing_service_input)
        processed_images_from_service: List[ProcessedImageData] = []

        try:
            image_processing_result: ServiceResult[List[ProcessedImageData]] = await image_processing_task
            
            if image_processing_result.status == 'error' or not image_processing_result.data:
                error_message_img = f"ImageProcessingService failed: {image_processing_result.error_message}"
                print(f"Orchestrator: {error_message_img}") # Log this error
                if not error_message: error_message = error_message_img # Store if no primary error yet
                # Consider if this should change final_status_code to "partial_success" or similar
            
            if image_processing_result.data:
                processed_images_data_dict = {
                    img_data.original_source_identifier: ProcessedImageData(
                        original_source_identifier=img_data.original_source_identifier,
                        gcs_url=img_data.gcs_url,
                        alt_text=img_data.alt_text,
                        caption=img_data.caption,
                        llm_description=img_data.llm_description
                        # Map other fields as necessary
                    ) for img_data in image_processing_result.data
                }
                print(f"Orchestrator.process: Successfully processed {len(processed_images_data_dict)} images according to ImageProcessingService.") # DEBUG PRINT
            else:
                print("Orchestrator.process: No data returned from ImageProcessingService or it failed.") # DEBUG PRINT

            # Debug: Check extracted_text before passing to content structuring
            print(f"ParallelOrchestrator: Text length before structuring: {len(extracted_text) if extracted_text else 0}")
            if extracted_text:
                print(f"ParallelOrchestrator: Text snippet before structuring: {extracted_text[:200]}...")

            content_structuring_service_input = ContentStructuringServiceInput(
                raw_text_content=extracted_text,
                processed_images=processed_images_from_service, 
                job_id=job_id
            )
            content_structuring_result: ServiceResult[List[ContentBlock]] = await self.content_structuring_service.execute(content_structuring_service_input)

            if content_structuring_result.status == 'error' or not content_structuring_result.data:
                error_message_struct = f"ContentStructuringService failed: {content_structuring_result.error_message}"
                print(f"Orchestrator: {error_message_struct}")
                if not error_message: error_message = error_message_struct
                final_status_code = "failure_structuring"
                if not final_content_blocks and extracted_text: # Keep raw text if structuring fails
                    final_content_blocks.append(ContentBlock(type="text", content=extracted_text))
            else:
                final_content_blocks = content_structuring_result.data
                if not final_content_blocks and extracted_text : # If structuring returned empty but text existed
                    final_content_blocks.append(ContentBlock(type="text", content=extracted_text))


        except Exception as e_processing_phase: # Should not happen if services handle their exceptions
            error_message_struct = f"Critical error during processing phase: {str(e_processing_phase)}"
            print(f"Orchestrator: {error_message_struct}")
            if not error_message: error_message = error_message_struct
            final_status_code = "failure_processing_critical"
            if not final_content_blocks and extracted_text: final_content_blocks.append(ContentBlock(type="text", content=extracted_text))


        # Final status refinement
        if final_status_code == "success" and error_message:
            final_status_code = "partial_success"
        elif final_status_code == "success" and not final_content_blocks and not processed_images_data_dict:
             if extracted_text : # If there was text but nothing came out of structuring
                 final_content_blocks.append(ContentBlock(type="text", content=extracted_text))
             else: # No input text and no images/blocks
                 final_status_code = "success_empty_output"


        # 4. Aggregate Output & Finalize
        # Ensure determined_final_source_type has a value. Fallback to initial_source_type_for_routing if it's somehow None.
        output_source_type = determined_final_source_type if determined_final_source_type else initial_source_type_for_routing
        if not output_source_type: # Absolute fallback if initial routing type was also None (should not happen with current logic)
            print("Orchestrator WARNING: output_source_type is None before calling _prepare_final_output. Defaulting to 'unknown'.")
            output_source_type = "unknown"

        final_output_obj = self._prepare_final_output(
            orchestrator_input, final_status_code, page_title, final_content_blocks, 
            processed_images_data_dict, error_message, final_url, output_source_type # MODIFIED: Pass the determined type
        )

        end_time = time.time()
        print(f"Orchestrator processing time: {end_time - start_time:.2f} seconds. Final status: {final_status_code}")

        if final_status_code.startswith("failure"):
            return ServiceResult.failure(error_message=error_message or "Orchestration failed.", error_details=final_output_obj.model_dump())
        
        return ServiceResult.success(data=final_output_obj)
    
    def _prepare_final_output(self, 
                              inp: OrchestrationInput, 
                              status: str, 
                              title: Optional[str],
                              blocks: List[ContentBlock],
                              images_data: Dict[str, ProcessedImageData],
                              err_msg: Optional[str],
                              final_url_val: Optional[str],
                              actual_source_type: Optional[str]) -> OrchestrationOutput: # MODIFIED: Add actual_source_type
        """
        Helper method to construct the OrchestrationOutput object.
        """
        # Ensure actual_source_type has a fallback if it's None, though it should be set by `process`
        # The OrchestrationOutput model requires a string for source_type.
        final_source_type_for_output = actual_source_type or inp.source_type or "unknown"
        if not actual_source_type and inp.source_type is None:
             print(f"Orchestrator._prepare_final_output WARNING: actual_source_type and inp.source_type are None. Using '{final_source_type_for_output}'. Input source: {inp.source_identifier}")


        return OrchestrationOutput(
            status_code=status,
            source_identifier=final_url_val or inp.source_identifier, 
            source_type=final_source_type_for_output, # MODIFIED: Use the passed or determined type
            processing_level_used=inp.processing_level,
            extracted_title=title,
            is_long_article=False, # Placeholder, determine actual value if needed
            original_content_blocks=blocks,
            processed_images_data=images_data,
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

# Need to add import for uuid at the top of the file
# import uuid # Removed redundant import

# Added here, should be at the top
import uuid # Added here, should be at the top 