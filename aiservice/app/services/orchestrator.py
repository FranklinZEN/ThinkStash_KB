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
from aiservice.app.utils.url_utils import custom_normalize_url
from aiservice.app.services.task_db_service import TaskDBService
from ..crews.title_generation_crew import GeneralPurposeTitleGenerationCrew
from ..crews.keyword_extraction_crew import GeneralPurposeKeywordExtractionCrew

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
            
            self.task_db_service.update_task_status_processing(job_id, conn)
            
            output = await self._run_pipeline(orchestrator_input, job_id, conn)

            conn.commit()
            self.logger.info(f"Job {job_id}: Pipeline successful. Database transaction committed.")
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
                OrchestrationStatusCodeEnum.ERROR_UNKNOWN,
                None, [], {}, str(e), orchestrator_input.source_identifier,
                orchestrator_input.source_type, None, False
            )
            return ServiceResult.failure(error_message=str(e), error_details=failure_output.model_dump())

        finally:
            if conn:
                self.task_db_service.release_connection(conn)
                self.logger.info(f"Job {job_id}: Database connection released back to pool.")

    async def _run_pipeline(self, orchestrator_input: OrchestrationInput, job_id: str, conn) -> OrchestrationOutput:
        """
        The core pipeline logic, now running within a managed transaction.
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
            enriched_images=enriched_images_list,
            raw_images=raw_images_from_acquisition,
            document_metadata=document_metadata_obj,
            job_id=job_id,
            user_id=orchestrator_input.user_id
        )
        structuring_result = await self.content_structuring_service.execute(structuring_input)

        if not structuring_result.is_success() or structuring_result.data is None:
            raise Exception(f"Content structuring failed: {structuring_result.error_message}")

        final_content_blocks = structuring_result.data

        # --- MANUAL BYPASS: Extract full text from content blocks ---
        # This logic is placed here to bypass the faulty FullTextContentExtractorTool.
        # It robustly extracts text from the structured blocks before passing it to the AI crews.
        extracted_text = ""
        try:
            texts = []
            if isinstance(final_content_blocks, list):
                for block in final_content_blocks:
                    block_dict = block.model_dump() # Convert ContentBlock to dict
                    if isinstance(block_dict, dict):
                        content = block_dict.get('content')
                        if isinstance(content, list):
                            for inline_item in content:
                                if isinstance(inline_item, dict) and 'text' in inline_item and inline_item['text']:
                                    texts.append(str(inline_item['text']))
                        elif isinstance(content, str) and content:
                            texts.append(content)
            if texts:
                extracted_text = "\\n\\n".join(texts)
        except Exception as e_text:
            self.logger.error(f"Job {job_id}: Failed to extract text from content blocks: {e_text}", exc_info=True)
            accumulated_warnings.append(f"Text Extraction Failed: {e_text}")
        
        # --- Title Generation (Synchronous) ---
        if orchestrator_input.run_title_generation and extracted_text:
            self.logger.info(f"Job {job_id}: Title generation requested. Running crew synchronously.")
            try:
                # Pass the extracted text directly to the crew
                title_crew = GeneralPurposeTitleGenerationCrew(full_text_content=extracted_text)
                title_output = title_crew.run() # No need to pass content_block_dicts anymore

                if document_metadata_obj and title_output.suggested_title and not title_output.suggested_title.startswith("Error:"):
                    document_metadata_obj.title = title_output.suggested_title
                    page_title = title_output.suggested_title
                elif title_output.suggested_title and title_output.suggested_title.startswith("Error:"):
                    accumulated_warnings.append(f"Title Generation Failed: {title_output.suggested_title}")
            except Exception as e_title:
                self.logger.error(f"Job {job_id}: Title generation crew failed with an exception: {e_title}", exc_info=True)
                accumulated_warnings.append(f"Title Generation Failed: {str(e_title)}")
        
        # --- Keyword Extraction (Synchronous) ---
        if orchestrator_input.run_keyword_extraction and extracted_text:
            self.logger.info(f"Job {job_id}: Keyword extraction requested. Running crew synchronously.")
            try:
                # Pass the extracted text directly to the crew
                keyword_crew = GeneralPurposeKeywordExtractionCrew(content_blocks=extracted_text) # content_blocks will now hold the string
                keywords_result = keyword_crew.run()
                if isinstance(keywords_result, list):
                    if document_metadata_obj:
                        document_metadata_obj.keywords = keywords_result
                else:
                    accumulated_warnings.append(f"Keyword Extraction Failed: {keywords_result}")

            except Exception as e_kw:
                self.logger.error(f"Job {job_id}: Keyword extraction crew failed with an exception: {e_kw}", exc_info=True)
                accumulated_warnings.append(f"Keyword Extraction Failed: {str(e_kw)}")

        self.task_db_service.update_task_progress_stage(job_id, "Finalizing and preparing output", conn)
        
        is_long = self._is_long_article(final_content_blocks)
        if accumulated_warnings:
            error_message = "; ".join(accumulated_warnings)

        # Step 4: DO NOT create the Knowledge Card. Instead, prepare the data for output.
        final_title = page_title or "Untitled Document"
        
        # Step 5: Finalize and return the result with the raw content
        log_extra = {'task_id': job_id}
        logger.info(f"Finalizing and preparing output with raw content", extra=log_extra)

        output = self._prepare_final_output(
            orchestrator_input, processed_source_identifier, OrchestrationStatusCodeEnum.SUCCESS,
            final_title, final_content_blocks, processed_images_data_dict, error_message,
            final_url, determined_final_source_type, document_metadata_obj, is_long
        )

        self.task_db_service.update_task_status_completed(job_id, output.model_dump(), conn)
        
        duration = time.time() - start_time
        self.logger.info(f"Job {job_id}: Pipeline finished successfully in {duration:.2f} seconds.")
        
        return output

    def _is_long_article(self, content_blocks: List[Any]) -> bool:
        """
        Calculates the total character count from text-based blocks to determine if an
        article is "long". This is used to decide whether to trigger summarization.
        """
        total_char_count = 0
        
        # Create a stack for depth-first traversal of content blocks and their children
        stack = list(content_blocks)

        while stack:
            block = stack.pop()

            # Ensure we are dealing with a ContentBlock object before proceeding
            if not hasattr(block, 'type'):
                continue

            # Add children to the stack to be processed
            if hasattr(block, 'children') and block.children:
                stack.extend(block.children)

            # Process content if it exists
            if hasattr(block, 'content') and block.content and isinstance(block.content, list):
                # block.content is a List of objects, hopefully InlineContent
                for content_item in block.content:
                    # Check for InlineContent-like structure
                    if hasattr(content_item, 'type') and content_item.type == 'text' and hasattr(content_item, 'text'):
                        total_char_count += len(content_item.text or '')
        
        long_article_threshold = self.settings.long_article_char_threshold if self.settings else 3000
        self.logger.info(f"Calculated total character count for article: {total_char_count}. Threshold: {long_article_threshold}")
        return total_char_count > long_article_threshold

    def _prepare_final_output(self, original_input: OrchestrationInput, used_source_identifier: str, 
                              status_code: Union[OrchestrationStatusCodeEnum, str], title: Optional[str], 
                              content_blocks: List[ContentBlock], processed_images_data: Dict[str, EnrichedImageMetadata],
                              error_message: Optional[str], final_url: Optional[str], final_source_type: Optional[str], 
                              document_metadata: Optional[DocumentMetadata], is_long_article: bool = False) -> OrchestrationOutput:
        
        status_enum_member = status_code
        if isinstance(status_code, str):
            try:
                status_enum_member = OrchestrationStatusCodeEnum[status_code.upper()]
            except KeyError:
                status_enum_member = OrchestrationStatusCodeEnum.FAILURE_UNHANDLED_EXCEPTION
        
        final_title = title or (document_metadata.title if document_metadata else None) or "Untitled"
        
        final_output = OrchestrationOutput(
            status_code=status_enum_member.value,
            user_id=original_input.user_id,
            document_id=original_input.job_id,
            source_identifier=used_source_identifier,
            source_type=final_source_type or "unknown",
            processing_level_used=original_input.processing_level,
            title=final_title,
            content_blocks=content_blocks,
            is_long_article=is_long_article,
            processed_images_data=processed_images_data,
            document_metadata=document_metadata,
            error_message=error_message,
            card_id=None # Explicitly set to None as it's no longer created here
        )
        return final_output

    async def execute(self, *args: Any, **kwargs: Any) -> ServiceResult[Any]:
        """Provide a concrete implementation for the abstract method."""
        # This implementation will depend on how you intend to use the `execute` method.
        # For now, it can be a placeholder.
        raise NotImplementedError("The 'execute' method must be implemented in the derived class.")

    async def _run_content_rewrite_pipeline(self, content_blocks: List[Dict[str, Any]], job_id: str, conn) -> List[Dict[str, Any]]:
        """
        Runs the content rewrite crew for a given set of content blocks.
        This is a separate pipeline for asynchronous execution.
        """
        self.logger.info(f"Job {job_id}: Starting content rewrite pipeline.")
        # TODO: Implement the call to the ContentRewriteCrewManager
        # For now, we'll just return the original content blocks as a placeholder
        await asyncio.sleep(1) # Simulate async work
        self.logger.info(f"Job {job_id}: Content rewrite pipeline placeholder finished.")
        return content_blocks