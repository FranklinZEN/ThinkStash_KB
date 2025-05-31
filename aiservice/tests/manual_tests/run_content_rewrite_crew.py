#!/usr/bin/env python
# coding: utf-8
"""
Manual test script for ContentRewriteCrew.

Allows for direct invocation of the crew with sample data to facilitate
testing, prompt engineering, and performance benchmarking.

Instructions:
1. Ensure your .env file in the `aiservice` directory is configured with
   GEMINI_API_KEY, GEMINI_TEXT_MODEL_COMPAT, and GEMINI_COMPATIBILITY_BASE_URL.
2. Run this script from the project root (e.g., ThinkStash/) using:
   python -m aiservice.tests.manual_tests.run_content_rewrite_crew
   (Adjust python executable if using a venv, e.g., aiservice/.venv/Scripts/python -m ...)
"""
import os
import sys
import time
import datetime
import uuid # Added for generating document_id
import json # Added for loading test data from JSON

# Ensure the aiservice module can be found
# This adjusts the path to include the parent directory of 'aiservice' if the script is run directly.
# For `python -m ...` invocation from root, this might not be strictly necessary
# but is good practice for script robustness.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from aiservice.app.crews.content_rewrite_crew import ContentRewriteCrewManager
from aiservice.app.models.insight_generation_models import RewriteContentInput
from aiservice.app.models.orchestration_models import ContentBlock
from aiservice.app.models.pipeline_models import DocumentMetadata
from aiservice.app.config.settings import settings # To verify settings load
from crewai import Task, Crew
from aiservice.app.agents.content_rewrite_agents import ContentRewriteAgents # To get the agent
from aiservice.app.config.llm_config import get_configured_llm, reset_llm_client # For direct LLM if needed for agent

JSON_INPUT_FILE_PATH = os.path.join(PROJECT_ROOT, "aiservice", "scripts", "e2e_test_output_https___www_deeplearning_ai_the_batch_when_to_fine.json")

def main():
    print("--- Initializing Manual Test for ContentRewriteCrew ---")
    # Load settings and display current LLM (already in your script)
    try:
        from aiservice.app.config.settings import settings
        # Reset and get a fresh LLM instance, which should now be Gemini
        reset_llm_client() 
        llm = get_configured_llm()
        print(f"LLM for test: {type(llm)}, Model: {llm.model_name if hasattr(llm, 'model_name') else (llm.model if hasattr(llm, 'model') else 'N/A')}")
        
        # Check for the correct API key setting based on our current strategy
        if settings.use_gemini_via_openai_compatibility:
            if not settings.gemini_api_key:
                print("Warning: GEMINI_API_KEY is not set in settings for compatibility mode!")
            else:
                print("GEMINI_API_KEY found in settings for compatibility mode.")
        elif settings.openai_api_key: # If checking for direct OpenAI
            if not settings.openai_api_key:
                 print("Warning: OPENAI_API_KEY is not set in settings for direct OpenAI mode!")
            else:
                print("OPENAI_API_KEY found in settings for direct OpenAI mode.")
        else:
            print("Warning: No primary API key (GEMINI_API_KEY or OPENAI_API_KEY) seems to be configured in settings.")

    except ImportError:
        print("Could not import settings. Ensure aiservice.app.config.settings is valid.")
        return
    except Exception as e:
        print(f"Error loading LLM or settings: {e}")
        return

    # --- Test ExpertSummarizerAgent with Gemini --- 
    print("\n--- Testing ExpertSummarizerAgent in Isolation ---")
    agents_factory = ContentRewriteAgents() # This will init agents with the new Gemini LLM config
    summarizer_agent = agents_factory.summarization_agent()

    sample_text_to_summarize = ("CrewAI is a framework for orchestrating role-playing, autonomous AI agents. "
                                "By defining agents with specific roles, goals, and tools, CrewAI enables them to collaborate on complex tasks. "
                                "This framework aims to simplify the development of sophisticated multi-agent AI systems.")

    test_summarizer_task = Task(
        description=f"Summarize the following text: '''{sample_text_to_summarize}'''",
        expected_output="A concise summary of the provided text, approximately 1-2 sentences.",
        agent=summarizer_agent
    )

    # Create a temporary crew for this isolated test
    isolated_summarizer_crew = Crew(
        agents=[summarizer_agent],
        tasks=[test_summarizer_task],
        verbose=True # Changed from 2 to True for boolean type
    )

    print("Kicking off isolated summarizer crew...")
    try:
        summary_result = isolated_summarizer_crew.kickoff()
        print("\n--- Isolated Summarizer Crew Result ---")
        print(summary_result)
        print(f"Usage Metrics: {isolated_summarizer_crew.usage_metrics}")

    except Exception as e:
        print(f"\n--- Isolated Summarizer Crew Error ---")
        import traceback
        traceback.print_exc()
        print(f"Error details: {e}")

    print("\n--- Isolated Summarizer Test Finished ---")

    # --- Full Crew Test using data from JSON file ---
    print("\n--- Preparing Input Data for Full Crew from JSON File ---")
    print(f"Loading data from: {JSON_INPUT_FILE_PATH}")

    try:
        with open(JSON_INPUT_FILE_PATH, 'r', encoding='utf-8') as f:
            e2e_data = json.load(f)
        
        raw_content_blocks = e2e_data.get("original_content_blocks", [])
        loaded_content_blocks = [ContentBlock(**block_data) for block_data in raw_content_blocks]
        
        raw_doc_metadata = e2e_data.get("document_metadata", {})
        # Ensure all required fields for DocumentMetadata are present or provide defaults
        # The DocumentMetadata model will raise errors if required fields are missing
        
        # Ensure document_id is present, generate if not (though it should be in e2e output)
        if not raw_doc_metadata.get("document_id"):
            raw_doc_metadata["document_id"] = str(uuid.uuid4())
            print(f"Generated missing document_id: {raw_doc_metadata['document_id']}")

        # Ensure user_id is present, generate a default if not
        if not raw_doc_metadata.get("user_id"):
            raw_doc_metadata["user_id"] = "test_user_manual_script_default" # Default user_id
            print(f"Added missing user_id with default: {raw_doc_metadata['user_id']}")

        # Example: 'extracted_at' needs to be datetime
        if 'extracted_at' in raw_doc_metadata and isinstance(raw_doc_metadata['extracted_at'], str):
            try:
                raw_doc_metadata['extracted_at'] = datetime.datetime.fromisoformat(raw_doc_metadata['extracted_at'].replace('Z', '+00:00')) # Handle Z for UTC
            except ValueError as ve:
                print(f"Warning: Could not parse 'extracted_at' string '{raw_doc_metadata['extracted_at']}'. Using current UTC time. Error: {ve}")
                raw_doc_metadata['extracted_at'] = datetime.datetime.now(datetime.timezone.utc)
        elif 'extracted_at' not in raw_doc_metadata:
             print(f"Warning: 'extracted_at' not found in document_metadata. Using current UTC time.")
             raw_doc_metadata['extracted_at'] = datetime.datetime.now(datetime.timezone.utc)

        loaded_doc_metadata = DocumentMetadata(**raw_doc_metadata)
        
        if not loaded_content_blocks:
            print("Warning: No content blocks loaded from JSON. Check the file and 'original_content_blocks' key.")
            # Potentially exit or use default sample data if this is critical
            # For now, we'll proceed, but the crew might not have much to do.

        rewrite_input_data = RewriteContentInput(
            content_blocks_to_rewrite=loaded_content_blocks,
            document_metadata=loaded_doc_metadata,
            original_content_blocks_json_string=json.dumps([block.model_dump(mode='json') for block in loaded_content_blocks]) if loaded_content_blocks else None,
            user_id=loaded_doc_metadata.user_id if loaded_doc_metadata else "test_user_json_fallback" # Pass user_id here too
        )
        print(f"Successfully loaded {len(loaded_content_blocks)} content blocks and document metadata.")

    except FileNotFoundError:
        print(f"Error: JSON input file not found at {JSON_INPUT_FILE_PATH}")
        print("Falling back to default sample data.")
        # Fallback to original sample data if JSON is not found
        sample_content_blocks = [
            ContentBlock(block_id="cb1", type="text", content="This is the first paragraph of a test document. It contains some initial thoughts."),
            ContentBlock(block_id="cb2", type="image", image_id_ref="img001", gcs_url="gs://example-bucket/images/img001.jpg", alt_text="A sample image.", caption="This is a sample image caption."),
            ContentBlock(block_id="cb3", type="text", content="This is a second paragraph, following the image. It expands on the ideas."),
            ContentBlock(block_id="cb4", type="list", items=["Point one", "Point two", "Point three"], ordered=False)
        ]
        sample_doc_metadata = DocumentMetadata(
            document_id=str(uuid.uuid4()),
            user_id="manual_test_user_fallback", # Added user_id here for the fallback
            source_type="manual_test_fallback",
            source_identifier="fallback_doc_001",
            extracted_at=datetime.datetime.now(datetime.timezone.utc)
            # Add other fields as necessary or let Pydantic use defaults/raise errors
        )
        rewrite_input_data = RewriteContentInput(
            content_blocks_to_rewrite=sample_content_blocks,
            document_metadata=sample_doc_metadata,
            original_content_blocks_json_string=json.dumps([block.model_dump(mode='json') for block in sample_content_blocks]),
            user_id=sample_doc_metadata.user_id
        )
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {JSON_INPUT_FILE_PATH}. Please ensure it's valid JSON.")
        print("Exiting test.")
        return
    except Exception as e: # Catch other Pydantic validation errors or unexpected issues
        print(f"Error processing JSON data or creating Pydantic models: {e}")
        import traceback
        traceback.print_exc()
        print("Exiting test.")
        return

    # --- Original Full Crew Test (Commented out for now) ---
    # print("\n--- Preparing Sample Input Data for Full Crew ---")
    # # Sample ContentBlocks
    # sample_content_blocks = [
    #     ContentBlock(block_id="cb1", type="text", content="This is the first paragraph of a test document. It contains some initial thoughts."),
    #     ContentBlock(block_id="cb2", type="image", image_id_ref="img001", gcs_url="gs://example-bucket/images/img001.jpg", alt_text="A sample image.", caption="This is a sample image caption."),
    #     ContentBlock(block_id="cb3", type="text", content="This is a second paragraph, following the image. It expands on the ideas."),
    #     ContentBlock(block_id="cb4", type="list", items=["Point one", "Point two", "Point three"], ordered=False)
    # ]

    # # Sample DocumentMetadata
    # sample_doc_metadata = DocumentMetadata(
    #     document_id=str(uuid.uuid4()), # Added document_id
    #     source_type="manual_test",
    #     source_identifier="test_doc_001",
    #     original_filename="test_document.txt",
    #     processed_at=datetime.datetime.now(datetime.timezone.utc),
    #     gcs_base_uri="gs://example-bucket/processed_docs/test_doc_001",
    #     original_title="My Test Document Title",
    #     detected_language="en"
    # )
    
    # rewrite_input_data = RewriteContentInput(
    #     content_blocks_to_rewrite=sample_content_blocks,
    #     document_metadata=sample_doc_metadata
    # )
    
    print("\n--- Initializing ContentRewriteCrewManager for Full Crew ---")
    crew_manager = ContentRewriteCrewManager(rewrite_input=rewrite_input_data)
    
    print("\n--- Running Full ContentRewriteCrew (this may take a few moments) ---")
    start_time = time.time()
    try:
        output = crew_manager.run()
        end_time = time.time()
        print(f"--- Full Crew Execution Finished in {end_time - start_time:.2f} seconds ---")
        print("\n--- Full Crew Output ---")
        if output:
            print(f"Type of output: {type(output)}")
            # Assuming output is a Pydantic model (e.g., RewriteContentOutput)
            # You might want to print its dict representation or specific fields
            if hasattr(output, 'model_dump_json'):
                print(output.model_dump_json(indent=2))
            else:
                print(output)
        else:
            print("Full crew returned no output.")
        
        # Access usage_metrics if the crew_manager.crew has it (might need to expose it)
        if hasattr(crew_manager, 'crew') and crew_manager.crew and hasattr(crew_manager.crew, 'usage_metrics'):
            print(f"Full Crew Usage Metrics: {crew_manager.crew.usage_metrics}")
        else:
            print("Full Crew usage metrics not available on crew_manager.crew")

    except Exception as e:
        print(f"\n--- Full Crew Execution Error ---")
        import traceback
        traceback.print_exc()
        print(f"Error details: {e}")

    print("\n--- Manual Test Script Finished ---")

if __name__ == "__main__":
    main() 