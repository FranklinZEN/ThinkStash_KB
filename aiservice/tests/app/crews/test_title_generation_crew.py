import pytest
from unittest.mock import patch, MagicMock
import uuid
import sys
import os

# Adjust sys.path to include the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from aiservice.app.crews.title_generation_crew import GeneralPurposeTitleGenerationCrew
from aiservice.app.models.task_output_models import TitleGenerationOutput
from aiservice.app.models.orchestration_models import ContentBlock
from aiservice.app.agents.title_generation_agents import TitleGenerationAgents
from crewai import Agent

@pytest.fixture
def sample_content_blocks_as_dicts() -> list[dict]:
    """Provides a list of content blocks as dictionaries, including all required fields."""
    return [
        {
            "block_id": "b1", "type": "heading", "content": "Sample Title", 
            "user_id": "test_user", "document_id": "test_doc", "order_index": 0
        },
        {
            "block_id": "b2", "type": "text", "content": "This is sample text for testing title generation.", 
            "user_id": "test_user", "document_id": "test_doc", "order_index": 1
        }
    ]

@pytest.fixture
def title_crew() -> GeneralPurposeTitleGenerationCrew:
    """Mocks the dependencies for GeneralPurposeTitleGenerationCrew and returns an instance."""
    with patch('aiservice.app.crews.title_generation_crew.TitleGenerationAgents') as mock_agents_factory_class:
        mock_agents_factory_instance = MagicMock(spec=TitleGenerationAgents)
        mock_agent = MagicMock(spec=Agent)
        
        # Mocking the agent's attributes to satisfy CrewAI's internal checks
        mock_agent.role = "Mocked Expert Title Crafter"
        mock_agent.goal = "Mocked Goal"
        mock_agent.backstory = "Mocked Backstory"
        mock_agent.tools = []
        mock_agent.llm = MagicMock()
        mock_agent.verbose = False
        mock_agent.allow_delegation = False
        mock_agent.memory = False
        mock_agent.max_rpm = None
        mock_agent.cache = None
        mock_agent._token_process = MagicMock()
        # Add the newly required attribute from the latest traceback
        mock_agent.security_config = None


        mock_agents_factory_instance.title_crafting_agent.return_value = mock_agent
        mock_agents_factory_class.return_value = mock_agents_factory_instance
        
        crew_instance = GeneralPurposeTitleGenerationCrew()
        # This is crucial: we replace the real agents factory with our mock
        crew_instance.agents_factory = mock_agents_factory_class.return_value
        yield crew_instance

@patch('crewai.Crew.kickoff')
def test_title_crew_run_success(mock_crew_kickoff, title_crew: GeneralPurposeTitleGenerationCrew, sample_content_blocks_as_dicts: list[dict]):
    """Test the run method for a successful title generation."""
    expected_title = "Mocked Generated Title"
    mock_crew_kickoff.return_value = TitleGenerationOutput(suggested_title=expected_title)

    # Call the run method with dictionaries
    result = title_crew.run(content_block_dicts=sample_content_blocks_as_dicts)

    mock_crew_kickoff.assert_called_once()
    assert isinstance(result, TitleGenerationOutput)
    assert result.suggested_title == expected_title

@patch('crewai.Crew.kickoff')
def test_title_crew_run_handles_unexpected_output(mock_crew_kickoff, title_crew: GeneralPurposeTitleGenerationCrew, sample_content_blocks_as_dicts: list[dict]):
    """Test that the crew returns a TitleGenerationOutput with an error message on unexpected kickoff result."""
    mock_crew_kickoff.return_value = "Just a raw string"

    result = title_crew.run(content_block_dicts=sample_content_blocks_as_dicts)
    
    assert isinstance(result, TitleGenerationOutput)
    assert "Error: Unexpected output format from crew:" in result.suggested_title
    assert "Just a raw string" in result.suggested_title

@patch('crewai.Crew.kickoff')
def test_title_crew_run_handles_crew_exception(mock_crew_kickoff, title_crew: GeneralPurposeTitleGenerationCrew, sample_content_blocks_as_dicts: list[dict]):
    """Test that the crew returns a TitleGenerationOutput with an error message when kickoff raises an exception."""
    mock_crew_kickoff.side_effect = Exception("Crew failed spectacularly")

    result = title_crew.run(content_block_dicts=sample_content_blocks_as_dicts)

    assert isinstance(result, TitleGenerationOutput)
    assert "Error:" in result.suggested_title
    assert "Crew failed spectacularly" in result.suggested_title 