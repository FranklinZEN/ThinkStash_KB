import os
# Set LITELLM_LOG environment variable for verbose logging from LiteLLM
os.environ['LITELLM_LOG'] = 'DEBUG'

from aiservice.app.crews.crews import CrewFactory
# from aiservice.app.config import initialize_env_vars # Removed
import litellm # Keep this for now, though set_verbose is deprecated
# litellm.set_verbose = True # Deprecated, replaced by env var

from crewai import Task, Crew # Ensure Task and Crew are imported
import json
import uuid # No longer needed for this version
from aiservice.app.tools.utility_tools import DataStoreAccessTool # Import the new tool
    
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
    # url_to_test = "https://www.deeplearning.ai/the-batch/issue-301/"
    url_to_test = "https://cloud.google.com/blog/products/databases/techniques-for-improving-text-to-sql" # Changed to new test URL
    # url_to_test = "https://example.com/" # You can switch this for testing
    print(f"Target URL: {url_to_test}")

    # Get agents from factory
    orchestrator = factory.main_orchestrator
    web_acquirer = factory.web_url_acquirer
    image_agent = factory.image_processor 
    structuring_agent = factory.content_structurer
    
    data_store = {} # Initialize the shared data store for this run
    data_store_tool = DataStoreAccessTool(data_store=data_store) # Tool instance for this run

    # Add data_store_tool to the agents that need it for this run
    # This is a direct modification for testing; a more robust system might use dependency injection
    if data_store_tool not in web_acquirer.tools:
        web_acquirer.tools.append(data_store_tool)
    if data_store_tool not in structuring_agent.tools:
        structuring_agent.tools.append(data_store_tool)

    tasks = []

    # Task 1: Initial Content Triage (Orchestrator)
    task_initial_triage = factory.orch_tasks_def.initial_content_triage_task(
        agent=orchestrator,
        source_type="url",
        source_identifier=url_to_test
    )
    tasks.append(task_initial_triage)

    # Task 2: Comprehensive Web Processing (Web Acquirer)
    # This task now uses WebContentFetcherTool which includes paywall detection.
    task_comprehensive_web_processing = factory.web_tasks_def.comprehensive_url_processing_task(
        agent=web_acquirer,
        url_to_process="{{task_initial_triage.output.normalized_identifier}}" 
    )
    task_comprehensive_web_processing.context = [task_initial_triage] # Depends only on triage now
    tasks.append(task_comprehensive_web_processing)

    # --- Image Processing (Placeholder - to be implemented fully later) ---
    # For now, we assume task_comprehensive_web_processing.output.images contains image URLs.
    # We would then need tasks for: Image Downloading, GCS Upload, Metadata Consolidation.
    # Let's simulate that the images from task_comprehensive_web_processing are what goes to structuring.

    # Task 3: LLM Driven Structuring (Structuring Agent)
    # This task will now receive references to the text and image data, 
    # or nulls if the web processing step didn't yield them (e.g. due to paywall, error, or PDF).
    task_llm_structure = factory.struct_tasks_def.llm_driven_structuring_task(
        agent=structuring_agent,
        source_document_text_ref="{{task_comprehensive_web_processing.output.extracted_text_ref}}",
        image_details_list_ref="{{task_comprehensive_web_processing.output.images_ref}}", 
        source_content_type_hint="{{task_comprehensive_web_processing.output.status}}", # Pass status as hint
        page_title="{{task_comprehensive_web_processing.output.page_title}}"
    )
    task_llm_structure.context = [task_comprehensive_web_processing]
    tasks.append(task_llm_structure)
        
    print(f"--- Tasks Created ({len(tasks)}) for Data Referencing URL Workflow ---")
    for i, tsk in enumerate(tasks):
        print(f"Task {i+1}: {tsk.description[:150]}...")

    crew_inputs_for_kickoff = {
        # Inputs for the first task if its description uses them directly.
        # Task_initial_triage takes source_identifier from here.
        "source_identifier": url_to_test 
    }

    print("--- Creating CoreReconstructionCrew with Data Referencing Flow ---   ")
    # Pass the data_store into the crew's shared context
    core_crew = factory.create_core_reconstruction_crew(crew_input={"source_type":"url", "source_identifier": url_to_test})
    # It might be better to pass data_store via the kickoff inputs if tasks are to access it via context variables,
    # or ensure tools can access it if passed to their constructors (more complex setup).
    # For now, tools will need a way to access this data_store. 
    # A simple way is to make it a global or pass it around if tools are classes that can hold it.
    # Let's assume tools can access it via a shared mechanism for now (will refine tool code).
    # core_crew.context = {"data_store": data_store} # REMOVED THIS LINE

    core_crew.agents = [orchestrator, web_acquirer, image_agent, structuring_agent] # Ensure all agents are part of the crew
    core_crew.tasks = tasks 
        
    print(f"--- Kicking off Data Referencing URL Workflow with {len(core_crew.tasks)} tasks ---   ")
    try:
        final_result = core_crew.kickoff(inputs=crew_inputs_for_kickoff) # crew.context is now set
        print("--- Crew Kickoff Finished ---")
        print("Result of the final task (task_llm_structure):")
        try:
            print(json.dumps(final_result, indent=2))
        except TypeError:
            print(final_result)

        print("\n--- Shared Data Store Contents ---")
        # Need to handle potential non-serializable items in data_store if any tool stores complex objects
        # For now, assume text and list of image dicts are JSON serializable.
        serializable_data_store = {}
        for key, value in data_store.items():
            if isinstance(value, (str, list, dict, int, float, bool, type(None))):
                serializable_data_store[key] = value
            else:
                serializable_data_store[key] = f"<Data of type {type(value).__name__} not directly printable>"
        print(json.dumps(serializable_data_store, indent=2, default=str))

        print("\n--- Individual Task Outputs ---")
        for i, tsk in enumerate(tasks):
            print(f"\nOutput of Task {i+1} ({tsk.description[:50]}...):")
            task_output_data = None 
            if hasattr(tsk, 'output') and tsk.output:
                if hasattr(tsk.output, 'exported_output'):
                    task_output_data = tsk.output.exported_output
                elif hasattr(tsk.output, 'raw'):
                    task_output_data = tsk.output.raw
                else:
                    task_output_data = str(tsk.output)
                
                if isinstance(task_output_data, str):
                    try:
                        parsed_output = json.loads(task_output_data)
                        print(json.dumps(parsed_output, indent=2))
                    except json.JSONDecodeError:
                        print(task_output_data) 
                else:
                    print(json.dumps(task_output_data, indent=2, default=str))
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
