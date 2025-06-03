import pytest
from unittest.mock import patch, MagicMock
import uuid
import json
import os
import logging
import sys

from aiservice.app.crews.title_generation_crew import GeneralPurposeTitleGenerationCrew, TitleOutput
from aiservice.app.models.orchestration_models import ContentBlock
from aiservice.app.agents.title_generation_agents import TitleGenerationAgents
from crewai import Agent

# Helper to create ContentBlock instances
def create_content_block(block_type: str, content: str = None, items: list = None, user_id: str = "test_user_crew", document_id: str = "doc_crew_test") -> ContentBlock:
    return ContentBlock(
        block_id=str(uuid.uuid4()),
        tmp_id=str(uuid.uuid4()),
        user_id=user_id,
        document_id=document_id,
        type=block_type,
        content=content,
        items=items,
        order_index=0
    )

@pytest.fixture
def sample_content_blocks() -> list[ContentBlock]:
    return [
        create_content_block(block_type="heading", content="Sample Title"),
        create_content_block(block_type="text", content="This is sample text for testing title generation.")
    ]

@pytest.fixture
def title_crew() -> GeneralPurposeTitleGenerationCrew:
    # Mock the TitleGenerationAgents to control agent creation within the crew
    with patch('aiservice.app.crews.title_generation_crew.TitleGenerationAgents') as mock_agents_factory_class:
        mock_agents_factory_instance = MagicMock(spec=TitleGenerationAgents)

        # Configure the mock_agent to behave more like an object CrewAI expects
        # Using spec=Agent helps ensure it has the basic structure of a CrewAI Agent.
        mock_agent = MagicMock(spec=Agent) 
        
        # Mock the .get() method that CrewAI's Task initialization/processing seems to call
        # This is to satisfy `values.get("config", {})` in CrewAI's `process_config`
        def mock_get_method(key, default=None):
            if key == "config":
                return {}  # Return an empty dict for agent config
            # Add other key handlings if needed for other parts of CrewAI
            return default
        
        mock_agent.get = MagicMock(side_effect=mock_get_method)

        # Ensure essential attributes that might be accessed by Task or Crew are present
        # spec=Agent might cover some, but being explicit can help.
        mock_agent.role = "Mocked Expert Title Crafter"
        mock_agent.goal = "Mocked: Analyze content and generate a title."
        mock_agent.backstory = "Mocked: A diligent agent for testing."
        mock_agent.tools = [] # Task might check tools
        mock_agent.llm = MagicMock() # Task will likely require an LLM on the agent
        mock_agent.verbose = False
        mock_agent.allow_delegation = False
        mock_agent.memory = False
        mock_agent.max_rpm = None  # Add max_rpm attribute
        mock_agent._rpm_controller = None # Add _rpm_controller attribute
        mock_agent._token_process = None # Add _token_process attribute
        mock_agent.security_config = None # Add security_config attribute
        # If CrewAI's Task checks for specific tool names or capabilities,
        # those would need to be mocked on mock_agent.tools as well.
        # For now, an empty list of tools might suffice if the task logic itself isn't tool-dependent in this unit test.
        # The task description in GeneralPurposeTitleGenerationCrew does mention tools.
        # Let's provide mock tools similar to what the real agent has.
        mock_full_text_extractor = MagicMock()
        mock_full_text_extractor.name = "FullTextContentExtractorTool"
        mock_optimized_llm_tool = MagicMock()
        mock_optimized_llm_tool.name = "OptimizedLLMInteractionTool"
        mock_agent.tools = [mock_full_text_extractor, mock_optimized_llm_tool]


        mock_agents_factory_instance.title_crafting_agent.return_value = mock_agent
        mock_agents_factory_class.return_value = mock_agents_factory_instance
        
        crew = GeneralPurposeTitleGenerationCrew(user_id="test_crew_user")
        return crew

@pytest.fixture
def e2e_content_blocks_data() -> list[dict]:
    """Provides the raw original_content_blocks data from the E2E JSON file."""
    # This JSON string is a condensed version of the original_content_blocks part of the e2e test output file.
    # In a real scenario, you might load this from the file directly.
    # For brevity and to avoid large string literals, this is a placeholder.
    # The actual content blocks from the file will be used in the test.
    json_data_str = '''
    [
        {
            "block_id": "f1bfb757-2482-49b8-b7cc-63e528c519d2", "tmp_id": "e2e_job_7af73473_p1_b0", "user_id": "test_google_images_v15",
            "document_id": "e2e_job_7af73473", "type": "heading", "order_index": 0,
            "content": "Benchmarking Intelligent Fulfillment Capacity Planning:  Strategies from Industry Leaders",
            "page_number": 1, "level": 2
        },
        {
            "block_id": "c979ea63-39f2-47fa-a8be-99339208146f", "tmp_id": "e2e_job_7af73473_p1_b1", "user_id": "test_google_images_v15",
            "document_id": "e2e_job_7af73473", "type": "heading", "order_index": 1,
            "content": "1. Executive Summary", "page_number": 1, "level": 2
        },
        {
            "block_id": "a89b5a7b-574a-4b56-9ea4-a9b9489ffff4", "tmp_id": "e2e_job_7af73473_p1_b2", "user_id": "test_google_images_v15",
            "document_id": "e2e_job_7af73473", "type": "text", "order_index": 2,
            "content": "This report analyzes the strategies and technologies employed by leading companies...",
            "page_number": 1
        }
    ]
    ''' # This is a truncated example. The actual test will load the full data.
    # Load the actual JSON data from the file path used in the previous step by the assistant
    e2e_file_path = os.path.join(os.path.dirname(__file__), "e2e_test_output_E__ThinkStash_documentation_AI_Agents_Testing_File.json")
    with open(e2e_file_path, 'r', encoding='utf-8') as f:
        full_e2e_data = json.load(f)
    return full_e2e_data["original_content_blocks"]

@pytest.fixture
def e2e_parsed_content_blocks(e2e_content_blocks_data: list[dict]) -> list[ContentBlock]:
    """Parses raw E2E content block data into ContentBlock Pydantic models."""
    # Fill missing optional fields with None or default values as per ContentBlock model
    # to prevent Pydantic validation errors if they are not present in the JSON.
    parsed_blocks = []
    for block_data in e2e_content_blocks_data:
        # Ensure all fields expected by ContentBlock are present, providing defaults for optionals if missing
        # This is crucial because ContentBlock model expects certain fields.
        # From orchestration_models.py, ContentBlock has many Optional fields.
        # We need to ensure that if a key is missing in block_data, we pass None or a sensible default.
        # A safer way is to pass **block_data and let Pydantic handle it,
        # but only if all keys in block_data match ContentBlock fields and optionals are handled by model defaults.
        # For robustness, explicitly map and provide defaults for optional fields not in the JSON.
        
        # Create a complete dict for ContentBlock instantiation
        # This ensures all fields required by Pydantic model are considered.
        # Fields in ContentBlock: block_id, tmp_id, user_id, document_id, type, order_index,
        # content, page_number, bbox, level, language, items, ordered, list_start_number,
        # image_id_ref, gcs_url, alt_text, caption, llm_description, width, height.

        # Start with all None to handle missing optional fields gracefully.
        complete_block_data = {
            "block_id": None, "tmp_id": None, "user_id": None, "document_id": None,
            "type": None, "order_index": None, "content": None, "page_number": None,
            "bbox": None, "level": None, "language": None, "items": None,
            "ordered": None, "list_start_number": None, "image_id_ref": None,
            "gcs_url": None, "alt_text": None, "caption": None,
            "llm_description": None, "width": None, "height": None
        }
        # Update with actual data from the JSON block
        complete_block_data.update(block_data)
        
        # Some specific handling if types are mismatched or missing and critical
        if not complete_block_data.get("block_id"):
            complete_block_data["block_id"] = str(uuid.uuid4()) # Generate if missing
        if not complete_block_data.get("user_id"):
            complete_block_data["user_id"] = "e2e_test_user" # Default if missing
        if not complete_block_data.get("document_id"):
            complete_block_data["document_id"] = "e2e_test_doc" # Default if missing

        parsed_blocks.append(ContentBlock(**complete_block_data))
    return parsed_blocks

@patch('crewai.Crew.kickoff') # Mock the kickoff method of the CrewAI Crew class
def test_title_crew_run_success(mock_crew_kickoff, title_crew: GeneralPurposeTitleGenerationCrew, sample_content_blocks: list[ContentBlock]):
    """Test the run method of GeneralPurposeTitleGenerationCrew for a successful case."""
    expected_title = "Mocked Generated Title"
    # Configure the mock_crew_kickoff to return a TitleOutput object
    mock_crew_kickoff.return_value = TitleOutput(generated_title=expected_title)

    result_title = title_crew.run(content_blocks=sample_content_blocks)

    # Assert that crew.kickoff was called once
    mock_crew_kickoff.assert_called_once()
    
    # Get the actual arguments passed to kickoff
    kickoff_args = mock_crew_kickoff.call_args[1] # kwargs is at index 1 for call_args
    assert 'content_blocks' in kickoff_args['inputs']
    assert kickoff_args['inputs']['content_blocks'] == sample_content_blocks
    
    assert result_title == expected_title

@patch('crewai.Crew.kickoff')
def test_title_crew_run_returns_error_string_on_failure(mock_crew_kickoff, title_crew: GeneralPurposeTitleGenerationCrew, sample_content_blocks: list[ContentBlock]):
    """Test that the crew's run method returns a string indicating error if kickoff returns unexpected data."""
    mock_crew_kickoff.return_value = {"some_other_key": "some_value"} # Not TitleOutput

    result_title = title_crew.run(content_blocks=sample_content_blocks)
    assert "Error: Title generation failed" in result_title

@patch('crewai.Crew.kickoff')
def test_title_crew_run_handles_direct_string_output(mock_crew_kickoff, title_crew: GeneralPurposeTitleGenerationCrew, sample_content_blocks: list[ContentBlock]):
    """Test the run method when kickoff directly returns a string (e.g. older CrewAI or simple task)."""
    expected_title = "Direct String Title"
    mock_crew_kickoff.return_value = expected_title
    
    result_title = title_crew.run(content_blocks=sample_content_blocks)
    assert result_title == expected_title

@patch('crewai.Crew.kickoff')
def test_title_crew_run_handles_raw_output_string(mock_crew_kickoff, title_crew: GeneralPurposeTitleGenerationCrew, sample_content_blocks: list[ContentBlock]):
    """Test the run method when kickoff returns an object with raw_output string."""
    expected_title = "Title from Raw Output"
    mock_result_object = MagicMock()
    mock_result_object.raw_output = expected_title
    # Make it not an instance of TitleOutput
    mock_result_object.__class__ = MagicMock # So isinstance(result, TitleOutput) is False
    mock_crew_kickoff.return_value = mock_result_object
    
    result_title = title_crew.run(content_blocks=sample_content_blocks)
    assert result_title == expected_title

@patch('crewai.Crew.kickoff')
def test_title_crew_run_with_e2e_data(mock_crew_kickoff, title_crew: GeneralPurposeTitleGenerationCrew, e2e_parsed_content_blocks: list[ContentBlock]):
    """Test the run method with content blocks loaded from the E2E JSON test file."""
    expected_title = "E2E Data Mocked Title"
    mock_crew_kickoff.return_value = TitleOutput(generated_title=expected_title)

    # Ensure the fixture provides some blocks
    assert e2e_parsed_content_blocks is not None
    assert len(e2e_parsed_content_blocks) > 0 

    result_title = title_crew.run(content_blocks=e2e_parsed_content_blocks)

    mock_crew_kickoff.assert_called_once()
    kickoff_args = mock_crew_kickoff.call_args[1]
    assert 'content_blocks' in kickoff_args['inputs']
    
    # Deep comparison of list of Pydantic models can be tricky if not perfectly identical in all fields (including defaults not in JSON)
    # For this unit test, ensuring the correct list object was passed is often sufficient,
    # assuming ContentBlock instantiation in the fixture is correct.
    assert kickoff_args['inputs']['content_blocks'] == e2e_parsed_content_blocks 
    
    assert result_title == expected_title

# To run these tests:
# Ensure PYTHONPATH is set up if needed, e.g., export PYTHONPATH=${PYTHONPATH}:${PWD}
# Then run: pytest aiservice/scripts/test_title_generation_crew.py

# If you want to run these tests in a specific directory, you can use the following command:
# pytest aiservice/scripts/test_title_generation_crew.py --directory=/path/to/your/directory

# If you want to run these tests with a specific pytest configuration, you can use the following command:
# pytest aiservice/scripts/test_title_generation_crew.py --config=your_config_file.ini

# If you want to run these tests with a specific pytest marker, you can use the following command:
# pytest aiservice/scripts/test_title_generation_crew.py --markers="slow"

# If you want to run these tests with a specific pytest filter, you can use the following command:
# pytest aiservice/scripts/test_title_generation_crew.py --filter="test_title_crew_run_success"

# If you want to run these tests with a specific pytest exclude, you can use the following command:
# pytest aiservice/scripts/test_title_generation_crew.py --exclude="test_title_crew_run_success" 