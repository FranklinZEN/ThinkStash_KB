import asyncio
import time
import uuid
from typing import Optional, Any, Dict, List, Union, Tuple, Type
import sys
import logging
import httpx
import traceback
import json

from aiservice.app.config.settings import Settings
from aiservice.app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ContentBlock, OrchestrationStatusCodeEnum
from aiservice.app.models.pipeline_models import EnrichedImageMetadata, DocumentMetadata, PreliminaryBlock, RawImageInput
from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.services.routing_service import RoutingService, RoutingInput
from aiservice.app.services.acquisition.web_service import WebAcquisitionService, WebAcquisitionServiceInput
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput
from aiservice.app.services.acquisition.file_service import FileAcquisitionService, FileAcquisitionServiceInput
from aiservice.app.services.processing.image_processing_service import ImageProcessingService, ImageProcessingServiceInput
from aiservice.app.services.structuring.content_structuring_service import ContentStructuringService, ContentStructuringServiceInput
from aiservice.app.crews.title_generation_crew import GeneralPurposeTitleGenerationCrew
from aiservice.app.utils.url_utils import custom_normalize_url
from aiservice.app.services.task_db_service import TaskDBService

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
        Wraps the entire pipeline in a single database transaction.
        """
        job_id = orchestrator_input.job_id or str(uuid.uuid4())
        self.logger.info(f"Orchestrator: Starting job {job_id} for source: {orchestrator_input.source_identifier} (Type hint: {orchestrator_input.source_type})")
        
        conn = None
        try:
            conn = self.task_db_service.get_connection()
            self.logger.info(f"Job {job_id}: Database connection acquired from pool.")
            
            # This is the core routing logic based on task type.
            task_type = orchestrator_input.task_type
            self.logger.info(f"Job {job_id}: Routing task of type '{task_type}'.")

            if task_type == "RECONSTRUCT_AND_ANALYZE":
                self.task_db_service.update_task_status_processing(job_id, conn)
                output = await self._run_reconstruction_pipeline(orchestrator_input, job_id, conn)
            elif task_type == "GENERATE_TITLE":
                self.task_db_service.update_task_status_processing(job_id, conn)
                output = await self._run_title_generation_pipeline(orchestrator_input, job_id, conn)
            else:
                raise NotImplementedError(f"Unknown or unsupported task type: {task_type}")

            conn.commit()
            self.logger.info(f"Job {job_id}: Pipeline for task type '{task_type}' successful. Database transaction committed.")
            return ServiceResult.success(data=output)

        except Exception as e:
            self.logger.error(f"Job {job_id}: An exception caused the pipeline to fail. Rolling back transaction. Error: {e}", exc_info=True)
            if conn:
                try:
                    conn.rollback()
                    self.logger.info(f"Job {job_id}: Original database transaction rolled back.")
                    
                    error_conn = None
                    try:
                        error_conn = self.task_db_service.get_connection()
                        self.task_db_service.update_task_status_failed(job_id, str(e), error_conn)
                        error_conn.commit()
                        self.logger.info(f"Job {job_id}: Successfully updated task status to FAILED in a separate transaction.")
                    except Exception as e_fail_update:
                        self.logger.critical(f"Job {job_id}: CRITICAL - FAILED TO UPDATE TASK STATUS TO FAILED. Error: {e_fail_update}", exc_info=True)
                        if error_conn: error_conn.rollback()
                    finally:
                        if error_conn: self.task_db_service.release_connection(error_conn)

                except Exception as e_rollback:
                     self.logger.critical(f"Job {job_id}: CRITICAL - FAILED TO ROLLBACK TRANSACTION. Error: {e_rollback}", exc_info=True)

            failure_output = self._prepare_final_output(
                orchestrator_input, orchestrator_input.source_identifier,
                OrchestrationStatusCodeEnum.FAILURE_UNHANDLED_EXCEPTION,
                None, [], {}, str(e), orchestrator_input.source_identifier,
                orchestrator_input.source_type, None, False, None
            )
            return ServiceResult.failure(error_message=str(e), error_details=failure_output.model_dump())

        finally:
            if conn:
                self.task_db_service.release_connection(conn)
                self.logger.info(f"Job {job_id}: Database connection released back to pool.")

    async def _run_reconstruction_pipeline(self, orchestrator_input: OrchestrationInput, job_id: str, conn) -> OrchestrationOutput:
        """
        The core pipeline logic for reconstructing content from a source (e.g., URL).
        The `conn` object is passed to any function that needs to interact with the DB.
        """
        start_time = time.time()

        preliminary_blocks: List[PreliminaryBlock] = []
        document_metadata_obj: Optional[DocumentMetadata] = None
        raw_images_from_acquisition: List[RawImageInput] = []
        enriched_images_list: List[EnrichedImageMetadata] = []
        processed_images_data_dict: Dict[str, EnrichedImageMetadata] = {}
        final_content_blocks: List[ContentBlock] = []
        error_message: Optional[str] = None
        accumulated_warnings: List[str] = []
        page_title: Optional[str] = orchestrator_input.source_identifier 
        final_url: Optional[str] = orchestrator_input.source_identifier
        determined_final_source_type: Optional[str] = orchestrator_input.source_type
        
        self.task_db_service.update_task_progress_stage(job_id, "Normalizing URL", conn)

        processed_source_identifier = custom_normalize_url(orchestrator_input.source_identifier)
        
        routing_input_obj = RoutingInput(source_identifier=processed_source_identifier, source_type=orchestrator_input.source_type)
        routing_result = await self.routing_service.execute(routing_input_obj)

        if not routing_result.is_success() or not routing_result.data:
            raise Exception(f"Routing failed: {routing_result.error_message}")

        determined_service_name = routing_result.data.determined_service
        actual_determined_source_type_from_router = routing_result.data.determined_source_type

        if determined_service_name == "WebAcquisitionService" and RoutingService.is_url(processed_source_identifier):
            try:
                async with httpx.AsyncClient(timeout=self.settings.default_request_timeout_seconds) as client:
                    head_response = await client.head(processed_source_identifier, follow_redirects=True)
                    content_type = head_response.headers.get('content-type', '').lower()
                    if 'application/pdf' in content_type:
                        determined_service_name = "PDFAcquisitionService"
                        actual_determined_source_type_from_router = "pdf"
            except Exception as e_head:
                self.logger.warning(f"Job {job_id}: HEAD request failed: {e_head}. Proceeding with router's decision.")

        determined_final_source_type = actual_determined_source_type_from_router
        self.task_db_service.update_task_progress_stage(job_id, f"Acquiring content via {determined_service_name}", conn)

        acq_result: Optional[ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]] = None
        if determined_service_name == "WebAcquisitionService":
            service = WebAcquisitionService(settings=self.settings)
            acq_input = WebAcquisitionServiceInput(url=processed_source_identifier, job_id=job_id, user_id=orchestrator_input.user_id)
            acq_result = await service.execute(acq_input)
        elif determined_service_name == "PDFAcquisitionService":
            service = PDFAcquisitionService(settings=self.settings)
            acq_input = PDFAcquisitionServiceInput(file_path=processed_source_identifier, job_id=job_id, user_id=orchestrator_input.user_id)
            acq_result = await service.execute(acq_input)
        elif determined_service_name == "FileAcquisitionService":
            service = FileAcquisitionService(settings=self.settings)
            acq_input = FileAcquisitionServiceInput(file_path=processed_source_identifier, source_content_type=actual_determined_source_type_from_router, job_id=job_id, user_id=orchestrator_input.user_id)
            acq_result = await service.execute(acq_input)
        else:
            raise Exception(f"Unknown or unsupported service: {determined_service_name}")

        if not acq_result or not acq_result.is_success() or not acq_result.data:
            raise Exception(f"{determined_service_name} failed: {acq_result.error_message if acq_result else 'No result'}")
        
        preliminary_blocks, document_metadata_obj, raw_images_from_acquisition = acq_result.data
        page_title = document_metadata_obj.title or page_title
        final_url = document_metadata_obj.final_url or final_url
        determined_final_source_type = document_metadata_obj.source_type

        progress_stage_msg = f"Processing {len(raw_images_from_acquisition)} images" if raw_images_from_acquisition else "No images to process"
        self.task_db_service.update_task_progress_stage(job_id, progress_stage_msg, conn)
        
        if raw_images_from_acquisition:
            img_processing_input = ImageProcessingServiceInput(images_to_process=raw_images_from_acquisition)
            img_processing_result = await self.image_processing_service.execute(img_processing_input)
            if img_processing_result.is_success() and img_processing_result.data:
                enriched_images_list = img_processing_result.data
                processed_images_data_dict = {img.image_id: img for img in enriched_images_list}
            else:
                warning_msg = f"Image Processing Failed: {img_processing_result.error_message}"
                self.logger.warning(f"Job {job_id}: {warning_msg}")
                accumulated_warnings.append(warning_msg)

        self.task_db_service.update_task_progress_stage(job_id, f"Structuring {len(preliminary_blocks)} preliminary blocks", conn)
        
        structuring_input = ContentStructuringServiceInput(
            preliminary_blocks=preliminary_blocks,
            enriched_images=processed_images_data_dict.get('enriched_images', []),
            raw_images=raw_images_from_acquisition,
            document_metadata=document_metadata_obj,
            job_id=job_id,
            user_id=orchestrator_input.user_id
        )
        structuring_result = await self.content_structuring_service.execute(structuring_input)

        if not structuring_result.is_success() or structuring_result.data is None:
            raise Exception(f"Content structuring failed: {structuring_result.error_message}")

        final_content_blocks = structuring_result.data
        
        self.task_db_service.update_task_progress_stage(job_id, "Finalizing and preparing output", conn)
        
        is_long = self._is_long_article(final_content_blocks)
        if accumulated_warnings:
            error_message = "; ".join(accumulated_warnings)

        # Step 4: Create the Knowledge Card in the database
        # A default title is used here. Title generation is now a separate, on-demand task.
        final_title = page_title or "Untitled Document"
        card_id = self.task_db_service.create_knowledge_card_from_blocks(
            orchestrator_input.user_id, 
            final_title, 
            [block.model_dump() for block in final_content_blocks],
            conn
        )

        # Step 5: Finalize and return the result with the new card_id
        log_extra = {'task_id': job_id}
        logger.info(f"Finalizing and preparing output, card created: {card_id}", extra=log_extra)

        output = self._prepare_final_output(
            orchestrator_input, processed_source_identifier, OrchestrationStatusCodeEnum.SUCCESS,
            page_title, final_content_blocks, processed_images_data_dict, error_message,
            final_url, determined_final_source_type, document_metadata_obj, is_long, card_id
        )
        
        reconstruction_result_payload = {"card_id": card_id}
        self.task_db_service.update_task_status_completed(job_id, reconstruction_result_payload, conn)
        
        duration = time.time() - start_time
        self.logger.info(f"Job {job_id}: RECONSTRUCT_AND_ANALYZE pipeline finished successfully in {duration:.2f} seconds.")
        
        return output

    async def _run_title_generation_pipeline(self, orchestrator_input: OrchestrationInput, job_id: str, conn) -> OrchestrationOutput:
        """
        The pipeline logic for generating a title for an existing KnowledgeCard.
        """
        start_time = time.time()
        
        card_id = orchestrator_input.payload.get("card_id")
        if not card_id:
            raise ValueError("Payload for GENERATE_TITLE task must contain a 'card_id'.")
            
        self.logger.info(f"Job {job_id}: GENERATE_TITLE pipeline starting for card_id: {card_id}")
        self.task_db_service.update_task_progress_stage(job_id, "Fetching card content", conn)

        card_content_str = self.task_db_service.get_knowledge_card_content_by_id(card_id, conn)
        if not card_content_str:
            raise ValueError(f"Could not retrieve content for KnowledgeCard with ID: {card_id}")

        self.task_db_service.update_task_progress_stage(job_id, "Running AI Title Generation Crew", conn)

        title_crew = GeneralPurposeTitleGenerationCrew(
            settings=self.settings,
            card_content=card_content_str,
            job_id=job_id
        )
        crew_result = await title_crew.akickoff()
        self.logger.info(f"Job {job_id}: Title generation crew finished. Result: {crew_result}")
        
        new_title = str(crew_result).strip()
        if not new_title:
            raise ValueError("Title generation crew returned an empty result.")
            
        self.logger.info(f"Job {job_id}: Successfully parsed new title: '{new_title}'")

        self.task_db_service.update_task_progress_stage(job_id, "Saving new title", conn)
        self.task_db_service.update_knowledge_card_title(card_id, new_title, conn)
        self.logger.info(f"Job {job_id}: Successfully saved new title to card {card_id}.")

        output = self._prepare_final_output(
            orchestrator_input, orchestrator_input.source_identifier, OrchestrationStatusCodeEnum.SUCCESS,
            new_title,
            [], {}, None, orchestrator_input.source_identifier, orchestrator_input.source_type,
            None, False, card_id
        )
        
        title_generation_result_payload = {"generated_title": new_title}
        self.task_db_service.update_task_status_completed(job_id, title_generation_result_payload, conn)
        
        duration = time.time() - start_time
        self.logger.info(f"Job {job_id}: GENERATE_TITLE pipeline finished successfully in {duration:.2f} seconds.")
        
        return output

    def _is_long_article(self, content_blocks: List[ContentBlock]) -> bool:
        """Checks if the document is long based on word count."""
        total_char_count = sum(len(block.content) for block in content_blocks if block.type == "text" and block.content)
        long_article_threshold = self.settings.long_article_char_threshold if self.settings else 3000
        return total_char_count > long_article_threshold

    def _prepare_final_output(self, original_input: OrchestrationInput, used_source_identifier: str, 
                              status_code: Union[OrchestrationStatusCodeEnum, str], extracted_title: Optional[str], 
                              content_blocks: List[ContentBlock], processed_images_data: Dict[str, EnrichedImageMetadata],
                              error_message: Optional[str], final_url: Optional[str], final_source_type: Optional[str], 
                              document_metadata: Optional[DocumentMetadata], is_long_article: bool = False, card_id: Optional[str] = None) -> OrchestrationOutput:
        
        status_enum_member = status_code
        if isinstance(status_code, str):
            try:
                status_enum_member = OrchestrationStatusCodeEnum[status_code.upper()]
            except KeyError:
                status_enum_member = OrchestrationStatusCodeEnum.FAILURE_UNHANDLED_EXCEPTION
        
        final_title = extracted_title or (document_metadata.title if document_metadata else None) or "Untitled"
        
        final_output = OrchestrationOutput(
            status_code=status_enum_member.value,
            user_id=original_input.user_id,
            document_id=original_input.job_id,
            source_identifier=used_source_identifier,
            source_type=final_source_type,
            processing_level_used=original_input.processing_level,
            extracted_title=final_title,
            is_long_article=is_long_article,
            original_content_blocks=content_blocks,
            processed_images_data=processed_images_data,
            document_metadata=document_metadata,
            error_message=error_message,
            card_id=card_id
        )
        return final_output

    async def execute(self, *args: Any, **kwargs: Any) -> ServiceResult[Any]:
        self.logger.error("The 'execute' method is not the primary entry point for ParallelOrchestrator. Use 'process' instead.")
        return ServiceResult.failure(error_message="Not Implemented: Use the 'process' method for ParallelOrchestrator.")