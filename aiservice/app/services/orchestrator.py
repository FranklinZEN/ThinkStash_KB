import asyncio
import time
import uuid
from typing import Optional, Any, Dict, List, Union, Tuple, Type
import sys
import logging
import httpx

from aiservice.app.config.settings import Settings # Import the specific Settings class
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock, OrchestrationStatusCodeEnum # Import OrchestrationStatusCodeEnum
# Remove the old WebAcquisitionInput import from models
# from aiservice.app.models.web_acquisition_models import WebAcquisitionInput 
from aiservice.app.models.pipeline_models import EnrichedImageMetadata, DocumentMetadata, PreliminaryBlock, RawImageInput
from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.services.routing_service import RoutingService, RoutingInput, RoutingService # Added RoutingService for static method access
# Import the correct WebAcquisitionServiceInput from the service file
from aiservice.app.services.acquisition.web_service import WebAcquisitionService, WebAcquisitionServiceInput
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput
from aiservice.app.services.acquisition.file_service import FileAcquisitionService, FileAcquisitionServiceInput
from aiservice.app.services.processing.image_processing_service import ImageProcessingService, ImageProcessingServiceInput
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService, ContentStructuringServiceInput
from aiservice.app.utils.url_utils import custom_normalize_url # Import the new utility

# Placeholder for actual settings, data_store, and monitor when implemented
# from aiservice.app.config.settings import Settings # When available
# from aiservice.app.core.data_store import get_data_store # When available
# from aiservice.app.core.monitoring import PerformanceMonitor # When available

# Configure logging
logger = logging.getLogger(__name__)

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
        self.settings: Settings = settings
        self.logger = logging.getLogger(__name__)
        # self.data_store = get_data_store(settings) # Pass settings if data_store needs it
        # self.monitor = PerformanceMonitor(settings) # Pass settings if monitor needs it

    # @monitor.track_operation() # Add when monitor is implemented
    async def process(self, orchestrator_input: OrchestrationInput) -> ServiceResult[OrchestrationOutput]:
        """
        Main processing method for the orchestrator.
        """
        job_id = orchestrator_input.job_id or str(uuid.uuid4())
        self.logger.info(f"Orchestrator: Starting job {job_id} for source: {orchestrator_input.source_identifier} (Type hint: {orchestrator_input.source_type})")
        start_time = time.time()

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

        # --- URL Normalization --- #
        # Attempt to normalize the source_identifier first, especially for complex URLs like chrome-extension.
        processed_source_identifier = orchestrator_input.source_identifier
        initial_source_type_for_routing = orchestrator_input.source_type # Preserve original hint

        try:
            normalized_attempt = custom_normalize_url(orchestrator_input.source_identifier)
            if normalized_attempt != orchestrator_input.source_identifier:
                self.logger.info(f"Job {job_id}: URL normalized from '{orchestrator_input.source_identifier}' to '{normalized_attempt}' by custom_normalize_url.")
                processed_source_identifier = normalized_attempt
                # If normalization changed it and the result is a standard URL, ensure routing treats it as such.
                if RoutingService.is_url(processed_source_identifier) and initial_source_type_for_routing != 'url':
                    self.logger.info(f"Job {job_id}: Post-normalization, identifier '{processed_source_identifier}' is a standard URL. Setting type hint for routing to 'url'.")
                    initial_source_type_for_routing = 'url'
            elif orchestrator_input.source_type == 'url' and not RoutingService.is_url(processed_source_identifier):
                 # This case covers if source_type was 'url' but custom_normalize_url didn't change it AND it's still not a standard http/s/ftp.
                 # This might happen if custom_normalize_url passed through an unhandled 'url' scheme.
                 self.logger.warning(f"Job {job_id}: Source type hint was 'url' for '{processed_source_identifier}', but it's not recognized as a standard http/s/ftp URL by RoutingService.is_url. Proceeding with original type hint.")
        except Exception as e_norm:
            self.logger.error(f"Job {job_id}: Error during URL normalization for '{orchestrator_input.source_identifier}': {e_norm}. Proceeding with original identifier and type hint.")
            # processed_source_identifier remains orchestrator_input.source_identifier
            # initial_source_type_for_routing remains orchestrator_input.source_type

        # 1. Routing
        self.logger.info(f"Job {job_id}: Routing for identifier: {processed_source_identifier}, type hint: {initial_source_type_for_routing}")
        
        # Determine initial source type for routing more explicitly if not already set by normalization or input
        if not initial_source_type_for_routing: 
            # Pass the *processed_source_identifier* to get_source_type
            determined_type_from_get_source_type = RoutingService.get_source_type(processed_source_identifier)
            self.logger.info(f"Job {job_id}: RoutingService.get_source_type determined initial type as: {determined_type_from_get_source_type} for identifier '{processed_source_identifier}'")
            initial_source_type_for_routing = determined_type_from_get_source_type
        elif initial_source_type_for_routing == 'url' and not RoutingService.is_url(processed_source_identifier):
            # If after normalization, it was hinted as 'url' but is_url still says no (e.g. "file:///" was normalized to itself)
            # then we should trust get_source_type for a more accurate classification than just 'url'.
            self.logger.info(f"Job {job_id}: Identifier '{processed_source_identifier}' was hinted as 'url' but is_url is false. Re-evaluating type with get_source_type.")
            initial_source_type_for_routing = RoutingService.get_source_type(processed_source_identifier)
            self.logger.info(f"Job {job_id}: Re-evaluated type for routing: {initial_source_type_for_routing}")


        routing_input_obj = RoutingInput(
            source_identifier=processed_source_identifier, # Use the potentially normalized identifier
            source_type=initial_source_type_for_routing 
        )
        routing_result = await self.routing_service.execute(routing_input_obj)

        if not routing_result.is_success() or not routing_result.data:
            error_message = f"Routing failed: {routing_result.error_message}"
            self.logger.error(f"Job {job_id}: {error_message}")
            final_status_code = OrchestrationStatusCodeEnum.FAILURE_ROUTING # Use Enum
            output_obj = self._prepare_final_output(
                orchestrator_input, # Pass original input for context
                processed_source_identifier, # Pass the identifier actually used
                final_status_code, 
                page_title, 
                final_content_blocks, 
                processed_images_data_dict, 
                error_message, 
                final_url or processed_source_identifier, # Use processed if final_url not set
                determined_final_source_type or initial_source_type_for_routing, # Best guess for source type
                document_metadata_obj, 
                False
            )
            return ServiceResult.failure(error_message=error_message, error_details=output_obj.model_dump())

        determined_service_name = routing_result.data.determined_service
        actual_determined_source_type_from_router = routing_result.data.determined_source_type

        # If router suggests WebAcquisitionService for a URL, perform a HEAD request to check for PDF content-type
        if determined_service_name == "WebAcquisitionService" and \
           RoutingService.is_url(processed_source_identifier): # Ensure it's a URL
            try:
                async with httpx.AsyncClient(timeout=self.settings.default_request_timeout_seconds) as client:
                    head_response = await client.head(processed_source_identifier, follow_redirects=True)
                    content_type = head_response.headers.get('content-type', '').lower()
                    if 'application/pdf' in content_type:
                        self.logger.info(f"Job {job_id}: HEAD request for {processed_source_identifier} indicates PDF content-type ('{content_type}'). Overriding service to PDFAcquisitionService.")
                        determined_service_name = "PDFAcquisitionService"
                        actual_determined_source_type_from_router = "pdf" # Update the determined type as well
                    else:
                        self.logger.info(f"Job {job_id}: HEAD request for {processed_source_identifier} content-type ('{content_type}') is not PDF. Proceeding with {determined_service_name}.")
            except httpx.RequestError as e_http:
                self.logger.warning(f"Job {job_id}: HTTP error during HEAD request for {processed_source_identifier}: {e_http}. Proceeding with router's decision ({determined_service_name}).")
            except Exception as e_head:
                self.logger.warning(f"Job {job_id}: Unexpected error during HEAD request or content-type check for {processed_source_identifier}: {e_head}. Proceeding with router's decision ({determined_service_name}).")

        self.logger.info(f"Job {job_id}: Final determined service: {determined_service_name}, type: {actual_determined_source_type_from_router}")
        determined_final_source_type = actual_determined_source_type_from_router # Update with router's or HEAD request's more specific type

        # 2. Acquisition
        # All acquisition services now return ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]
        acq_result: Optional[ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]] = None

        if determined_service_name == "WebAcquisitionService":
            web_acq_input = WebAcquisitionServiceInput(
                url=processed_source_identifier, # Use potentially normalized URL
                processing_level=orchestrator_input.processing_level,
                job_id=job_id,
                user_id=orchestrator_input.user_id
            )
            acq_result = await self.web_acquisition_service.execute(web_acq_input)
        elif determined_service_name == "PDFAcquisitionService":
            pdf_acq_input = PDFAcquisitionServiceInput(
                file_path=processed_source_identifier, # Use potentially normalized identifier
                processing_level=orchestrator_input.processing_level,
                job_id=job_id,
                user_id=orchestrator_input.user_id
            )
            acq_result = await self.pdf_acquisition_service.execute(pdf_acq_input)
        elif determined_service_name == "FileAcquisitionService":
            file_acq_input = FileAcquisitionServiceInput(
                file_path=processed_source_identifier, # Use potentially normalized identifier
                source_content_type=actual_determined_source_type_from_router, 
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
                    
            output_obj = self._prepare_final_output(
                orchestrator_input, # Pass original input for context
                processed_source_identifier, # Pass the identifier actually used
                final_status_code, 
                page_title, 
                final_content_blocks, 
                processed_images_data_dict, 
                error_message, 
                final_url or processed_source_identifier, # Use processed if final_url not set
                determined_final_source_type or initial_source_type_for_routing, # Best guess for source type
                document_metadata_obj, 
                False
            )
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

            if img_processing_result.is_success() and img_processing_result.data:
                self.logger.info(f"Job {job_id}: ImageProcessingService succeeded, got {len(img_processing_result.data)} enriched images.")
                enriched_images_list = img_processing_result.data
            else:
                warning_message = f"ImageProcessingService did not return any enriched images or failed: {img_processing_result.error_message}"
                self.logger.warning(f"Job {job_id}: {warning_message}")
                accumulated_warnings.append(warning_message)
        else:
            self.logger.info(f"Job {job_id}: No raw images from acquisition to process.")

        # 4. Content Structuring
        self.logger.info(f"Job {job_id}: Starting ContentStructuringService with {len(preliminary_blocks)} prelim blocks and {len(enriched_images_list)} enriched images.")
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

        # Calculate is_long_article
        total_char_count = 0
        for block in final_content_blocks:
            if block.type == "text" and block.content:
                total_char_count += len(block.content)
        
        # User-defined threshold for long article
        long_article_threshold = 20000  # As per user specification
        is_long_article_calculated = total_char_count > long_article_threshold
        print(f"Orchestrator: Job {job_id} total character count: {total_char_count}, is_long_article: {is_long_article_calculated}")


        output_obj = self._prepare_final_output(
            orchestrator_input, # Pass original input for context
            processed_source_identifier, # Pass the identifier actually used
            final_status_code, 
            page_title, 
            final_content_blocks, 
            processed_images_data_dict, 
            error_message, 
            final_url or processed_source_identifier, # Use processed if final_url not set
            determined_final_source_type or initial_source_type_for_routing, # Best guess for source type
            document_metadata_obj, # Pass the complete DocumentMetadata object
            is_long_article_calculated # Pass the calculated value
        )
        
        if final_status_code == "success" or final_status_code.startswith("partial_success"):
            return ServiceResult.success(data=output_obj)
        else:
            # For critical failures, error_message should already be set.
            # The output_obj contains all data gathered up to the point of failure.
            return ServiceResult.failure(error_message=error_message or "Orchestration failed with no specific message.", error_details=output_obj.model_dump())
    
    def _prepare_final_output(
        self,
        original_input: OrchestrationInput, 
        used_source_identifier: str,      
        status_code: Union[OrchestrationStatusCodeEnum, str],
        extracted_title: Optional[str],
        content_blocks: List[ContentBlock],
        processed_images_data: Dict[str, EnrichedImageMetadata],
        error_message: Optional[str],
        final_url: Optional[str],         
        final_source_type: Optional[str], 
        document_metadata: Optional[DocumentMetadata],
        is_long_article: bool = False
    ) -> OrchestrationOutput:
        
        final_status = status_code.value if isinstance(status_code, OrchestrationStatusCodeEnum) else status_code
        
        # Determine the best source_identifier and source_type for the output
        
        # Initialize with values known to the orchestrator or from the original input
        output_source_identifier = final_url or used_source_identifier 
        output_source_type = final_source_type or original_input.source_type or "unknown"

        current_user_id = original_input.user_id
        current_document_id = original_input.job_id # job_id is used as the document_id for the run

        if document_metadata:
            # If DocumentMetadata is available, its fields are usually more authoritative
            # for the content that was actually processed.
            if document_metadata.final_url:
                output_source_identifier = document_metadata.final_url
            elif document_metadata.source_identifier: # Fallback to the source_identifier from metadata
                output_source_identifier = document_metadata.source_identifier
            
            if document_metadata.source_type and document_metadata.source_type != "unknown":
                output_source_type = document_metadata.source_type

            # Prefer user_id and document_id from metadata if set and valid
            current_user_id = document_metadata.user_id or original_input.user_id 
            current_document_id = document_metadata.document_id or original_input.job_id

        return OrchestrationOutput(
            status_code=final_status,
            user_id=current_user_id, 
            document_id=current_document_id,
            source_identifier=output_source_identifier,
            source_type=output_source_type,
            processing_level_used=original_input.processing_level,
            extracted_title=extracted_title,
            is_long_article=is_long_article,
            original_content_blocks=content_blocks,
            processed_images_data=processed_images_data,
            document_metadata=document_metadata,
            error_message=error_message
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