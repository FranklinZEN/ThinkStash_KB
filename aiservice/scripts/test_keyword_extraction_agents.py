#!/usr/bin/env python
# coding: utf-8
"""
Unit tests for the Keyword Identifier Agent.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import List
import sys
from pathlib import Path

# Adjust sys.path to include the project root directory
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from aiservice.app.models.orchestration_models import ContentBlock
from aiservice.app.agents.keyword_extraction_agents import KeywordExtractionAgents
from aiservice.app.tools.formatting_tools import KeywordToTagFormatterTool
from crewai import Agent

@pytest.fixture
def keyword_agent() -> Agent:
    """Fixture to provide a keyword_identifier_agent instance for testing."""
    # We can mock the llm_client used by the agent factory
    agent_factory = KeywordExtractionAgents(llm_client=MagicMock())
    return agent_factory.keyword_identifier_agent()

@pytest.fixture
def sample_content_blocks() -> list[ContentBlock]:
    """Provides a sample list of ContentBlock objects for testing."""
    return [
        ContentBlock(type="text", content="Deep learning is a powerful AI technique."),
        ContentBlock(type="text", content="It enables computers to learn from large datasets.")
    ]

# Test the agent's initialization (basic test)
def test_keyword_agent_initialization(keyword_agent: Agent):
    """Tests the initialization of the keyword agent, checking its configuration."""
    assert keyword_agent.role == "Expert Keyword Analyst and Subject Matter Specialist"
    assert "deeply understand its core concepts" in keyword_agent.goal
    assert len(keyword_agent.tools) == 1
    assert isinstance(keyword_agent.tools[0], KeywordToTagFormatterTool)

# The comments below are kept for context, as they correctly state that
# full testing is best done at the crew level.
# To test the agent's execution, we would typically mock the `kickoff` method of a Crew
# that uses this agent, or mock the tools' `_run` methods if testing the agent directly.
# Since an agent's primary execution happens within a Task in a Crew, testing it in isolation
# without a task can be limited. The most meaningful tests often involve the agent within a task.

# For now, we'll assume the primary testing of the agent's keyword generation capability
# will be done via testing the GeneralPurposeKeywordExtractionCrew, which sets up the necessary task.

# If we wanted to directly test the agent's interaction with tools, it would look like this:
# (This requires more intricate mocking of how CrewAI passes data between tools and agent)

# @patch.object(FullTextContentExtractorTool, '_run')
# @patch.object(OptimizedLLMInteractionTool, '_run')
# def test_agent_uses_tools_correctly(mock_llm_tool_run, mock_text_extractor_run, keyword_agent, sample_content_blocks):
#     mock_text_extractor_run.return_value = "Deep learning is a powerful AI technique. It enables computers to learn from large datasets."
#     mock_llm_tool_run.return_value = "['deep learning', 'AI', 'large datasets']" # Simulate LLM output

#     # This is a conceptual test. Actually invoking agent methods to trigger tool usage
#     # outside a CrewAI task execution flow is not straightforward.
#     # Agent's logic is typically bound to a Task that defines its execution context.

#     # A more practical approach for agent logic is usually testing it as part of a crew task.
#     # For instance, in test_keyword_extraction_crew.py, we'd mock the LLM tool's output for the agent's task.

#     # For the purpose of this file, we acknowledge that agent-level testing often merges with crew-level testing
#     # where the agent performs a specific task.

    # assert True # Placeholder for more complex agent-specific logic test if developed.

print("Basic structure for test_keyword_extraction_agents.py created.")
print("Further tests would typically mock tool outputs or test the agent within a crew and task structure.") 