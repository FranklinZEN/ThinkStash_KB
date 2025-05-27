import os
# Set LITELLM_LOG environment variable for verbose logging from LiteLLM
os.environ['LITELLM_LOG'] = 'DEBUG'

from aiservice.app.crews.crews import CrewFactory
# from aiservice.app.config import initialize_env_vars # Removed
import litellm # Keep this for now, though set_verbose is deprecated
# litellm.set_verbose = True # Deprecated, replaced by env var

from crewai import Task # Ensure Task is imported if using it directly
    
def main():
        # Ensure environment variables are loaded (e.g., OPENAI_API_KEY)
        # If you have a specific function for this like in some projects:
        # initialize_env_vars() 
        # Otherwise, ensure your .env is loaded or keys are in the environment
    print("Loading .env (if any)...")
    from dotenv import load_dotenv
    load_dotenv() # Loads .env from the current working directory
    
    print("--- Initializing CrewFactory ---")
    factory = CrewFactory()
    # if not factory.default_llm: # This check is problematic and redundant with factory's own init logic
    #     print("LLM failed to initialize in CrewFactory. Exiting.")
    #     return

    # --- Define the URL and tasks (simplified from _get_url_task_sequence) ---
    url_to_test = "https://www.deeplearning.ai/the-batch/issue-301/"
    # url_to_test = "https://example.com/" # You can switch this for testing
    print(f"Target URL: {url_to_test}")

    # Get agents from factory
    orchestrator = factory.main_orchestrator
    web_acquirer = factory.web_url_acquirer
    image_agent = factory.image_processor 
    structuring_agent = factory.content_structurer
        
    tasks = []

    # Task 1: Initial Content Triage (Orchestrator)
    task_initial_triage = factory.orch_tasks_def.initial_content_triage_task(
        agent=orchestrator,
        source_type="url",
        source_identifier=url_to_test
    )
    tasks.append(task_initial_triage)

    # Task 2: HTTP Fetching (Web Acquirer)
    task_http_fetching = factory.web_tasks_def.http_fetching_task(
        agent=web_acquirer,
        normalized_url="{{task_initial_triage.output.normalized_identifier}}"
    )
    task_http_fetching.context = [task_initial_triage]
    tasks.append(task_http_fetching)

    # Task 3: Main Content Extraction (Web Acquirer)
    task_main_content_extraction = factory.web_tasks_def.main_content_extraction_task(
        agent=web_acquirer,
        raw_html_content="{{task_http_fetching.output.full_html_content}}", # Use the full HTML
        url="{{task_http_fetching.output.final_url}}" 
    )
    task_main_content_extraction.context = [task_http_fetching]
    tasks.append(task_main_content_extraction)

    # Task 4: Image Extraction (Web Acquirer)
    task_image_extraction = factory.web_tasks_def.image_extraction_contextualization_task(
        agent=web_acquirer,
        raw_html_content="{{task_http_fetching.output.full_html_content}}", # Use the full HTML
        base_url="{{task_http_fetching.output.final_url}}"
    )
    task_image_extraction.context = [task_http_fetching]
    tasks.append(task_image_extraction)

    # Task 5: Title Extraction (Web Acquirer)
    task_title_extraction = factory.web_tasks_def.title_extraction_task(
        agent=web_acquirer,
        raw_html_content="{{task_http_fetching.output.full_html_content}}" # Use the full HTML
    )
    task_title_extraction.context = [task_http_fetching]
    tasks.append(task_title_extraction)
    
    # Task 6: Paywall Detection (Web Acquirer)
    task_paywall_detection = factory.web_tasks_def.paywall_detection_task(
        agent=web_acquirer,
        url="{{task_http_fetching.output.final_url}}",
        raw_html_content="{{task_http_fetching.output.full_html_content}}", # Use the full HTML
        extracted_text_length="{{len(task_main_content_extraction.output) if task_main_content_extraction.output else -1}}" 
    )
    task_paywall_detection.context = [task_http_fetching, task_main_content_extraction]
    tasks.append(task_paywall_detection)

    # Task 7: LLM Driven Structuring (Structuring Agent)
    task_llm_structure = factory.struct_tasks_def.llm_driven_structuring_task(
        agent=structuring_agent,
        source_document_text="{{task_main_content_extraction.output}}",
        image_details_list="{{task_image_extraction.output}}", 
        source_content_type_hint="html_with_context"
    )
    task_llm_structure.context = [task_main_content_extraction, task_image_extraction, task_title_extraction, task_paywall_detection]
    tasks.append(task_llm_structure)
        
    print(f"--- Tasks Created ({len(tasks)}) for Full URL Workflow ---")
    for i, tsk in enumerate(tasks):
        print(f"Task {i+1}: {tsk.description[:150]}...")

    crew_inputs_for_kickoff = {
        "source_identifier": url_to_test
    }

    print("--- Creating CoreReconstructionCrew ---   ")
    core_crew = factory.create_core_reconstruction_crew() 
    core_crew.agents = [orchestrator, web_acquirer, image_agent, structuring_agent]
    core_crew.tasks = tasks
        
    print(f"--- Kicking off Full URL Workflow with {len(core_crew.tasks)} tasks ---   ")
    try:
        result = core_crew.kickoff(inputs=crew_inputs_for_kickoff)
        print("--- Crew Kickoff Finished ---")
        print("Result of the final task (task_llm_structure):")
        import json
        try:
            print(json.dumps(result, indent=2))
        except TypeError:
            print(result)

        # Print output of each task for inspection
        print("\n--- Individual Task Outputs ---")
        for i, tsk in enumerate(tasks):
            print(f"\nOutput of Task {i+1} ({tsk.description[:50]}...):")
            task_output = None
            if hasattr(tsk, 'output') and tsk.output:
                if hasattr(tsk.output, 'exported_output'):
                    task_output = tsk.output.exported_output
                elif hasattr(tsk.output, 'raw'):
                    task_output = tsk.output.raw
                else:
                    task_output = str(tsk.output)
                
                if isinstance(task_output, str):
                    try:
                        parsed_output = json.loads(task_output)
                        print(json.dumps(parsed_output, indent=2))
                    except json.JSONDecodeError:
                        print(task_output) # Print as is if not JSON
                else:
                    print(json.dumps(task_output, indent=2, default=str))
            else:
                print("No output or task not executed to completion with output.")

    except Exception as e:
        print(f"An error occurred during crew kickoff: {e}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        print("--- Crew kickoff interrupted by user ---")

if __name__ == "__main__":
    main()
