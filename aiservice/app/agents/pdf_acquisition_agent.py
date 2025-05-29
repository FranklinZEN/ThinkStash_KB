# Placeholder for TS-AI-Reconstruct-1: PDF Content Acquisition & Marking Agent 

import sys # Added import for sys
from crewai import Agent, Task
from typing import List, Type, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import os
import uuid 
import json 
import re 

# Tool Imports
from app.tools.data_extraction_tools import PyMuPDFParserTool, NougatPDFParserTool, PDFToImageTool, PDFMinerSixParserTool # Added PDFMinerSixParserTool
from app.tools.llm_interaction_tools import MultimodalLLMImageMarkerTool
from app.tools.utility_tools import DataStoreAccessTool

# Model Imports
from app.models.pdf_acquisition_models import PDFAcquisitionInput, PDFAcquisitionOutput, RawPDFImageWithID
# If ProcessedImageData was only for type hinting, we can just remove it.
# If other models from orchestration_models are needed by this agent, they should remain.
# For example, if ContentBlock is used:
# from app.models.orchestration_models import ContentBlock 

class PDFAcquisitionAgent:
    """Extracts content from PDF files according to V2.4 specifications using a tiered approach."""

    def __init__(self, 
                 pymupdf_parser_tool: PyMuPDFParserTool,
                 pdfminer_six_parser_tool: PDFMinerSixParserTool, # Added
                 nougat_parser_tool: NougatPDFParserTool, 
                 pdf_to_image_tool: PDFToImageTool,
                 multimodal_llm_marker_tool: MultimodalLLMImageMarkerTool,
                 data_store_tool: DataStoreAccessTool):
        
        self.pymupdf_parser_tool = pymupdf_parser_tool
        self.pdfminer_six_parser_tool = pdfminer_six_parser_tool # Added
        self.nougat_parser_tool = nougat_parser_tool
        self.pdf_to_image_tool = pdf_to_image_tool
        self.multimodal_llm_marker_tool = multimodal_llm_marker_tool
        self.data_store_tool = data_store_tool
        
        agent_tools = [
            self.pymupdf_parser_tool,
            self.pdfminer_six_parser_tool, # Added
            self.nougat_parser_tool, 
            self.pdf_to_image_tool,
            self.multimodal_llm_marker_tool,
            self.data_store_tool
        ]
        self.agent_instance = self._create_agent_instance(agent_tools)

    def _create_agent_instance(self, configured_tools: List[BaseModel]) -> Agent:
        return Agent(
            role='PDF Content Acquisition Specialist with Tiered Parsing for V2.4',
            goal=('Extract text (including LaTeX/code via tiered parsing - PyMuPDF, PDFMinerSix, then Nougat) and, if processing_level is "full_content", ' 
                  'convert PDF pages to images, use a multimodal LLM to identify images, extract metadata, and generate unique IDs (PDF_PAGE<P>_IMG<I>). ' 
                  'Store outputs using DataStoreAccessTool and return references/status.'),
            backstory=(
                "As a key member of the CoreReconstructionCrew, you specialize in dissecting PDF documents. "
                "You employ a sophisticated tiered parsing strategy: starting with the fast PyMuPDF, then trying PDFMinerSix for layout-aware extraction if needed, and finally escalating to advanced models like Nougat for OCR or complex academic content with math/code. "
                "If 'processing_level' is 'full_content', your responsibilities expand: you convert PDF pages to images using PDFToImageTool, then leverage the MultimodalLLMImageMarkerTool to meticulously analyze these page images, identifying embedded images, extracting descriptive metadata and captions, and assigning persistent, unique IDs (e.g., PDF_PAGE1_IMG1). "
                "All extracted text and raw image data (with IDs) are stored via DataStoreAccessTool. You provide references to this data, an extracted title (if possible), the parsing tier used, and a comprehensive status."
            ),
            tools=configured_tools,
            verbose=True,
            allow_delegation=False 
        )

    def get_agent(self) -> Agent:
        return self.agent_instance

    # --- Agent's Core Logic Methods (to be called by tasks) ---
    def _extract_title_from_path(self, file_path: str) -> str:
        return os.path.splitext(os.path.basename(file_path))[0]

    def _sanitize_for_path(self, text: Optional[str], max_length: int = 100) -> str:
        if not text: return f"untitled_{uuid.uuid4().hex[:6]}"
        text = str(text)
        text = re.sub(r'[^a-zA-Z0-9._-]', '_', text)
        text = re.sub(r'_+', '_', text)
        text = text.strip('_')
        return text[:max_length]

    def execute_pdf_processing(self, input_data: PDFAcquisitionInput, job_id_for_ds_keys: Optional[str] = None) -> PDFAcquisitionOutput:
        print(f"PDFAgent: Processing {input_data.file_path} for job ID: {job_id_for_ds_keys}")
        title = self._extract_title_from_path(input_data.file_path)
        # Ensure job_id_suffix is always a string, even if empty
        job_id_suffix = f"_{job_id_for_ds_keys}" if job_id_for_ds_keys else "_no_job_id"
        
        text_content_ref: Optional[str] = None
        image_list_ref: Optional[str] = None
        raw_images_for_pdf: List[RawPDFImageWithID] = [] # Holds RawPDFImageWithID objects before storing their ref
        status = "pending"
        error_message: Optional[str] = None
        extracted_text: Optional[str] = None
        accumulated_parse_errors = []

        # Placeholder for PyMuPDF parsing logic
        try:
            print(f"PDFAgent: Attempting PyMuPDF parsing for {input_data.file_path}")
            pymupdf_result = self.pymupdf_parser_tool._run(file_path=input_data.file_path)
            if isinstance(pymupdf_result, dict) and pymupdf_result.get("text_content"):
                extracted_text = pymupdf_result["text_content"]
                text_key = f"pdf_{self._sanitize_for_path(title)}_pymupdf_text{job_id_suffix}"
                self.data_store_tool._run(action="put", key=text_key, value=extracted_text)
                text_content_ref = text_key
                status = "success_pymupdf"
                print(f"PDFAgent: PyMuPDF success. Text stored at {text_content_ref}")
            else:
                status = "error_pymupdf_no_text"
                error_message = "PyMuPDF did not return text content."
                print(f"PDFAgent: PyMuPDF parsing issue: {error_message}")
                # Optionally, attempt PDFMinerSix as fallback
                if self.pdfminer_six_parser_tool:
                    print(f"PDFAgent: Attempting PDFMinerSix parsing for {input_data.file_path}")
                    pdfminer_text = self.pdfminer_six_parser_tool._run(file_path=input_data.file_path)
                    if pdfminer_text and not pdfminer_text.startswith("Error:"):
                        text_key = f"pdf_{self._sanitize_for_path(title)}_pdfminer_text{job_id_suffix}"
                        self.data_store_tool._run(action="put", key=text_key, value=pdfminer_text)
                        text_content_ref = text_key
                        extracted_text = pdfminer_text # Use this for context if image marking runs
                        status = "success_pdfminer"
                        error_message = None # Clear previous error
                        print(f"PDFAgent: PDFMinerSix success. Text stored at {text_content_ref}")
                    else:
                        status = "error_all_text_parsers_failed"
                        error_message = (error_message + "; " if error_message else "") + f"PDFMinerSix also failed or returned error: {pdfminer_text}"
                        print(f"PDFAgent: PDFMinerSix parsing issue: {pdfminer_text}")
        except Exception as e_parse:
            status = "error_text_parsing_exception"
            error_message = f"Exception during text parsing: {str(e_parse)}"
            print(f"PDFAgent: {error_message}")
            extracted_text = None # Ensure no partial text is used if parsing fails badly

        # Image processing logic (if processing_level is full_content and text was extracted or not required for images)
        if input_data.processing_level == "full_content":
            print(f"PDFAgent: Processing level is full_content. Attempting image extraction and marking for {input_data.file_path}")
            temp_image_output_folder = f"temp_pdf_images_{self._sanitize_for_path(title)}{job_id_suffix}_{uuid.uuid4().hex[:6]}"
            try:
                os.makedirs(temp_image_output_folder, exist_ok=True)
                page_image_paths = self.pdf_to_image_tool._run(pdf_path=input_data.file_path, output_folder=temp_image_output_folder)

                if isinstance(page_image_paths, str) and page_image_paths.startswith("Error:"):
                    status = "error_page_to_image_conversion" # Overwrite status if text was success but images failed
                    error_message = (error_message + "; " if error_message else "") + page_image_paths
                    print(f"PDFAgent: PDFToImageTool error: {page_image_paths}")
                elif page_image_paths and isinstance(page_image_paths, list):
                    print(f"PDFAgent: Converted {len(page_image_paths)} pages to images.")
                    for page_idx, page_image_path in enumerate(page_image_paths):
                        page_num_1_indexed = page_idx + 1
                        print(f"PDFAgent: Marking images on page {page_num_1_indexed} (image: {page_image_path})")
                        
                        # Provide some text context from the extracted text if available
                        page_context_text = None
                        if extracted_text:
                            # Basic way to get context: ~500 chars around an assumed position for the page
                            # This is very approximate and needs a better page-to-text mapping for real use
                            chars_per_page_estimate = 700 # Highly dependent on PDF structure
                            start_char = page_idx * chars_per_page_estimate
                            end_char = start_char + chars_per_page_estimate
                            page_context_text = extracted_text[start_char:end_char]
                            if not page_context_text and page_idx == 0: # Fallback for first page context
                                page_context_text = extracted_text[:700]

                        marker_output_json_str = self.multimodal_llm_marker_tool._run(
                            image_path_or_base64=page_image_path, 
                            page_number=page_num_1_indexed, 
                            text_context=page_context_text
                        )
                        try:
                            llm_findings: List[Dict[str, Any]] = json.loads(marker_output_json_str)
                            if llm_findings and isinstance(llm_findings, list) and (not llm_findings[0].get("error")):
                                for finding in llm_findings:
                                    figure_id_from_llm = finding.get("id", f"FIG_P{page_num_1_indexed}_{uuid.uuid4().hex[:4]}")
                                    unique_figure_id_for_pdf = f"P{page_num_1_indexed}_{self._sanitize_for_path(figure_id_from_llm, 30)}"
                                    
                                    # Store the full page image path as raw_image_data_ref for this figure
                                    # The ImageProcessingAgent will then use this path to get the actual image bytes
                                    # This avoids duplicating large image data if multiple figures are on one page image.
                                    page_image_ref_key = f"pdf_{self._sanitize_for_path(title)}_pageimg_{page_num_1_indexed}_path{job_id_suffix}"
                                    self.data_store_tool._run(action="put", key=page_image_ref_key, value=page_image_path)

                                    raw_pdf_image = RawPDFImageWithID(
                                        image_id=unique_figure_id_for_pdf, # Unique ID for this figure within the PDF context
                                        raw_image_data_ref=page_image_ref_key, # Ref to the stored full page image path
                                        page_number=page_num_1_indexed,
                                        image_type_from_llm=finding.get("type"),
                                        description=finding.get("description"),
                                        caption=finding.get("caption")
                                    )
                                    raw_images_for_pdf.append(raw_pdf_image)
                            elif llm_findings and isinstance(llm_findings, list) and llm_findings[0].get("error"):
                                print(f"PDFAgent: LLM image marker returned an error for page {page_num_1_indexed}: {llm_findings[0].get('error')}")
                                error_message = (error_message + "; " if error_message else "") + f"LLM marker error p{page_num_1_indexed}: {llm_findings[0].get('error')}"

                        except json.JSONDecodeError as e_json_llm:
                            print(f"PDFAgent: JSONDecodeError from LLM image marker for page {page_num_1_indexed}: {e_json_llm}")
                            error_message = (error_message + "; " if error_message else "") + f"LLM marker JSON error p{page_num_1_indexed}"
                        except Exception as e_llm_other:
                            print(f"PDFAgent: Exception from LLM image marker for page {page_num_1_indexed}: {e_llm_other}")
                            error_message = (error_message + "; " if error_message else "") + f"LLM marker other error p{page_num_1_indexed}"
                    
                    if raw_images_for_pdf:
                        image_list_ds_key = f"pdf_{self._sanitize_for_path(title)}_img_list{job_id_suffix}"
                        # Storing list of Pydantic models (as list of dicts)
                        self.data_store_tool._run(action="put", key=image_list_ds_key, value=json.dumps([img.model_dump() for img in raw_images_for_pdf]))
                        image_list_ref = image_list_ds_key
                        print(f"PDFAgent: Stored {len(raw_images_for_pdf)} identified raw PDF image details at {image_list_ref}")
                        if status.startswith("success"): status = "success_text_and_images" # Upgrade status
                        elif status.startswith("error_pymupdf") or status.startswith("error_all_text"): # If text failed but images okay
                            status = "success_images_only_text_failed"
                            error_message = (error_message + "; " if error_message else "") + "Text extraction failed but images were processed."
                    else:
                        print("PDFAgent: No images successfully marked or processed from PDF pages.")
                        if status.startswith("success"): status = "success_text_no_images_found_or_processed"
            except Exception as e_img_proc:
                print(f"PDFAgent: Exception during PDF image processing pipeline: {e_img_proc}")
                img_proc_error_msg = f"Image processing pipeline error: {str(e_img_proc)}"
                if status.startswith("success"): 
                    status = "error_image_processing_pipeline" 
                    error_message = img_proc_error_msg
                else: # Prepend to existing error message
                    error_message = (error_message + "; " if error_message else "") + img_proc_error_msg
            # No finally block to delete temp_image_output_folder here;
            # ImageProcessingPersistenceAgent will use the paths referenced in RawPDFImageWithID.raw_image_data_ref
            # That agent should be responsible for cleanup if it copies the files.
            # Or, a final cleanup step in the overall workflow could handle temp folders based on job_id.

        elif status == "pending": # If full_content not selected and no errors yet
            status = "success_text_only_no_image_processing"
            if not text_content_ref: # Should not happen if no errors before, but as a safeguard
                status = "error_no_text_and_no_image_processing"
                error_message = (error_message + "; " if error_message else "") + "No text extracted and image processing not requested."

        return PDFAcquisitionOutput(
            status=status,
            extracted_text_content_ref=text_content_ref,
            image_list_ref=image_list_ref, # This refers to the list of RawPDFImageWithID
            extracted_title=title, # Use the basic title for now
            error_message=error_message
        )

    # --- Task Definition for Agent (Conceptual) ---
    def task_process_pdf(self, agent_to_use: Agent, input_data: PDFAcquisitionInput) -> Task:
        """Task for processing a PDF file based on V2.4 specifications."""
        return Task(
            description=(
                f"Process PDF file: {input_data.file_path} with processing level: {input_data.processing_level}. "
                f"Perform tiered text parsing (PyMuPDF, PDFMinerSix, Nougat). If 'full_content', convert pages to images (PDFToImageTool), "
                f"then use MultimodalLLMImageMarkerTool to identify images, generate metadata, and unique IDs. "
                f"Store all outputs via DataStoreAccessTool and return references."
            ),
            expected_output=(
                "A PDFAcquisitionOutput model as a dictionary, containing status, extracted title, parsing tier, "
                "references to extracted text content and list of raw image data with IDs (if applicable), and any error messages."
            ),
            agent=agent_to_use,
        )

# Placeholder for uuid if not already imported
if 'uuid' not in sys.modules:
    import uuid

# Further methods specific to this agent's internal logic could be added here.
# For example, a method to orchestrate its own sequence of tool calls for a given PDF.
# def process_pdf_file(self, pdf_path):
#     # 1. Call tiered parsing tool
#     # 2. Call page to image conversion tool for pages with images
#     # 3. Call multimodal LLM image marking tool for those images
#     # 4. Integrate markers
#     # 5. Package output
#     pass

# Further methods for tiered parsing logic, image marking invocation etc. will be added. 