import sys
import os
from pathlib import Path
import json
import uuid

# Adjust sys.path to include the project root directory (aiservice)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Model Imports ---
from app.models.orchestration_models import OrchestrationInput, OrchestrationOutput, ProcessedImageData, ContentBlock
from app.models.file_acquisition_models import FileAcquisitionInput, FileAcquisitionOutput
from app.models.web_acquisition_models import WebAcquisitionInput, WebAcquisitionOutput
from app.models.pdf_acquisition_models import PDFAcquisitionInput, PDFAcquisitionOutput
from app.models.image_processing_models import ImageProcessingInput, ImageProcessingOutput
from app.models.content_structuring_models import ContentStructuringInput, ContentStructuringOutput

# --- Tool Imports ---
from app.tools.utility_tools import ContentTypeDetectionTool, DataStoreAccessTool
from app.tools.data_extraction_tools import (
    DocxParserTool, TxtParserTool, MarkdownParserTool, 
    PyMuPDFParserTool, NougatPDFParserTool, PDFToImageTool, PDFMinerSixParserTool
)
from app.tools.web_tools import WebContentFetcherTool
from app.tools.content_processing_tools import ImageDownloaderTool, GCSUploadTool, ImageMetadataTool
from app.tools.llm_interaction_tools import MultimodalLLMImageMarkerTool, AdvancedLLMStructuringTool

# --- Agent Imports ---
from app.agents.orchestration_agent import OrchestrationAgent
from app.agents.generic_file_acquisition_agent import GenericFileContentAcquisitionAgent
from app.agents.web_url_acquisition_agent import WebURLContentAcquisitionAgent
from app.agents.pdf_acquisition_agent import PDFAcquisitionAgent
from app.agents.image_processing_agent import ImageProcessingPersistenceAgent
from app.agents.content_structuring_agent import ContentConsolidationStructuringAgent

# --- Main Script --- 
def run_crew_simulation(source_type: str, source_identifier: str, processing_level: str = "full_content"):
    print(f"=== Starting Core Reconstruction for: {source_identifier} (Type: {source_type}, Level: {processing_level}) ===\n")
    job_id = str(uuid.uuid4())

    # 1. Initialize Tools (Shared DataStore)
    print("Initializing tools...")
    data_store_dict = {}
    data_store_tool = DataStoreAccessTool(data_store=data_store_dict)
    
    content_type_detection_tool = ContentTypeDetectionTool()
    docx_parser_tool = DocxParserTool()
    txt_parser_tool = TxtParserTool()
    markdown_parser_tool = MarkdownParserTool()
    pymupdf_parser_tool = PyMuPDFParserTool()
    nougat_parser_tool = NougatPDFParserTool() # Will use placeholder logic if no service_url
    pdf_to_image_tool = PDFToImageTool()
    web_content_fetcher_tool = WebContentFetcherTool()
    image_downloader_tool = ImageDownloaderTool()
    gcs_upload_tool = GCSUploadTool() # Will try to get bucket from env/config
    image_metadata_tool = ImageMetadataTool()
    # LLM tools will use placeholder logic if OpenAI client not available/configured
    multimodal_llm_marker_tool = MultimodalLLMImageMarkerTool(client=None) # Pass explicit None for now
    advanced_llm_structuring_tool = AdvancedLLMStructuringTool(client=None) # Pass explicit None for now
    pdfminer_six_parser_tool = PDFMinerSixParserTool() # Initialize PDFMinerSixParserTool
    print("Tools initialized.\n")

    # 2. Initialize Agents
    print("Initializing agents...")
    orchestration_agent = OrchestrationAgent(content_type_detection_tool, data_store_tool)
    generic_file_agent = GenericFileContentAcquisitionAgent(docx_parser_tool, txt_parser_tool, markdown_parser_tool, data_store_tool)
    web_url_agent = WebURLContentAcquisitionAgent(web_content_fetcher_tool, data_store_tool)
    pdf_agent = PDFAcquisitionAgent(pymupdf_parser_tool, pdfminer_six_parser_tool, nougat_parser_tool, pdf_to_image_tool, multimodal_llm_marker_tool, data_store_tool)
    image_processing_agent = ImageProcessingPersistenceAgent(image_downloader_tool, gcs_upload_tool, image_metadata_tool, data_store_tool)
    content_structuring_agent = ContentConsolidationStructuringAgent(advanced_llm_structuring_tool, data_store_tool)
    print("Agents initialized.\n")

    # --- Simulated Orchestration Flow ---
    orchestration_input = OrchestrationInput(source_type=source_type, source_identifier=source_identifier, processing_level=processing_level)
    
    # Step 1: Initial Triage
    print("--- Step 1: Orchestration - Initial Triage ---")
    triage_results = orchestration_agent.execute_initial_triage(orchestration_input)
    print(f"Triage Output: {triage_results}\n")
    if triage_results.get("validation_status") == "failure":
        print(f"Triage failed: {triage_results.get('error_message')}. Halting.")
        return

    # Step 2: Routing
    print("--- Step 2: Orchestration - Routing ---")
    routing_results = orchestration_agent.execute_routing(triage_results)
    print(f"Routing Output: {routing_results}\n")
    if routing_results.get("routing_decision", "").startswith("routing_failed"):
        print(f"Routing failed: {routing_results.get('error_message')}. Halting.")
        # Even if routing fails, we might still want to call error aggregation and output aggregation
        # to get a structured error response from the orchestrator.
        error_agg_result = orchestration_agent.execute_error_aggregation(orchestration_input, triage_results)
        final_output = orchestration_agent.execute_output_aggregation(orchestration_input, error_agg_result, None, False, [], None)
        print(f"\nFINAL Orchestration Output (Routing Failure):\n{final_output.model_dump_json(indent=2)}")
        return

    # Step 3: Content Acquisition (based on routing)
    print(f"--- Step 3: Content Acquisition ({routing_results.get('routing_decision')}) ---")
    acquisition_output_dict: Optional[Dict[str, Any]] = None
    extracted_title_from_acq: Optional[str] = None
    pdf_image_list_ref_from_acq: Optional[str] = None
    generic_file_image_list_ref_from_acq: Optional[str] = None
    web_image_list_ref_from_acq: Optional[str] = None
    text_content_ref_from_acq: Optional[str] = None

    acq_input_file_path = routing_results.get("source_identifier") # Could be URL or file path
    acq_content_type_hint = routing_results.get("content_type_hint")

    if routing_results["routing_decision"] == "route_to_pdf_agent":
        pdf_input = PDFAcquisitionInput(file_path=acq_input_file_path, processing_level=processing_level)
        acq_output_model = pdf_agent.execute_pdf_processing(pdf_input)
        acquisition_output_dict = acq_output_model.model_dump()
        extracted_title_from_acq = acq_output_model.extracted_title
        text_content_ref_from_acq = acq_output_model.extracted_text_content_ref
        pdf_image_list_ref_from_acq = acq_output_model.raw_image_list_with_ids_ref
    elif routing_results["routing_decision"] == "route_to_generic_file_agent":
        file_input = FileAcquisitionInput(file_path=acq_input_file_path, processing_level=processing_level, source_content_type=acq_content_type_hint)
        acq_output_model = generic_file_agent.dispatch_file_processing(file_input) # Assuming dispatch method
        acquisition_output_dict = acq_output_model.model_dump()
        extracted_title_from_acq = acq_output_model.extracted_title
        text_content_ref_from_acq = acq_output_model.extracted_text_content_ref
        generic_file_image_list_ref_from_acq = acq_output_model.raw_or_linked_image_list_with_ids_ref
    elif routing_results["routing_decision"] == "route_to_web_agent":
        web_input = WebAcquisitionInput(url=acq_input_file_path, processing_level=processing_level)
        acq_output_model = web_url_agent.execute_comprehensive_url_processing(web_input)
        acquisition_output_dict = acq_output_model.model_dump()
        extracted_title_from_acq = acq_output_model.page_title_from_web
        text_content_ref_from_acq = acq_output_model.extracted_text_content_ref
        web_image_list_ref_from_acq = acq_output_model.extracted_image_url_list_with_ids_ref
        # Special case: if Web agent downloaded a PDF
        if acq_output_model.status == "success_pdf_redirect" and acq_output_model.downloaded_pdf_path_ref:
            print("Web agent redirected to and processed a PDF. This might need further routing to PDF agent or direct handling.")
            # For this simulation, we'll assume orchestrator can decide what to do. 
            # Here, we'll treat the downloaded_pdf_path_ref as if it were a raw_image_list_ref for simplicity of flow to image processor
            # but this needs proper handling in a full system (e.g. PDF agent takes over).
            # For now, ImageProcessing may not know how to handle a PDF content ref directly as an "image".
            pass 

    print(f"Acquisition Output: {json.dumps(acquisition_output_dict, indent=2)}\n")
    if acquisition_output_dict and acquisition_output_dict.get("status","").startswith("error"):
        print(f"Acquisition failed: {acquisition_output_dict.get('error_message')}. Proceeding to error aggregation.")
        # Fall through to error aggregation and output
        pass

    # Step 4: Image Processing (Conditional)
    print("--- Step 4: Image Processing ---")
    image_processing_result_dict: Optional[Dict[str, Any]] = None
    processed_image_list_ref_final: Optional[str] = None

    if processing_level == "full_content" and (pdf_image_list_ref_from_acq or generic_file_image_list_ref_from_acq or web_image_list_ref_from_acq):
        image_input = ImageProcessingInput(
            pdf_image_list_ref=pdf_image_list_ref_from_acq,
            generic_file_image_list_ref=generic_file_image_list_ref_from_acq,
            web_image_list_ref=web_image_list_ref_from_acq,
            original_source_identifier=source_identifier,
            source_type=source_type,
            job_id=job_id
        )
        img_output_model = image_processing_agent.execute_image_processing_pipeline(image_input)
        image_processing_result_dict = img_output_model.model_dump()
        processed_image_list_ref_final = img_output_model.processed_image_data_list_ref
        print(f"Image Processing Output: {json.dumps(image_processing_result_dict, indent=2)}\n")
    else:
        print("Image processing skipped (text_only or no image refs from acquisition).\n")

    # Step 5: Content Consolidation & Structuring
    print("--- Step 5: Content Structuring ---")
    structuring_result_dict: Optional[Dict[str, Any]] = None
    final_blocks_from_structuring: List[Dict[str,Any]] = []
    is_long_article_from_structuring: bool = False

    if text_content_ref_from_acq: # Only run if we have text
        structuring_input = ContentStructuringInput(
            extracted_text_content_ref=text_content_ref_from_acq,
            processed_image_data_list_ref=processed_image_list_ref_final, # Use the output from image processing
            source_content_type_hint=acq_content_type_hint or source_type,
            page_title_from_acquisition=extracted_title_from_acq
        )
        structuring_output_model = content_structuring_agent.execute_content_structuring(structuring_input)
        structuring_result_dict = structuring_output_model.model_dump()
        final_blocks_from_structuring = structuring_output_model.final_original_content_blocks
        is_long_article_from_structuring = structuring_output_model.is_long_article_flag
        print(f"Structuring Output: {json.dumps(structuring_result_dict, indent=2)}\n")
    elif acquisition_output_dict and acquisition_output_dict.get("status","").startswith("error"):
        print("Content structuring skipped due to acquisition failure.\n")
        structuring_result_dict = {"status": "skipped_due_to_acquisition_error", "error_message": "Content acquisition failed."}
    else:
        print("Content structuring skipped (no text content reference from acquisition).\n")
        structuring_result_dict = {"status": "skipped_no_text", "error_message": "No text content to structure."}
        # If there was no text but there were images, the gallery should still be in processed_image_list_ref_final
        # The orchestration output aggregation will handle this.
        if processed_image_list_ref_final:
            # Manually create image blocks if structuring didn't run but we have images
            try:
                img_list = data_store_tool._run(action="get", key=processed_image_list_ref_final)
                if isinstance(img_list, list):
                    for img_data_dict in img_list:
                        pd_img_data = ProcessedImageData(**img_data_dict)
                        final_blocks_from_structuring.append(ContentBlock(
                            type="image", 
                            original_source_identifier=pd_img_data.original_source_identifier,
                            gcs_url=pd_img_data.gcs_url,
                            alt_text=pd_img_data.alt_text,
                            caption=pd_img_data.caption,
                            llm_description=pd_img_data.llm_description
                        ).model_dump())
            except Exception as e:
                print(f"Error creating manual gallery for no-text scenario: {e}")

    # Step 6: Orchestration - Error & Output Aggregation
    print("--- Step 6: Orchestration - Final Aggregation ---")
    error_aggregation_result = orchestration_agent.execute_error_aggregation(
        initial_input=orchestration_input,
        triage_results=triage_results,
        acquisition_output=acquisition_output_dict,
        image_processing_output=image_processing_result_dict,
        structuring_output=structuring_result_dict
    )
    print(f"Error Aggregation Result: {error_aggregation_result}\n")

    final_orchestration_output = orchestration_agent.execute_output_aggregation(
        initial_input=orchestration_input,
        error_aggregation_results=error_aggregation_result,
        extracted_title=extracted_title_from_acq,
        is_long_article_flag=is_long_article_from_structuring,
        final_original_content_blocks=final_blocks_from_structuring, # This is List[Dict]
        processed_image_data_list_ref=processed_image_list_ref_final
    )

    print(f"\n=== FINAL Core Reconstruction Output for: {source_identifier} ===")
    print(final_orchestration_output.model_dump_json(indent=2))
    print("=============================================================\n")

    # Optional: Print a summary of the data store for inspection
    # print("\n--- DataStore Contents (Summary) ---")
    # for key, value in data_store_dict.items():
    #     if isinstance(value, list) or isinstance(value, dict):
    #         print(f"Key: {key}, Type: {type(value)}, Length/Keys: {len(value)}")
    #     elif isinstance(value, str) and len(value) > 200:
    #         print(f"Key: {key}, Type: str, Length: {len(value)}, Snippet: {value[:100]}...")
    #     else:
    #         print(f"Key: {key}, Value: {value}")
    # print("---------------------------------")


if __name__ == "__main__":
    # --- Test Cases ---
    # Ensure test files are in the correct relative path from workspace root.
    # Workspace root is assumed to be one level above the `aiservice` directory.
    workspace_root_for_tests = Path(__file__).resolve().parent.parent.parent 
    test_file_dir_for_tests = workspace_root_for_tests / "documentation" / "AI Agents Testing File"

    test_scenarios = [
        # ("TXT File", "txt", str(test_file_dir_for_tests / "Test.txt"), "full_content"),
        # ("MD File", "md", str(test_file_dir_for_tests / "Product Requirement Document - Knowledge Card System v3.8.md"), "full_content"),
        # ("DOCX File", "docx", str(test_file_dir_for_tests / "Fulfillment Planning Deep Research Paper.docx"), "full_content"),
        ("PDF File - Airbnb Embedding", "pdf", str(test_file_dir_for_tests / "Embedding-Based Retrieval for Airbnb Search.pdf"), "full_content"),
        # ("URL - DeepLearning.AI Blog", "url", "https://www.deeplearning.ai/the-batch/issue-301/", "full_content"), 
        # ("URL - Airbnb Tech Blog", "url", "https://airbnb.tech/uncategorized/accelerating-large-scale-test-migration-with-llms/", "full_content"),
        # ("URL - Google Cloud Blog", "url", "https://cloud.google.com/blog/products/databases/techniques-for-improving-text-to-sql", "full_content"),
        # ("URL - Direct Image PNG", "url", "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png", "full_content"),
    ]

    # Ensure the test file directory exists if any file tests are active
    test_file_dir_for_tests.mkdir(parents=True, exist_ok=True)

    for name, s_type, s_id, proc_level in test_scenarios:
        # Check for local files if not a URL before running
        if s_type != "url" and not Path(s_id).exists():
            print(f"--- SKIPPING Local File Test Case: {name} ---")
            print(f"File not found: {s_id}")
            print(f"Ensure it's relative to: {workspace_root_for_tests} or an absolute path.")
            print("--------------------------------------------\n")
            continue
        run_crew_simulation(source_type=s_type, source_identifier=s_id, processing_level=proc_level)

    print("\n--- All Crew Simulations Attempted ---")

    # Add a helper in GenericFileContentAcquisitionAgent
    # def dispatch_file_processing(self, input_data: FileAcquisitionInput) -> FileAcquisitionOutput:
    #     if input_data.source_content_type == "docx":
    #         return self.execute_docx_processing(input_data)
    #     elif input_data.source_content_type == "txt":
    #         return self.execute_txt_processing(input_data)
    #     elif input_data.source_content_type == "md":
    #         return self.execute_markdown_processing(input_data)
    #     else:
    #         return FileAcquisitionOutput(
    #             status="unsupported_type_for_agent", 
    #             error_message=f"File type '{input_data.source_content_type}' not supported by this agent for dispatch."
    #         ) 