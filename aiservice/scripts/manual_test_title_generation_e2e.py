'''
End-to-End tests for the GeneralPurposeTitleGenerationCrew.
These tests will involve actual LLM calls.
'''
import pytest
import json
import os
from typing import List

from aiservice.app.models.orchestration_models import ContentBlock
from aiservice.app.crews.title_generation_crew import GeneralPurposeTitleGenerationCrew

# The path to the JSON file will now be determined by a command-line option

@pytest.fixture
def e2e_content_blocks(request) -> List[ContentBlock]:
    '''Loads content blocks from the E2E test JSON file specified by --e2e-json-file command-line option.'''
    scripts_dir = os.path.dirname(__file__)
    debug_log_path = os.path.join(scripts_dir, "e2e_debug.log")

    with open(debug_log_path, "w", encoding="utf-8") as debug_f:
        json_file_name = request.config.getoption("--e2e-json-file")
        debug_f.write(f"[DEBUG] pytest_addoption --e2e-json-file: {json_file_name}\n")
        
        if not json_file_name:
            debug_f.write("[DEBUG] Skipping: No JSON file name provided.\n")
            pytest.skip("E2E test skipped: No JSON file specified. Use --e2e-json-file <filename.json>")

        data_file_path = os.path.join(scripts_dir, json_file_name)
        debug_f.write(f"[DEBUG] Constructed data_file_path: {data_file_path}\n")
        
        file_exists = os.path.exists(data_file_path)
        debug_f.write(f"[DEBUG] Does data_file_path exist? {file_exists}\n")

        if not file_exists:
            debug_f.write(f"[DEBUG] Skipping: File not found at {data_file_path}.\n")
            pytest.skip(f"E2E data file not found: {data_file_path}. Ensure it is in the aiservice/scripts/ directory.")

        debug_f.write(f"[DEBUG] Attempting to open and read: {data_file_path}\n")
        try:
            with open(data_file_path, 'r', encoding='utf-8') as f_data:
                orchestration_output = json.load(f_data)
            debug_f.write(f"[DEBUG] Successfully loaded JSON from {data_file_path}\n")
        except json.JSONDecodeError as e:
            debug_f.write(f"[DEBUG] Failed to parse JSON from {data_file_path}: {e}\n")
            pytest.fail(f"Failed to parse JSON file {data_file_path}: {e}")
        except Exception as e:
            debug_f.write(f"[DEBUG] Other error opening/reading {data_file_path}: {e}\n")
            pytest.fail(f"Error reading file {data_file_path}: {e}")
        
        raw_blocks = orchestration_output.get("original_content_blocks", [])
        debug_f.write(f"[DEBUG] Found {len(raw_blocks)} raw blocks in JSON (using key 'original_content_blocks').\n")
        parsed_blocks: List[ContentBlock] = []
        for i, block_data in enumerate(raw_blocks):
            try:
                parsed_blocks.append(ContentBlock(**block_data))
            except Exception as e:
                debug_f.write(f"[DEBUG] Warning: Skipping block {i} due to parsing error: {e}. Block data: {block_data}\n")
                continue
        
        debug_f.write(f"[DEBUG] Successfully parsed {len(parsed_blocks)} blocks.\n")
        if not parsed_blocks and raw_blocks: # Only skip if raw_blocks existed but none parsed
            debug_f.write(f"[DEBUG] Skipping: No content blocks successfully parsed from {data_file_path} though raw blocks were present.\n")
            pytest.skip(f"No content blocks were successfully parsed from the E2E data file: {data_file_path}")
        elif not raw_blocks: # If the content_blocks array itself was empty or missing
             debug_f.write(f"[DEBUG] Skipping: content_blocks array was empty or missing in {data_file_path}.\n")
             pytest.skip(f"The 'content_blocks' array was empty or missing in the E2E data file: {data_file_path}")
            
    return parsed_blocks

@pytest.mark.e2e
def test_e2e_title_generation_with_json_file(e2e_content_blocks: List[ContentBlock], request):
    '''
    Tests the full title generation flow using content blocks from a JSON file
    and a real LLM call.
    '''
    json_file_name = request.config.getoption("--e2e-json-file") # For logging purposes
    print(f"Starting E2E title generation test for file: {json_file_name}")
    print(f"Loaded {len(e2e_content_blocks)} content blocks.")
    
    # The user_id is handled by TitleGenerationAgents if needed.
    # The crew's __init__ now takes an optional request_model, which we are not using here.
    title_crew = GeneralPurposeTitleGenerationCrew()
    
    print("Running GeneralPurposeTitleGenerationCrew for E2E test...")
    # The run method expects a list of dictionaries, not ContentBlock objects directly.
    # Convert ContentBlock objects to dictionaries using model_dump() for Pydantic v2.
    # The argument name in the run method is content_block_dicts.
    generated_title_output = title_crew.run(content_block_dicts=[block.model_dump() for block in e2e_content_blocks])
    
    print(f"Raw generated title from crew: \"{generated_title_output.suggested_title}\"")
    
    generated_title = generated_title_output.suggested_title # Extract the string

    assert generated_title is not None, "Generated title should not be None"
    assert isinstance(generated_title, str), "Generated title should be a string"
    
    # Temporarily expect the specific error message, since the tool call is still failing
    # expected_error_message = "Error: No content available for title generation."
    # assert generated_title == expected_error_message, \
    #     f"Expected error message '{expected_error_message}', but got '{generated_title}'"
    
    # Comment out original assertions for when a real title is expected
    assert "Error:" not in generated_title, f"Title generation should not result in an error string: {generated_title}"
    assert len(generated_title.strip()) > 0, "Generated title should not be empty"

    print(f"\n==> E2E Test Suggested Title for {json_file_name}: {generated_title}\n")

    # Example of a more specific assertion if you know the expected topic of the E2E data
    # For instance, if the e2e data is about "AI in Healthcare":
    # expected_keywords = ["ai", "healthcare", "medical"]
    # expected_keywords = ["uber", "blog", "session"] # Example for the Uber blog
    # assert any(keyword in generated_title.lower() for keyword in expected_keywords), \
    #     f"Generated title \"{generated_title}\" does not seem related to the expected topic." 