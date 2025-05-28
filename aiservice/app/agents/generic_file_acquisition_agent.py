# Placeholder for TS-AI-Reconstruct-2: Generic File Content Acquisition Agent (DOCX, TXT, MD) 

from crewai import Agent, Task
from typing import List, Type, Dict, Any, Optional
from pydantic import BaseModel
# Import specific tool classes if they are to be instantiated here, e.g.:
# from app.tools.data_extraction_tools import DocxParserTool, TxtParserTool, MarkdownParserTool

from app.tools.data_extraction_tools import DocxParserTool, TxtParserTool, MarkdownParserTool
from app.tools.utility_tools import DataStoreAccessTool
from app.models.file_acquisition_models import FileAcquisitionInput, FileAcquisitionOutput, RawOrLinkedImage
import uuid
import os
import re
import json

class GenericFileContentAcquisitionAgent:
    """Handles DOCX, TXT, and MD files according to processing_level."""

    def __init__(self, docx_parser_tool: DocxParserTool, txt_parser_tool: TxtParserTool, 
                 markdown_parser_tool: MarkdownParserTool, data_store_tool: DataStoreAccessTool):
        self.docx_parser_tool = docx_parser_tool
        self.txt_parser_tool = txt_parser_tool
        self.markdown_parser_tool = markdown_parser_tool
        self.data_store_tool = data_store_tool
        
        # Consolidate tools for agent configuration
        agent_tools = [docx_parser_tool, txt_parser_tool, markdown_parser_tool, data_store_tool]
        self.agent_instance = self._create_agent_instance(agent_tools)

    def _create_agent_instance(self, configured_tools: List[BaseModel]) -> Agent:
        return Agent(
            role='Generic File Content Acquisition Agent (DOCX, TXT, MD) for V2.4',
            goal=('Efficiently extract text and, if processing_level is "full_content", ' 
                  'identify/extract images (or links to images for MD) from DOCX, TXT, or MD files. '
                  'Assign unique IDs to images. Store extracted content and image data using DataStoreAccessTool. '
                  'Return references and status.'),
            backstory=(
                "You are a specialist agent within the CoreReconstructionCrew, tasked with parsing common office and text-based file formats: DOCX, TXT, and Markdown (MD). "
                "You receive a file path, its type, and a 'processing_level'. For DOCX, you extract text and images, assigning unique IDs like 'DOCX_IMG_<I>'. "
                "For TXT, you read the raw text. For MD, you parse text, code, math, and identify linked images, assigning IDs like 'MD_IMG_<I>'. "
                "If 'processing_level' is 'text_only', you skip all image processing. All significant outputs (text, image lists) are stored via the DataStoreAccessTool, and you return references to this stored data, along with any extracted title and a status report."
            ),
            tools=configured_tools,
            verbose=True,
            allow_delegation=False # This agent uses its tools directly for its tasks
        )
    
    def get_agent(self) -> Agent:
        """Returns the configured CrewAI Agent instance."""
        return self.agent_instance

    # --- Agent's Core Logic Methods (to be called by tasks) ---

    def _extract_title_from_path(self, file_path: str) -> str:
        """Extracts a basic title from the file path (filename without extension)."""
        return os.path.splitext(os.path.basename(file_path))[0]

    def _sanitize_for_path(self, text: Optional[str], max_length: int = 100) -> str:
        if not text: return f"untitled_{uuid.uuid4().hex[:6]}"
        text = str(text)
        text = re.sub(r'[^a-zA-Z0-9._-]', '_', text)
        text = re.sub(r'_+', '_', text)
        text = text.strip('_')
        return text[:max_length]

    def dispatch_file_processing(self, input_data: FileAcquisitionInput, job_id_for_ds_keys: Optional[str] = None) -> FileAcquisitionOutput:
        print(f"GenericFileAgent: Dispatching for {input_data.file_path}, type: {input_data.source_content_type}, job ID: {job_id_for_ds_keys}")
        if input_data.source_content_type == "docx":
            return self.execute_docx_processing(input_data, job_id_for_ds_keys)
        elif input_data.source_content_type == "md":
            return self.execute_markdown_processing(input_data, job_id_for_ds_keys)
        elif input_data.source_content_type == "txt":
            return self.execute_txt_processing(input_data, job_id_for_ds_keys)
        else:
            return FileAcquisitionOutput(
                status="error_unsupported_file_type", 
                error_message=f"Unsupported file type for GenericFileAgent: {input_data.source_content_type}",
                extracted_title=self._extract_title_from_path(input_data.file_path)
            )

    def execute_txt_processing(self, input_data: FileAcquisitionInput, job_id_for_ds_keys: Optional[str] = None) -> FileAcquisitionOutput:
        print(f"GenericFileAgent: TXT processing for {input_data.file_path}, job ID: {job_id_for_ds_keys}")
        title = self._extract_title_from_path(input_data.file_path)
        job_id_suffix = f"_{job_id_for_ds_keys}" if job_id_for_ds_keys else "_no_job_id"
        text_content_ref: Optional[str] = None
        status = "success_txt"
        error_message: Optional[str] = None

        try:
            raw_text = self.txt_parser_tool._run(file_path=input_data.file_path)
            if raw_text is None or (isinstance(raw_text, str) and raw_text.startswith("Error:")):
                status = "error_parsing_txt"
                error_message = raw_text if isinstance(raw_text, str) else "TxtParserTool returned None."
            else:
                text_key = f"file_{self._sanitize_for_path(title)}_txt_text{job_id_suffix}"
                self.data_store_tool._run(action="put", key=text_key, value=raw_text)
                text_content_ref = text_key
        except Exception as e:
            status = "error_exception_txt"
            error_message = f"Exception in TXT processing: {str(e)}"
        
        return FileAcquisitionOutput(
            status=status,
            extracted_text_content_ref=text_content_ref,
            # No images for TXT
            extracted_title=title,
            error_message=error_message,
            source_content_type_processed=input_data.source_content_type
        )

    def execute_markdown_processing(self, input_data: FileAcquisitionInput, job_id_for_ds_keys: Optional[str] = None) -> FileAcquisitionOutput:
        print(f"GenericFileAgent: Markdown processing for {input_data.file_path}, job ID: {job_id_for_ds_keys}")
        title = self._extract_title_from_path(input_data.file_path)
        job_id_suffix = f"_{job_id_for_ds_keys}" if job_id_for_ds_keys else "_no_job_id"
        text_content_ref: Optional[str] = None
        image_list_ref: Optional[str] = None
        status = "success_md"
        error_message: Optional[str] = None
        raw_images_for_md: List[RawOrLinkedImage] = []

        try:
            parsed_md_output = self.markdown_parser_tool._run(file_path=input_data.file_path)
            if isinstance(parsed_md_output, str) and parsed_md_output.startswith("Error:"):
                status = "error_parsing_md"
                error_message = parsed_md_output
            elif isinstance(parsed_md_output, dict):
                md_text = parsed_md_output.get("text_content")
                if md_text:
                    text_key = f"file_{self._sanitize_for_path(title)}_md_text{job_id_suffix}"
                    self.data_store_tool._run(action="put", key=text_key, value=md_text)
                    text_content_ref = text_key
                
                md_images = parsed_md_output.get("images", [])
                if md_images:
                    for idx, img_info in enumerate(md_images):
                        raw_images_for_md.append(RawOrLinkedImage(
                            image_id=img_info.get("image_id", f"MD_IMG_{idx+1}{job_id_suffix}"), 
                            source_path_or_url=img_info.get("url"),
                            alt_text=img_info.get("alt_text")
                        ))
                    image_list_key = f"file_{self._sanitize_for_path(title)}_md_images{job_id_suffix}"
                    self.data_store_tool._run(action="put", key=image_list_key, value=json.dumps([img.model_dump() for img in raw_images_for_md]))
                    image_list_ref = image_list_key
            else:
                status = "error_parsing_md"
                error_message = "MarkdownParserTool returned unexpected data."

        except Exception as e:
            status = "error_exception_md"
            error_message = f"Exception in Markdown processing: {str(e)}"

        return FileAcquisitionOutput(
            status=status,
            extracted_text_content_ref=text_content_ref,
            raw_or_linked_image_list_with_ids_ref=image_list_ref,
            extracted_title=title,
            error_message=error_message,
            source_content_type_processed=input_data.source_content_type
        )

    def execute_docx_processing(self, input_data: FileAcquisitionInput, job_id_for_ds_keys: Optional[str] = None) -> FileAcquisitionOutput:
        print(f"GenericFileAgent: DOCX processing for {input_data.file_path}, job ID: {job_id_for_ds_keys}")
        title = self._extract_title_from_path(input_data.file_path)
        job_id_suffix = f"_{job_id_for_ds_keys}" if job_id_for_ds_keys else "_no_job_id"
        text_content_ref: Optional[str] = None
        image_list_ref: Optional[str] = None
        status = "success_docx"
        error_message: Optional[str] = None
        raw_images_for_docx: List[RawOrLinkedImage] = []
        
        temp_docx_image_folder = f"temp_docx_images_{self._sanitize_for_path(title)}{job_id_suffix}_{uuid.uuid4().hex[:6]}"
        try:
            os.makedirs(temp_docx_image_folder, exist_ok=True)
            parsed_docx_output = self.docx_parser_tool._run(file_path=input_data.file_path, image_output_folder=temp_docx_image_folder)

            if isinstance(parsed_docx_output, str) and parsed_docx_output.startswith("Error:"):
                status = "error_parsing_docx"
                error_message = parsed_docx_output
            elif isinstance(parsed_docx_output, dict):
                docx_text = parsed_docx_output.get("text_content")
                if docx_text:
                    text_key = f"file_{self._sanitize_for_path(title)}_docx_text{job_id_suffix}"
                    self.data_store_tool._run(action="put", key=text_key, value=docx_text)
                    text_content_ref = text_key
                
                docx_images = parsed_docx_output.get("images", [])
                if docx_images:
                    for img_info in docx_images: # DocxParserTool returns list of dicts
                        raw_images_for_docx.append(RawOrLinkedImage(
                            image_id=img_info.get("image_id"), # Already includes filename
                            source_path_or_url=img_info.get("saved_path"), # This is the local path
                            # alt_text might not be available from python-docx easily
                        ))
                    image_list_key = f"file_{self._sanitize_for_path(title)}_docx_images{job_id_suffix}"
                    self.data_store_tool._run(action="put", key=image_list_key, value=json.dumps([img.model_dump() for img in raw_images_for_docx]))
                    image_list_ref = image_list_key
            else:
                status = "error_parsing_docx"
                error_message = "DocxParserTool returned unexpected data."
        except Exception as e:
            status = "error_exception_docx"
            error_message = f"Exception in DOCX processing: {str(e)}"
        # Note: temp_docx_image_folder is not cleaned up here. 
        # ImageProcessingPersistenceAgent will use the source_path_or_url if it's a local path.

        return FileAcquisitionOutput(
            status=status,
            extracted_text_content_ref=text_content_ref,
            raw_or_linked_image_list_with_ids_ref=image_list_ref,
            extracted_title=title,
            error_message=error_message,
            source_content_type_processed=input_data.source_content_type
        )

    # --- Task Definitions for Agent (Conceptual) ---
    # These tasks would be defined by the OrchestrationAgent or a Crew and would call the execute_* methods.

    def task_process_file(self, agent_to_use: Agent, input_data: FileAcquisitionInput) -> Task:
        """A single task that dispatches to the correct internal processing method based on source_content_type."""
        
        description = f"Process file: {input_data.file_path} (type: {input_data.source_content_type}, level: {input_data.processing_level}). "
        if input_data.source_content_type == "docx":
            description += "Extract text and images (if full_content) from DOCX."
        elif input_data.source_content_type == "txt":
            description += "Extract text from TXT."
        elif input_data.source_content_type == "md":
            description += "Parse Markdown for text, code, math, and linked images (if full_content)."
        else:
            description += "Unsupported file type for this agent."

        # The actual action of this task would be a method in this agent that calls the specific
        # execute_docx_processing, execute_txt_processing, or execute_markdown_processing based on input_data.source_content_type.
        # For example, a method like `dispatch_file_processing(self, context: Dict[str, Any]) -> Dict[str,Any]`
        # where context contains the FileAcquisitionInput data.
        
        return Task(
            description=description,
            expected_output="A FileAcquisitionOutput model as a dictionary, containing status, extracted title reference, text content reference, and image list reference (if applicable).",
            agent=agent_to_use,
            # arguments = input_data.model_dump() # To pass to the action method
        )

# Example of how the dispatching method might look inside the agent class:
# def dispatch_file_processing(self, file_path: str, processing_level: str, source_content_type: str) -> Dict[str, Any]:
#     input_model = FileAcquisitionInput(file_path=file_path, processing_level=processing_level, source_content_type=source_content_type)
#     if source_content_type == "docx":
#         output = self.execute_docx_processing(input_model)
#     elif source_content_type == "txt":
#         output = self.execute_txt_processing(input_model)
#     elif source_content_type == "md":
#         output = self.execute_markdown_processing(input_model)
#     else:
#         output = FileAcquisitionOutput(
#             status="unsupported_type_for_agent", 
#             error_message=f"File type '{source_content_type}' not supported by this agent."
#         )
#     return output.model_dump()

# Further development:
# 1. Implement the actual logic in execute_docx_processing, execute_txt_processing, execute_markdown_processing.
#    - Use the respective parser tools.
#    - Implement image ID generation (e.g., DOCX_IMG_1, MD_IMG_1) if processing_level="full_content".
#    - Use DataStoreAccessTool to store extracted_text_content and raw_or_linked_image_list_with_ids.
#      The output model should then contain *references* (keys) to this stored data.
# 2. Refine error handling and status codes in FileAcquisitionOutput.
# 3. Ensure the output data (especially image lists) conforms to what ImageProcessingPersistenceAgent expects.

# Agent-specific methods for orchestrating the processing of a given file
# (e.g., deciding which tool to use based on file extension) could be added here.
# def process_file(self, file_path, file_type):
#     if file_type == 'docx':
#         return self.docx_parser._run(file_path)
#     elif file_type == 'txt':
#         return self.txt_parser._run(file_path)
#     # ... and so on
#     pass

# Methods for DOCX, TXT, MD processing will be added here. 