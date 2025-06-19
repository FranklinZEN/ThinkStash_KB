import asyncio
import time
import uuid
from typing import Optional, Any, Dict, List, Union, Tuple
import logging
import httpx

from aiservice.app.config.settings import Settings
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock, OrchestrationStatusCodeEnum
from aiservice.app.models.pipeline_models import EnrichedImageMetadata, DocumentMetadata, PreliminaryBlock, RawImageInput
from aiservice.app.models.task_models import TaskResult, TaskStatus
from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.services.routing_service import RoutingService, RoutingInput
from aiservice.app.services.acquisition.correct_web_service import CorrectWebAcquisitionService, WebAcquisitionServiceInput
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput
from aiservice.app.services.acquisition.file_service import FileAcquisitionService, FileAcquisitionServiceInput
from aiservice.app.services.processing.image_processing_service import ImageProcessingService, ImageProcessingServiceInput
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService, ContentStructuringServiceInput
from aiservice.app.utils.url_utils import custom_normalize_url
from aiservice.app.services.task_db_service import TaskDBService
from ..crews.title_generation_crew import GeneralPurposeTitleGenerationCrew

logger = logging.getLogger(__name__)

class ParallelOrchestrator(BaseService):
    """
    Manages the end-to-end processing flow, invoking other services in sequence or parallel.
    Integrates logic for routing, acquisition, processing, and structuring.
    """

    def __init__(self,
                 task_db_service: TaskDBService,
                 routing_service: RoutingService,
                 image_processing_service: ImageProcessingService,
                 content_structuring_service: ContentStructuringService,
                 settings: Settings):
        super().__init__(settings)
        self.task_db_service = task_db_service
        self.routing_service = routing_service
        self.image_processing_service = image_processing_service
        self.content_structuring_service = content_structuring_service
        self.settings: Settings = settings
        self.logger = logging.getLogger(__name__)

    async def process(self, orchestrator_input: OrchestrationInput) -> ServiceResult[OrchestrationOutput]:
        """
        Main processing method for the orchestrator.
        Wraps the entire pipeline in a single database transaction for the main reconstruction task.
        """
        job_id = orchestrator_input.job_id or str(uuid.uuid4())
        self.logger.info(f"Orchestrator: Starting job {job_id} for source: {orchestrator_input.source_identifier} (Type hint: {orchestrator_input.source_type})")
        
        conn = None
        try:
            conn = self.task_db_service.get_connection()
            self.logger.info(f"Job {job_id}: Database connection acquired.")
            
            self.task_db_service.update_task_status_processing(job_id, conn)
            
            output = await self._run_pipeline(orchestrator_input, job_id, conn)

            conn.commit()
            self.logger.info(f"Job {job_id}: Pipeline successful. DB transaction committed.")
            return ServiceResult.success(data=output)

        except Exception as e:
            self.logger.error(f"Job {job_id}: Pipeline failed. Rolling back. Error: {e}", exc_info=True)
            if conn:
                try:
                    conn.rollback()
                    # Use a new connection to ensure failure status is written
                    error_conn = self.task_db_service.get_connection()
                    try:
                        self.task_db_service.update_task_status_failed(job_id, str(e), error_conn)
                        error_conn.commit()
                    finally:
                        self.task_db_service.release_connection(error_conn)
                except Exception as e_rollback:
                     self.logger.critical(f"Job {job_id}: FAILED TO ROLLBACK AND UPDATE STATUS. Error: {e_rollback}", exc_info=True)

            failure_output = self._prepare_final_output(
                orchestrator_input, orchestrator_input.source_identifier,
                OrchestrationStatusCodeEnum.ERROR_UNEXPECTED_OUTPUT_TYPE,
                None, [], {}, str(e), orchestrator_input.source_identifier,
                orchestrator_input.source_type, None, False
            )
            return ServiceResult.failure(error_message=str(e), error_details=failure_output.model_dump())
        finally:
            if conn:
                self.task_db_service.release_connection(conn)
                self.logger.info(f"Job {job_id}: DB connection released.")

    async def _run_pipeline(self, orchestrator_input: OrchestrationInput, job_id: str, conn) -> OrchestrationOutput:
        """
        The core pipeline logic, running within a managed transaction.
        """
        start_time = time.time()
        
        # Initialize variables
        page_title: Optional[str] = orchestrator_input.source_identifier 
        final_url: Optional[str] = orchestrator_input.source_identifier
        
        self.task_db_service.update_task_progress_stage(job_id, "Normalizing URL", conn)
        processed_source_identifier = custom_normalize_url(orchestrator_input.source_identifier)
        
        routing_input_obj = RoutingInput(source_identifier=processed_source_identifier, source_type=orchestrator_input.source_type)
        routing_result = await self.routing_service.execute(routing_input_obj)

        if not routing_result.is_success() or not routing_result.data:
            raise Exception(f"Routing failed: {routing_result.error_message}")

        determined_service_name = routing_result.data.determined_service
        actual_determined_source_type = routing_result.data.determined_source_type

        # HEAD request check for PDFs disguised as web pages
        if determined_service_name == "CorrectWebAcquisitionService" and RoutingService.is_url(processed_source_identifier):
            try:
                async with httpx.AsyncClient(timeout=self.settings.default_request_timeout_seconds) as client:
                    head_response = await client.head(processed_source_identifier, follow_redirects=True)
                    if 'application/pdf' in head_response.headers.get('content-type', '').lower():
                        determined_service_name = "PDFAcquisitionService"
                        actual_determined_source_type = "pdf"
            except Exception as e_head:
                self.logger.warning(f"Job {job_id}: HEAD request failed: {e_head}. Proceeding.")

        self.task_db_service.update_task_progress_stage(job_id, f"Acquiring content via {determined_service_name}", conn)

        # Content Acquisition
        acq_result: Optional[ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]] = None
        service_map = {
            "CorrectWebAcquisitionService": (CorrectWebAcquisitionService, WebAcquisitionServiceInput, {"url": processed_source_identifier}),
            "PDFAcquisitionService": (PDFAcquisitionService, PDFAcquisitionServiceInput, {"file_path": processed_source_identifier}),
            "FileAcquisitionService": (FileAcquisitionService, FileAcquisitionServiceInput, {"file_path": processed_source_identifier, "source_content_type": actual_determined_source_type})
        }

        if determined_service_name in service_map:
            service_class, input_class, kwargs = service_map[determined_service_name]
            service = service_class(settings=self.settings)
            acq_input = input_class(job_id=job_id, user_id=orchestrator_input.user_id, **kwargs)
            acq_result = await service.execute(acq_input)
        else:
            raise Exception(f"Unknown or unsupported service: {determined_service_name}")

        if not acq_result or not acq_result.is_success() or not acq_result.data:
            raise Exception(f"{determined_service_name} failed: {acq_result.error_message if acq_result else 'No result'}")
        
        preliminary_blocks, document_metadata_obj, raw_images = acq_result.data
        page_title = document_metadata_obj.title or page_title
        final_url = document_metadata_obj.final_url or final_url
        
        # Image Processing
        self.task_db_service.update_task_progress_stage(job_id, f"Processing {len(raw_images)} images", conn)
        processed_images_dict = {}
        if raw_images:
            img_proc_input = ImageProcessingServiceInput(images_to_process=raw_images)
            img_proc_result = await self.image_processing_service.execute(img_proc_input)
            if img_proc_result.is_success() and img_proc_result.data:
                processed_images_dict = {img.image_id: img for img in img_proc_result.data}

        # Content Structuring
        self.task_db_service.update_task_progress_stage(job_id, f"Structuring {len(preliminary_blocks)} blocks", conn)
        structuring_input = ContentStructuringServiceInput(
            preliminary_blocks=preliminary_blocks,
            enriched_images=list(processed_images_dict.values()),
            document_metadata=document_metadata_obj
        )
        structuring_result = await self.content_structuring_service.execute(structuring_input)

        if not structuring_result.is_success() or structuring_result.data is None:
            raise Exception(f"Content structuring failed: {structuring_result.error_message}")
        
        final_content_blocks = structuring_result.data
        
        # Manually determine if the article is long-form content now
        long_article_threshold = self.settings.long_article_char_threshold if self.settings else 3000
        total_char_count = sum(len(block.content) for block in final_content_blocks if block.type == "paragraph" and block.content and isinstance(block.content, str))
        is_long_article = total_char_count > long_article_threshold
        
        # Finalization
        self.task_db_service.update_task_progress_stage(job_id, "Finalizing output", conn)
        output = self._prepare_final_output(
            orchestrator_input, processed_source_identifier, OrchestrationStatusCodeEnum.SUCCESS,
            page_title, final_content_blocks, processed_images_dict, None,
            final_url, actual_determined_source_type, document_metadata_obj, is_long_article
        )
        
        self.task_db_service.update_task_status_completed(job_id, output.model_dump(), conn)
        self.logger.info(f"Job {job_id}: Pipeline finished successfully in {time.time() - start_time:.2f}s.")
        return output

    async def _run_title_generation_pipeline(self, job_id: str, content_blocks_data: List[dict]) -> TaskResult:
        """
        Runs the title generation crew with the provided content blocks.
        """
        self.logger.info(f"Job {job_id}: Running title generation pipeline.")
        try:
            if not content_blocks_data:
                self.logger.warning(f"Job {job_id}: No content blocks provided for title generation.")
                return TaskResult(
                    status=TaskStatus.FAILED,
                    message="No content provided for title generation."
                )

            # Extract full text from content blocks before initializing the crew
            full_text = " ".join(
                block.get('content', '') or '' 
                for block in content_blocks_data 
                if isinstance(block.get('content'), str)
            )

            if not full_text.strip():
                self.logger.warning(f"Job {job_id}: Content blocks contain no text for title generation.")
                return TaskResult(
                    status=TaskStatus.FAILED,
                    message="Content blocks contain no text for title generation."
                )

            title_crew = GeneralPurposeTitleGenerationCrew(full_text_content=full_text)
            
            # The crew's run method does not need arguments anymore
            title_output = title_crew.run()

            if title_output and getattr(title_output, 'suggested_title', None) and not title_output.suggested_title.startswith("Error:"):
                self.logger.info(f"Job {job_id}: Title generation successful.")
                return TaskResult(
                    status=TaskStatus.COMPLETED,
                    result={"title": title_output.suggested_title},
                    message="Title generated successfully."
                )
            else:
                error_message = f"Title Generation Failed: {getattr(title_output, 'suggested_title', 'No output from crew.')}"
                self.logger.error(f"Job {job_id}: {error_message}")
                return TaskResult(status=TaskStatus.FAILED, message=error_message)

        except Exception as e:
            self.logger.error(f"Job {job_id}: Title generation pipeline failed with an exception: {e}", exc_info=True)
            return TaskResult(status=TaskStatus.FAILED, message=f"An unexpected error occurred: {str(e)}")

    def _prepare_final_output(self, original_input: OrchestrationInput, used_source_identifier: str, 
                              status_code: Union[OrchestrationStatusCodeEnum, str], extracted_title: Optional[str], 
                              content_blocks: List[ContentBlock], processed_images_data: Dict[str, EnrichedImageMetadata],
                              error_message: Optional[str], final_url: Optional[str], final_source_type: Optional[str], 
                              document_metadata: Optional[DocumentMetadata], is_long_article: bool = False) -> OrchestrationOutput:
        
        status_code_str = status_code.value if isinstance(status_code, OrchestrationStatusCodeEnum) else status_code
        final_title = extracted_title or (document_metadata.title if document_metadata else "Untitled")
        
        return OrchestrationOutput(
            status_code=status_code_str,
            user_id=original_input.user_id,
            request_id=original_input.job_id,
            source_identifier=used_source_identifier,
            final_url=final_url,
            source_type=final_source_type,
            title=final_title,
            content_blocks=content_blocks,
            images_metadata=list(processed_images_data.values()),
            document_metadata=document_metadata,
            error_message=error_message,
            is_long_form_content=is_long_article,
            processing_level=original_input.processing_level,
            additional_context=original_input.additional_context,
        )

    async def execute(self, *args: Any, **kwargs: Any) -> ServiceResult[Any]:
        # This method is for compatibility with the BaseService but should not be the primary entry point.
        if args and isinstance(args[0], OrchestrationInput):
            return await self.process(args[0])
        if 'orchestrator_input' in kwargs and isinstance(kwargs['orchestrator_input'], OrchestrationInput):
            return await self.process(kwargs['orchestrator_input'])
        logger.warning("Orchestrator's generic 'execute' called without a valid OrchestrationInput.")
        return ServiceResult.failure("Invalid call to orchestrator. Use 'process' method.")