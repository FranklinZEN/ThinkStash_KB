import pytest
from unittest.mock import MagicMock, patch
from crewai import Agent
import os

from aiservice.app.agents.title_generation_agents import TitleGenerationAgents
from aiservice.app.tools.content_processing_tools import FullTextContentExtractorTool
from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool

@pytest.fixture
def title_agents_factory():
    """Fixture to create an instance of TitleGenerationAgents."""
    with patch('aiservice.app.agents.title_generation_agents.get_configured_llm') as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        yield TitleGenerationAgents(user_id="test_fixture_user")

def test_title_crafting_agent_creation(title_agents_factory: TitleGenerationAgents):
    """Test the creation of the title_crafting_agent."""
    agent = title_agents_factory.title_crafting_agent()
    assert isinstance(agent, Agent)
    assert agent.role == "Expert Title Crafter"
    assert agent.llm is not None 
    assert len(agent.tools) == 2
    assert isinstance(agent.tools[0], FullTextContentExtractorTool)
    assert isinstance(agent.tools[1], OptimizedLLMInteractionTool)
    assert agent.tools[1].llm_client == agent.llm.llm

# Unit testing an agent's full execution flow is complex as it relies on CrewAI's
# task orchestration. We primarily test its configuration and tool setup here.
# Integration tests with a Crew and Task would cover the execution aspects.

# To run these tests:
# Ensure PYTHONPATH is set up if needed, e.g., export PYTHONPATH=${PYTHONPATH}:${PWD}
# Then run: pytest aiservice/scripts/test_title_generation_agents.py