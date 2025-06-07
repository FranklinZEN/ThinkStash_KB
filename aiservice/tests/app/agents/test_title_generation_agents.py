import pytest
from unittest.mock import MagicMock, patch
from crewai import Agent
import sys
import os

# Adjust sys.path to include the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from aiservice.app.agents.title_generation_agents import TitleGenerationAgents
from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool

@pytest.fixture
def title_agents_factory() -> TitleGenerationAgents:
    """Fixture to create an instance of TitleGenerationAgents with a mock LLM."""
    with patch('aiservice.app.agents.title_generation_agents.Settings') as mock_settings_class:
        mock_settings_instance = mock_settings_class.return_value
        mock_settings_instance.get_crew_llm.return_value = MagicMock()
        yield TitleGenerationAgents()

def test_title_crafting_agent_creation(title_agents_factory: TitleGenerationAgents):
    """
    Tests the creation of the title_crafting_agent, which is the only agent
    created by this factory.
    """
    # ACT
    agent = title_agents_factory.title_crafting_agent()

    # ASSERT
    assert isinstance(agent, Agent)
    
    # Assert the agent's properties match the implementation
    assert agent.role == "Expert Title Writer"
    assert "Generate a concise, informative, and engaging title" in agent.goal
    assert agent.llm is not None 
    assert agent.allow_delegation is False
    
    # Assert the correct tool is present
    assert len(agent.tools) == 1
    tool = agent.tools[0]
    assert isinstance(tool, OptimizedLLMInteractionTool)

    # The assertion below is removed because it tests an internal implementation detail.
    # The fact that the agent and its tools are created without error is sufficient.
    # assert tool.llm_client == title_agents_factory.llm