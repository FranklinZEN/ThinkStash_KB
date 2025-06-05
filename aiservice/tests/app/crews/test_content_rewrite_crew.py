#!/usr/bin/env python
# coding: utf-8
import pytest
import json
import uuid
from unittest.mock import MagicMock, patch, call
from typing import List, Dict, Any, Optional

from aiservice.app.crews.content_rewrite_crew import ContentRewriteCrewManager
from aiservice.app.models.insight_generation_models import RewriteContentInput, RewriteContentOutput, ContentBlock
from aiservice.app.models.task_output_models import SummarizerTaskOutput, StructuredSummary, Segment
from aiservice.app.models.pipeline_models import DocumentMetadata
from aiservice.app.agents.content_rewrite_agents import ContentRewriteAgents # For patching
from aiservice.app.tools.insight_generation_tools import FastContentBlockProcessorTool # For patching
from crewai import Crew, Agent # For patching kickoff and for spec in Agent mock
from crewai.tasks.task_output import TaskOutput as CrewTaskOutput # To mock task output from crew
from crewai.crew import CrewOutput # For spec in Crew kickoff mock

# --- Test Fixtures ---
@pytest.fixture
def sample_user_id() -> str:
    return "test_user_crew"

@pytest.fixture
def sample_document_id() -> str:
    return "test_doc_crew_original"

@pytest.fixture
def sample_rewrite_input(sample_user_id, sample_document_id) -> RewriteContentInput:
    doc_meta = DocumentMetadata(
        document_id=sample_document_id,
        user_id=sample_user_id,
        source_identifier="test_source",
        source_type="test_type"
    )
    content_blocks = [
        ContentBlock(block_id="cb1", type="text", content="First paragraph.", user_id=sample_user_id, document_id=sample_document_id),
        ContentBlock(block_id="cb2", type="image", image_id_ref="img1", gcs_url="gs://bucket/img1.jpg", alt_text="Alt text 1", user_id=sample_user_id, document_id=sample_document_id),
        ContentBlock(block_id="cb3", type="text", content="Second paragraph.", user_id=sample_user_id, document_id=sample_document_id),
    ]
    return RewriteContentInput(
        content_blocks_to_rewrite=content_blocks,
        document_metadata=doc_meta,
        user_id=sample_user_id # Also passing user_id directly to RewriteContentInput
    )

@pytest.fixture
def mock_agents_factory_path() -> str:
    return "aiservice.app.crews.content_rewrite_crew.ContentRewriteAgents"

@pytest.fixture
def mock_crew_path() -> str:
    return "aiservice.app.crews.content_rewrite_crew.Crew"

# --- Test Cases for ContentRewriteCrewManager.run() ---

@patch("aiservice.app.crews.content_rewrite_crew.uuid.uuid4") # Mock uuid4 to control new_rewritten_document_id
def test_run_successful_flow(
    mock_uuid_uuid4: MagicMock,
    mock_agents_factory_path: str,
    mock_crew_path: str,
    sample_rewrite_input: RewriteContentInput,
    sample_user_id: str,
    sample_document_id: str # Original doc id
):
    fixed_new_doc_id = "fixed_new_rewritten_doc_id"
    mock_uuid_uuid4.return_value = fixed_new_doc_id

    # Mock agents factory and its methods
    with patch(mock_agents_factory_path) as MockAgentsFactory:
        mock_summarization_agent_instance = MagicMock(spec=Agent) # Make it a spec of Agent
        mock_summarization_agent_instance.name = "Mocked Summarization Agent" # Give it a name for CrewTaskOutput
        mock_summarization_agent_instance.role = "Mock Role" # Add role attribute
        # Add other essential Agent attributes if Task validation requires them
        mock_summarization_agent_instance.goal = "Mock Goal"
        mock_summarization_agent_instance.backstory = "Mock Backstory"
        mock_summarization_agent_instance.llm = MagicMock()
        mock_summarization_agent_instance.tools = []
        mock_summarization_agent_instance.verbose = False # Add verbose attribute
        mock_summarization_agent_instance.max_rpm = None # Add max_rpm attribute
        mock_summarization_agent_instance._token_process = None # Add _token_process attribute
        mock_summarization_agent_instance.security_config = None # Add security_config attribute
        
        mock_content_processor_tool_instance = MagicMock(spec=FastContentBlockProcessorTool)
        
        mock_agents_factory_instance = MockAgentsFactory.return_value
        mock_agents_factory_instance.summarization_agent.return_value = mock_summarization_agent_instance
        mock_agents_factory_instance.content_processor_tool = mock_content_processor_tool_instance
        mock_agents_factory_instance.summarizer_temperature = 0.1 # Example value
        mock_agents_factory_instance.summarizer_max_tokens = 100 # Example value

        # Mock Crew and its kickoff method
        with patch(mock_crew_path) as MockCrewConstructor:
            mock_crew_instance = MockCrewConstructor.return_value
            
            # Simulate LLM output for structured summary
            llm_output_segments_json = json.dumps({
                "segments": [
                    {"type": "text", "content": "Rewritten text 1"},
                    {"type": "image_reference", "image_id_ref": "img1"}
                ]
            })
            # Mock the raw output from the summarization task
            mock_summarizer_task_raw_output = CrewTaskOutput(description="Summarizer task", agent=mock_summarization_agent_instance.name, raw=llm_output_segments_json) # Use agent name (string)
            
            mock_crew_kickoff_output = MagicMock(spec=CrewOutput)
            mock_crew_kickoff_output.tasks_output = [mock_summarizer_task_raw_output]
            mock_crew_kickoff_output.raw = "Crew raw output for successful flow" # Example raw output
            mock_crew_kickoff_output.json_output = None # Or actual JSON if relevant
            mock_crew_kickoff_output.pydantic_output = None # Or actual Pydantic if relevant
            mock_crew_kickoff_output.token_usage = {"total_tokens": 50, "prompt_tokens": 20, "completion_tokens": 30}
            mock_crew_instance.kickoff.return_value = mock_crew_kickoff_output

            # This mock is for self.crew.usage_metrics accessed by SUT for RewriteContentOutput
            mock_crew_instance.usage_metrics = {"total_tokens": 50, "prompt_tokens": 20, "completion_tokens": 30}

            # Mock FastContentBlockProcessorTool._run() output
            reconstructed_dicts = [
                {"block_id": "new_cb1", "type": "text", "content": "Rewritten text 1", "user_id": sample_user_id, "document_id": fixed_new_doc_id, "order_index": 0},
                {"block_id": "new_cb2", "type": "image", "image_id_ref": "img1", "gcs_url": "gs://bucket/img1.jpg", "user_id": sample_user_id, "document_id": fixed_new_doc_id, "order_index": 1}
            ]
            mock_content_processor_tool_instance._run.return_value = reconstructed_dicts

            # Initialize and run the manager
            manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
            result = manager.run()

            # Assertions
            assert result.status_code == "success"
            assert result.error_message is None
            assert len(result.ai_rewritten_content_blocks) == 2
            
            # Check block content and assigned IDs
            assert result.ai_rewritten_content_blocks[0].content == "Rewritten text 1"
            assert result.ai_rewritten_content_blocks[0].document_id == fixed_new_doc_id
            assert result.ai_rewritten_content_blocks[0].user_id == sample_user_id # User ID from input
            assert result.ai_rewritten_content_blocks[1].image_id_ref == "img1"
            assert result.ai_rewritten_content_blocks[1].document_id == fixed_new_doc_id
            assert result.ai_rewritten_content_blocks[1].user_id == sample_user_id

            assert result.usage_metrics["total_tokens"] == 50
            assert manager.user_id_for_rewrite == sample_user_id
            assert manager.original_document_id == sample_document_id
            assert manager.new_rewritten_document_id == fixed_new_doc_id

            # Verify agents_factory was initialized with correct IDs
            MockAgentsFactory.assert_called_once_with(
                user_id=sample_user_id,
                document_id_for_output_blocks=fixed_new_doc_id
            )

            # Verify summarization agent was created
            mock_agents_factory_instance.summarization_agent.assert_called_once()
            
            # Verify crew kickoff inputs
            expected_concatenated_text = "First paragraph.\n\nSecond paragraph."
            expected_essential_image_meta_json = json.dumps([{
                "image_id_ref": "img1", 
                "gcs_url": "gs://bucket/img1.jpg", 
                "alt_text": "Alt text 1",
                # Caption and llm_description are None in fixture, so not included by default
            }])
            mock_crew_instance.kickoff.assert_called_once()
            kickoff_args = mock_crew_instance.kickoff.call_args[1]["inputs"]
            assert kickoff_args["concatenated_text"] == expected_concatenated_text
            # For image metadata, load JSON to compare dicts due to potential key order differences
            assert json.loads(kickoff_args["essential_image_metadata_for_summarizer_prompt"]) == json.loads(expected_essential_image_meta_json)

            # Verify content_processor_tool was called correctly
            mock_content_processor_tool_instance._run.assert_called_once()
            tool_run_args = mock_content_processor_tool_instance._run.call_args[1]
            assert tool_run_args["operation"] == "reconstruct_content_from_summary"
            assert isinstance(tool_run_args["structured_summary_input"], StructuredSummary)
            assert len(tool_run_args["structured_summary_input"].segments) == 2
            assert tool_run_args["structured_summary_input"].segments[0].content == "Rewritten text 1"
            assert json.loads(tool_run_args["image_metadata_list_json"]) == json.loads(expected_essential_image_meta_json)
            assert tool_run_args["document_id"] == fixed_new_doc_id


def test_run_summarizer_returns_invalid_json(
    mock_agents_factory_path: str,
    mock_crew_path: str,
    sample_rewrite_input: RewriteContentInput
):
    with patch(mock_agents_factory_path) as MockAgentsFactory, \
         patch(mock_crew_path) as MockCrewConstructor:
        
        mock_agents_factory_instance = MockAgentsFactory.return_value
        mock_summarization_agent_instance = MagicMock(spec=Agent) # Make it a spec of Agent
        mock_summarization_agent_instance.name = "Mocked Summarization Agent" # Give it a name
        mock_summarization_agent_instance.role = "Mock Role"
        mock_summarization_agent_instance.goal = "Mock Goal"
        mock_summarization_agent_instance.backstory = "Mock Backstory"
        mock_summarization_agent_instance.llm = MagicMock()
        mock_summarization_agent_instance.tools = []
        mock_summarization_agent_instance.verbose = False
        mock_summarization_agent_instance.max_rpm = None
        mock_summarization_agent_instance._token_process = None
        mock_summarization_agent_instance.security_config = None
        mock_agents_factory_instance.summarization_agent.return_value = mock_summarization_agent_instance
        mock_agents_factory_instance.summarizer_temperature = 0.1
        mock_agents_factory_instance.summarizer_max_tokens = 100

        mock_crew_instance = MockCrewConstructor.return_value
        mock_summarizer_task_raw_output = CrewTaskOutput(description="Summarizer task", agent=mock_summarization_agent_instance.name, raw="this is not valid json") # Use agent name
        
        mock_crew_kickoff_output = MagicMock(spec=CrewOutput)
        mock_crew_kickoff_output.tasks_output = [mock_summarizer_task_raw_output]
        mock_crew_kickoff_output.raw = "Crew raw output for invalid json test"
        mock_crew_kickoff_output.token_usage = {"total_tokens": 5, "prompt_tokens": 2, "completion_tokens": 3} # Example usage
        mock_crew_instance.kickoff.return_value = mock_crew_kickoff_output
        mock_crew_instance.usage_metrics = mock_crew_kickoff_output.token_usage

        manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
        result = manager.run()

        assert result.status_code == "error_unexpected_output_type"
        assert "Failed to process or parse valid structured summary from LLM output after all attempts." in result.error_message
        assert not result.ai_rewritten_content_blocks


def test_run_summarizer_returns_json_not_matching_structure(
    mock_agents_factory_path: str,
    mock_crew_path: str,
    sample_rewrite_input: RewriteContentInput
):
    with patch(mock_agents_factory_path) as MockAgentsFactory, \
         patch(mock_crew_path) as MockCrewConstructor:
        
        mock_agents_factory_instance = MockAgentsFactory.return_value
        mock_summarization_agent_instance = MagicMock(spec=Agent) # Make it a spec of Agent
        mock_summarization_agent_instance.name = "Mocked Summarization Agent" # Give it a name
        mock_summarization_agent_instance.role = "Mock Role"
        mock_summarization_agent_instance.goal = "Mock Goal"
        mock_summarization_agent_instance.backstory = "Mock Backstory"
        mock_summarization_agent_instance.llm = MagicMock()
        mock_summarization_agent_instance.tools = []
        mock_summarization_agent_instance.verbose = False
        mock_summarization_agent_instance.max_rpm = None
        mock_summarization_agent_instance._token_process = None
        mock_summarization_agent_instance.security_config = None
        mock_agents_factory_instance.summarization_agent.return_value = mock_summarization_agent_instance

        mock_crew_instance = MockCrewConstructor.return_value
        # Valid JSON, but not the expected structure for StructuredSummary (e.g. missing "segments" key)
        llm_output_invalid_structure_json = json.dumps({"summary_text": "Some text"})
        mock_summarizer_task_raw_output = CrewTaskOutput(description="Summarizer task", agent=mock_summarization_agent_instance.name, raw=llm_output_invalid_structure_json) # Use agent name
        
        mock_crew_kickoff_output = MagicMock(spec=CrewOutput)
        mock_crew_kickoff_output.tasks_output = [mock_summarizer_task_raw_output]
        mock_crew_kickoff_output.raw = "Crew raw output for invalid structure test"
        mock_crew_kickoff_output.token_usage = {"total_tokens": 6, "prompt_tokens": 3, "completion_tokens": 3}
        mock_crew_instance.kickoff.return_value = mock_crew_kickoff_output
        mock_crew_instance.usage_metrics = mock_crew_kickoff_output.token_usage

        manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
        result = manager.run()

        assert result.status_code == "error_unexpected_output_type"
        assert "Failed to process or parse valid structured summary from LLM output after all attempts." in result.error_message
        assert not result.ai_rewritten_content_blocks


@patch("aiservice.app.crews.content_rewrite_crew.uuid.uuid4") # ADDED: Patch uuid
def test_run_reconstruction_tool_fails(
    mock_uuid_uuid4: MagicMock, # ADDED: mock_uuid_uuid4 argument
    mock_agents_factory_path: str,
    mock_crew_path: str,
    sample_rewrite_input: RewriteContentInput,
    sample_user_id: str, # ADDED for consistency if needed for user_id in block assertions
    sample_document_id: str # ADDED for consistency
):
    fixed_fail_new_doc_id = "fixed_reconstruction_fail_doc_id" # ADDED
    mock_uuid_uuid4.return_value = fixed_fail_new_doc_id # ADDED

    with patch(mock_agents_factory_path) as MockAgentsFactory, \
         patch(mock_crew_path) as MockCrewConstructor:
        
        mock_agents_factory_instance = MockAgentsFactory.return_value
        mock_summarization_agent_instance = MagicMock(spec=Agent) # Make it a spec of Agent
        mock_summarization_agent_instance.name = "Mocked Summarization Agent" # Give it a name
        mock_summarization_agent_instance.role = "Mock Role"
        mock_summarization_agent_instance.goal = "Mock Goal"
        mock_summarization_agent_instance.backstory = "Mock Backstory"
        mock_summarization_agent_instance.llm = MagicMock()
        mock_summarization_agent_instance.tools = []
        mock_summarization_agent_instance.verbose = False
        mock_summarization_agent_instance.max_rpm = None
        mock_summarization_agent_instance._token_process = None
        mock_summarization_agent_instance.security_config = None
        mock_content_processor_tool_instance = MagicMock(spec=FastContentBlockProcessorTool)
        mock_agents_factory_instance.summarization_agent.return_value = mock_summarization_agent_instance
        mock_agents_factory_instance.content_processor_tool = mock_content_processor_tool_instance

        mock_crew_instance = MockCrewConstructor.return_value
        llm_output_segments_json = json.dumps({"segments": [{"type": "text", "content": "Text"}]})
        mock_summarizer_task_raw_output = CrewTaskOutput(description="Summarizer task", agent=mock_summarization_agent_instance.name, raw=llm_output_segments_json) # Use agent name
        
        mock_crew_kickoff_output = MagicMock(spec=CrewOutput)
        mock_crew_kickoff_output.tasks_output = [mock_summarizer_task_raw_output]
        mock_crew_kickoff_output.raw = "Crew raw output for reconstruction fail test"
        mock_crew_kickoff_output.token_usage = {"total_tokens": 7, "prompt_tokens": 4, "completion_tokens": 3}
        mock_crew_instance.kickoff.return_value = mock_crew_kickoff_output
        mock_crew_instance.usage_metrics = mock_crew_kickoff_output.token_usage

        # Simulate error from reconstruction tool
        mock_content_processor_tool_instance._run.return_value = [{"error": "Tool failed badly"}]

        manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
        result = manager.run()

        # ADDED: Verify the tool was called correctly before it "failed"
        mock_content_processor_tool_instance._run.assert_called_once()
        tool_run_args = mock_content_processor_tool_instance._run.call_args[1]
        assert tool_run_args["operation"] == "reconstruct_content_from_summary"
        assert isinstance(tool_run_args["structured_summary_input"], StructuredSummary)
        assert tool_run_args["structured_summary_input"].segments[0].content == "Text" # From llm_output_segments_json in this test

        # Construct expected_essential_image_meta_json based on sample_rewrite_input
        # (as it's passed to the tool regardless of what the summary contained)
        expected_essential_image_meta_from_input = [{
            "image_id_ref": "img1",
            "gcs_url": "gs://bucket/img1.jpg",
            "alt_text": "Alt text 1"
            # user_id and document_id are not part of this essential_image_metadata structure
        }]
        # Filter None values if any block in sample_rewrite_input didn't have all these fields
        filtered_expected_image_meta = []
        for item in expected_essential_image_meta_from_input:
            filtered_item = {k: v for k, v in item.items() if v is not None}
            if filtered_item.get("image_id_ref"): # Ensure image_id_ref is present
                 filtered_expected_image_meta.append(filtered_item)

        assert json.loads(tool_run_args["image_metadata_list_json"]) == filtered_expected_image_meta
        assert tool_run_args["document_id"] == fixed_fail_new_doc_id
        # END ADDED Block

        assert result.status_code == "error_content_block_validation" # Or a more specific code if tool provides one
        assert "FastContentBlockProcessorTool failed during reconstruction: Tool failed badly" in result.error_message
        assert not result.ai_rewritten_content_blocks


def test_run_crew_kickoff_raises_exception(
    mock_agents_factory_path: str,
    mock_crew_path: str,
    sample_rewrite_input: RewriteContentInput
):
    with patch(mock_agents_factory_path) as MockAgentsFactory, \
         patch(mock_crew_path) as MockCrewConstructor:
        
        mock_agents_factory_instance = MockAgentsFactory.return_value
        # Ensure the agent returned by the factory is a spec of Agent for Task validation
        mock_agent_for_task = MagicMock(spec=Agent) 
        mock_agent_for_task.role = "Mock Role for Exception Test"
        mock_agent_for_task.goal = "Mock Goal"
        mock_agent_for_task.backstory = "Mock Backstory"
        mock_agent_for_task.llm = MagicMock()
        mock_agent_for_task.tools = []
        mock_agent_for_task.verbose = False
        mock_agent_for_task.max_rpm = None
        mock_agent_for_task._token_process = None
        mock_agent_for_task.security_config = None
        mock_agents_factory_instance.summarization_agent.return_value = mock_agent_for_task

        mock_crew_instance = MockCrewConstructor.return_value
        mock_crew_instance.kickoff.side_effect = Exception("Crew exploded!")
        # Also mock usage_metrics for the exception path, as SUT tries to access it
        mock_crew_instance.usage_metrics = {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5} 

        manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
        result = manager.run()

        assert result.status_code == "error_crew_execution_failed"
        assert "An exception occurred during crew kickoff or direct tool call: Crew exploded!" in result.error_message
        # Verify that the usage_metrics from the crew instance (even if kickoff failed) are propagated
        assert result.usage_metrics["total_tokens"] == 10 
        assert not result.ai_rewritten_content_blocks

# TODO: Add tests for:
# - Empty content_blocks_to_rewrite in input
# - Different ways user_id and document_metadata are sourced for self.user_id_for_rewrite
# - Edge cases in _try_json_parse (though this is an internal helper, its effects are tested via main run)
# - Edge cases in safe_parse_to_content_blocks (e.g. tool returns list but not dicts, or dicts missing required fields) 