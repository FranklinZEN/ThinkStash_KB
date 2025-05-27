import pytest
import os
import json
from crewai import Task
from aiservice.app.crews.crews import CrewFactory
from aiservice.app import config

TEST_FILE_DIR = "documentation/AI Agents Testing File"
TEMP_TEST_OUTPUT_DIR = "temp_pytest_outputs"

@pytest.fixture(scope="module")
def crew_factory_instance():
    print("\n--- PyTest: Initializing CrewFactory for module ---")
    factory = CrewFactory()
    print("--- PyTest: CrewFactory Initialized ---")
    # Create the temp output dir if it doesn't exist for PDFToImageTool tests
    if not os.path.exists(TEMP_TEST_OUTPUT_DIR):
        os.makedirs(TEMP_TEST_OUTPUT_DIR)
    return factory

def _get_pdf_task_sequence(factory: CrewFactory, pdf_file_path: str) -> list[Task]:
    print(f"_get_pdf_task_sequence: Building tasks for {pdf_file_path}")
    # Ensure agents are accessed via the factory instance if they are instance attributes
    orchestrator = factory.main_orchestrator
    pdf_agent = factory.pdf_acquirer
    image_agent = factory.image_processor
    structuring_agent = factory.content_structurer

    tasks = []

    # Task 1: Initial Content Triage by Orchestrator
    task_initial_triage = factory.orch_tasks_def.initial_content_triage_task(
        agent=orchestrator,
        source_type="file", # For this PDF sequence
        source_identifier=pdf_file_path
    )
    tasks.append(task_initial_triage)

    # Subsequent tasks are now more directly chained after the triage.
    # We'll assume the triage output provides 'detected_content_type' and 'normalized_identifier'.
    # For this PDF-specific sequence, we are proceeding as if 'pdf' was detected.

    task_tiered_parsing = factory.pdf_tasks_def.tiered_pdf_parsing_task(
        agent=pdf_agent,
        # Assuming triage task output will be accessible, e.g. {{task_initial_triage.output.normalized_identifier}}
        # For now, pdf_file_path is directly used as it's known in this test sequence.
        pdf_file_path=pdf_file_path
    )
    # Tiered parsing depends on the initial triage identifying the content.
    task_tiered_parsing.context = [task_initial_triage]
    tasks.append(task_tiered_parsing)

    pdf_to_image_output_dir = os.path.join(TEMP_TEST_OUTPUT_DIR, os.path.basename(pdf_file_path) + "_images")
    os.makedirs(pdf_to_image_output_dir, exist_ok=True)

    task_pdf_to_image = factory.pdf_tasks_def.page_to_image_conversion_task(
        agent=pdf_agent, 
        pdf_file_path=pdf_file_path,
        output_folder=pdf_to_image_output_dir,
        page_numbers=[1] # For testing, let's assume we convert page 1
    )
    task_pdf_to_image.context = [task_tiered_parsing] # Typically after parsing, or in parallel
    tasks.append(task_pdf_to_image)

    # For task_image_marking, page_image_path comes from task_pdf_to_image.
    # page_text_content comes from task_tiered_parsing.
    task_image_marking = factory.pdf_tasks_def.multimodal_llm_image_marking_task(
        agent=pdf_agent,
        page_image_path="{{task_pdf_to_image.output[0].image_path}}",
        page_number=1, # Assuming we are processing page 1 from previous task
        page_text_content="{{task_tiered_parsing.output.parsed_text_content}}"
    )
    task_image_marking.context = [task_pdf_to_image, task_tiered_parsing]
    tasks.append(task_image_marking)

    task_gcs_upload = factory.img_proc_tasks_def.gcs_upload_task(
        agent=image_agent,
        image_data_list="{{task_image_marking.output}}", 
    )
    task_gcs_upload.context = [task_image_marking] # Correctly set as attribute
    tasks.append(task_gcs_upload)

    task_consolidate_metadata = factory.img_proc_tasks_def.metadata_consolidation_task(
        agent=image_agent,
        all_image_info_list="{{task_gcs_upload.output}}",
    )
    task_consolidate_metadata.context = [task_gcs_upload] # Correctly set as attribute
    tasks.append(task_consolidate_metadata)

    task_llm_structure = factory.struct_tasks_def.llm_driven_structuring_task(
        agent=structuring_agent,
        source_document_text="{{task_tiered_parsing.output.parsed_text_content}}", # Pass full output of parsing
        image_details_list="{{task_consolidate_metadata.output}}", 
        source_content_type_hint="pdf_multimodal"
    )
    task_llm_structure.context = [task_tiered_parsing, task_consolidate_metadata] # Correctly set as attribute
    tasks.append(task_llm_structure)

    print(f"_get_pdf_task_sequence: Total tasks built: {len(tasks)}")
    return tasks

def _get_url_task_sequence(factory: CrewFactory, url: str) -> list[Task]:
    print(f"_get_url_task_sequence: Building tasks for {url}")
    orchestrator = factory.main_orchestrator
    web_acquirer = factory.web_url_acquirer 
    # image_agent = factory.image_processor # To be used later if we download & GCS upload URL images
    structuring_agent = factory.content_structurer

    tasks = []

    # Task 1: Initial Content Triage (already added)
    task_initial_triage = factory.orch_tasks_def.initial_content_triage_task(
        agent=orchestrator,
        source_type="url",
        source_identifier=url
    )
    tasks.append(task_initial_triage)

    # Task 2: HTTP Fetching (depends on triage for normalized_url)
    # Assuming triage output is {{task_initial_triage.output.normalized_identifier}}
    task_http_fetching = factory.web_tasks_def.http_fetching_task(
        agent=web_acquirer,
        normalized_url="{{task_initial_triage.output.normalized_identifier}}"
    )
    task_http_fetching.context = [task_initial_triage]
    tasks.append(task_http_fetching)

    # Task 3: Main Content Extraction (depends on fetched HTML)
    task_main_content_extraction = factory.web_tasks_def.main_content_extraction_task(
        agent=web_acquirer,
        raw_html_content="{{task_http_fetching.output.full_html_content}}",
        url="{{task_http_fetching.output.final_url}}" 
    )
    task_main_content_extraction.context = [task_http_fetching]
    tasks.append(task_main_content_extraction)

    # Task 4: Image Extraction (depends on fetched HTML and final URL as base)
    task_image_extraction = factory.web_tasks_def.image_extraction_contextualization_task(
        agent=web_acquirer,
        raw_html_content="{{task_http_fetching.output.full_html_content}}",
        base_url="{{task_http_fetching.output.final_url}}"
    )
    task_image_extraction.context = [task_http_fetching]
    tasks.append(task_image_extraction)

    # Task 5: Title Extraction (depends on fetched HTML)
    task_title_extraction = factory.web_tasks_def.title_extraction_task(
        agent=web_acquirer,
        raw_html_content="{{task_http_fetching.output.full_html_content}}"
    )
    task_title_extraction.context = [task_http_fetching]
    tasks.append(task_title_extraction)
    
    # Task 6: Paywall Detection (optional, can run in parallel or on fetched HTML)
    task_paywall_detection = factory.web_tasks_def.paywall_detection_task(
        agent=web_acquirer,
        url="{{task_http_fetching.output.final_url}}",
        raw_html_content="{{task_http_fetching.output.full_html_content}}"
    )
    task_paywall_detection.context = [task_http_fetching]
    tasks.append(task_paywall_detection)

    # Task 7: Package Web Output (gathers all from web_acquirer)
    # This task's expected_output is a dictionary. 
    # The llm_driven_structuring_task expects image_details_list to be a list directly.
    # So, we might need an intermediate step or adjust how llm_driven_structuring_task gets its image list for URLs.
    # For now, let's assume the llm_driven_structuring_task can handle the output of image_extraction directly.

    # Task 8: LLM Driven Structuring
    # For URLs, image_details_list will come from task_image_extraction.output
    # These images are URLs, not GCS paths yet. The structuring agent/tool needs to handle this.
    task_llm_structure = factory.struct_tasks_def.llm_driven_structuring_task(
        agent=structuring_agent,
        source_document_text="{{task_main_content_extraction.output}}",
        image_details_list="{{task_image_extraction.output}}", # This list contains image URLs, alt text, etc.
        source_content_type_hint="html_with_context"
    )
    task_llm_structure.context = [task_main_content_extraction, task_image_extraction, task_title_extraction, task_paywall_detection]
    tasks.append(task_llm_structure)

    print(f"_get_url_task_sequence: Total tasks built: {len(tasks)}")
    return tasks

def test_pdf_reconstruction_flow(crew_factory_instance: CrewFactory):
    print("\n--- PyTest: Starting test_pdf_reconstruction_flow ---")
    
    # Create a crew instance. The create_core_reconstruction_crew method itself 
    # will now set up initial validation and detection tasks if inputs are provided to it.
    # For a full flow test, we will override the tasks later.
    pdf_file_name = "When Grades Matter More Than Learning, AI Wins.pdf"
    pdf_file_path = os.path.join(TEST_FILE_DIR, pdf_file_name)
    assert os.path.exists(pdf_file_path), f"Test PDF file not found: {pdf_file_path}"

    crew_inputs_for_kickoff = {
        "source_type": "file",
        "source_identifier": pdf_file_path
    }
    
    # Create the crew with initial validation/detection tasks based on input to create_core_reconstruction_crew
    # The `create_core_reconstruction_crew` method already sets up the first two tasks
    # if crew_input (its parameter) has source_type and source_identifier.
    # The `crew_inputs_for_kickoff` is for the `kickoff` method.
    core_crew = crew_factory_instance.create_core_reconstruction_crew(crew_input=crew_inputs_for_kickoff)
    assert core_crew is not None, "Crew creation failed"
    
    print("--- PyTest: Overriding tasks with full PDF sequence for test_pdf_reconstruction_flow ---")
    pdf_tasks_full_sequence = _get_pdf_task_sequence(crew_factory_instance, pdf_file_path)
    core_crew.tasks = pdf_tasks_full_sequence
    
    print(f"--- PyTest: Kicking off CoreReconstructionCrew for PDF: {pdf_file_name} with {len(core_crew.tasks)} tasks ---")
    result = core_crew.kickoff(inputs=crew_inputs_for_kickoff) 
    print(f"--- PyTest: CoreReconstructionCrew kickoff finished. Result: ---")
    
    try:
        if isinstance(result, (dict, list)):
            print(json.dumps(result, indent=2, default=str)) 
        else:
            print(result)
    except TypeError:
        print(result) 

    assert result is not None
    print("--- PyTest: test_pdf_reconstruction_flow COMPLETED ---")

#@pytest.mark.skip(reason="URL flow not fully implemented or focus is on PDF now")
def test_url_reconstruction_flow(crew_factory_instance: CrewFactory):
    print("\n--- PyTest: Starting test_url_reconstruction_flow ---")
    url_to_test = "https://www.deeplearning.ai/the-batch/issue-301/"
    crew_inputs_for_kickoff = {
        "source_type": "url",
        "source_identifier": url_to_test
    }
    # The create_core_reconstruction_crew method sets up the initial triage task.
    core_crew = crew_factory_instance.create_core_reconstruction_crew(crew_input=crew_inputs_for_kickoff)
    assert core_crew is not None, "Crew creation failed"

    print("--- PyTest: Overriding tasks with full URL sequence for test_url_reconstruction_flow ---")
    url_tasks_full_sequence = _get_url_task_sequence(crew_factory_instance, url_to_test)
    core_crew.tasks = url_tasks_full_sequence
    
    print(f"--- PyTest: Kicking off CoreReconstructionCrew for URL: {url_to_test} with {len(core_crew.tasks)} tasks ---")
    result = core_crew.kickoff(inputs=crew_inputs_for_kickoff)
    print(f"--- PyTest: CoreReconstructionCrew kickoff finished for URL. Result: ---")
    try:
        if isinstance(result, (dict, list)):
            print(json.dumps(result, indent=2, default=str))
        else:
            print(result)
    except TypeError:
        print(result)
    assert result is not None
    print("--- PyTest: test_url_reconstruction_flow COMPLETED ---")

# A simpler test to just check tool execution directly if needed (outside of crew)
@pytest.mark.skip(reason="Focusing on crew tests for now")
def test_pdf_miner_tool_direct(crew_factory_instance: CrewFactory):
    print("\n--- PyTest: Starting test_pdf_miner_tool_direct ---")
    pdf_file_name = "a-data-leaders-technical-guide-to-scaling-gen-ai.pdf"
    pdf_file_path = os.path.join(TEST_FILE_DIR, pdf_file_name)
    assert os.path.exists(pdf_file_path), f"Test PDF file not found: {pdf_file_path}"

    # Accessing pdfminer_tool, ensure it's initialized in CrewFactory if this test is unskipped
    if hasattr(crew_factory_instance, 'pdfminer_tool'):
        pdfminer_tool = crew_factory_instance.pdfminer_tool
        print(f"--- PyTest: Running PDFMinerSixParserTool directly for {pdf_file_name} ---")
        text_content = pdfminer_tool._run(file_path=pdf_file_path)
        print(f"--- PyTest: PDFMinerSixParserTool direct run finished. ---")
        assert text_content is not None
        assert "Error:" not in text_content
        assert len(text_content) > 100 # Expect some reasonable amount of text
        print(f"Extracted text length: {len(text_content)}")
    else:
        print("--- PyTest: pdfminer_tool not found on crew_factory_instance, skipping direct run ---")
        pytest.skip("pdfminer_tool not available on factory")
    print("--- PyTest: test_pdf_miner_tool_direct COMPLETED ---")

# To run this test file: pytest -vs aiservice/tests/crews/test_core_reconstruction_crew.py
# To run a specific test: pytest -vs aiservice/tests/crews/test_core_reconstruction_crew.py::test_pdf_reconstruction_flow 