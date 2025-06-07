import pytest
import json
import uuid
import itertools
from unittest.mock import patch, MagicMock
from aiservice.app.models.orchestration_models import ContentBlock, OrchestrationStatusCodeEnum
from aiservice.app.models.insight_generation_models import RewriteContentInput
from crewai.tasks.task_output import TaskOutput

from aiservice.app.crews.content_rewrite_crew import ContentRewriteCrewManager
from aiservice.app.models.pipeline_models import DocumentMetadata

@pytest.fixture
def sample_user_id() -> str:
    return "test_user_crew"

@pytest.fixture
def sample_rewrite_input(sample_user_id) -> RewriteContentInput:
    """Provides a sample RewriteContentInput for testing."""
    content_block = ContentBlock(
        block_id="cb1", user_id=sample_user_id, document_id="test_doc_crew_original",
        type="text", content="This is the original text."
    )
    doc_meta = DocumentMetadata(
        document_id="test_doc_crew_original", user_id=sample_user_id,
        source_identifier="test_doc_crew_original", source_type='text'
    )
    return RewriteContentInput(content_blocks_to_rewrite=[content_block], document_metadata=doc_meta)

class TestContentRewriteCrewManager:
    @patch("aiservice.app.crews.content_rewrite_crew.uuid.uuid4")
    def test_run_successful_flow(self, mock_uuid, sample_rewrite_input, sample_user_id):
        fixed_new_doc_id = "fixed_new_rewritten_doc_id"
        mock_uuid.side_effect = itertools.chain(["some-random-task-id", fixed_new_doc_id], itertools.repeat("junk-uuid"))

        with patch('aiservice.app.crews.content_rewrite_crew.Task'), \
             patch('aiservice.app.crews.content_rewrite_crew.ContentRewriteAgents') as MockAgentsFactory, \
             patch('aiservice.app.crews.content_rewrite_crew.Crew') as MockCrew:

            agent_instance = MockAgentsFactory.return_value
            mock_reconstruction_tool = MagicMock()
            agent_instance.content_processor_tool = mock_reconstruction_tool
            
            manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
            
            llm_output_str = '{"segments": [{"type": "text", "content": "Rewritten text."}]}'
            mock_task_output = MagicMock(spec=TaskOutput, raw=llm_output_str)
            mock_crew_kickoff_output = MagicMock(tasks_output=[mock_task_output], usage_metrics={'total_tokens': 10})
            MockCrew.return_value.kickoff.return_value = mock_crew_kickoff_output
            
            reconstructed_blocks = [ContentBlock(block_id="new1", type="text", content="Rewritten text.", user_id=sample_user_id, document_id=fixed_new_doc_id)]
            mock_reconstruction_tool.reconstruct_content_from_summary.return_value = reconstructed_blocks

            result = manager.run()
            
            assert result.status_code == OrchestrationStatusCodeEnum.SUCCESS.value
            assert result.new_rewritten_document_id == fixed_new_doc_id
            assert result.rewritten_content_blocks[0].content == "Rewritten text."
            assert result.usage_metrics['total_tokens'] == 10

    @patch("aiservice.app.crews.content_rewrite_crew.uuid.uuid4")
    def test_run_fails_with_invalid_json_from_agent(self, mock_uuid, sample_rewrite_input):
        mock_uuid.side_effect = itertools.repeat("junk-uuid")
        with patch('aiservice.app.crews.content_rewrite_crew.Task'), \
             patch('aiservice.app.crews.content_rewrite_crew.ContentRewriteAgents'), \
             patch('aiservice.app.crews.content_rewrite_crew.Crew') as MockCrew:
            
            manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
            mock_task_output = MagicMock(spec=TaskOutput, raw="this is not valid json")
            MockCrew.return_value.kickoff.return_value = MagicMock(tasks_output=[mock_task_output])

            result = manager.run()
            
            assert result.status_code == OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_OUTPUT_PARSING.value
            assert "Failed to extract clean JSON" in result.error_message

    @patch("aiservice.app.crews.content_rewrite_crew.uuid.uuid4")
    def test_run_fails_with_json_violating_pydantic_model(self, mock_uuid, sample_rewrite_input):
        mock_uuid.side_effect = itertools.repeat("junk-uuid")
        with patch('aiservice.app.crews.content_rewrite_crew.Task'), \
             patch('aiservice.app.crews.content_rewrite_crew.ContentRewriteAgents'), \
             patch('aiservice.app.crews.content_rewrite_crew.Crew') as MockCrew:

            manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
            raw_output = '{"wrong_key": "some value"}'
            mock_task_output = MagicMock(spec=TaskOutput, raw=raw_output)
            MockCrew.return_value.kickoff.return_value = MagicMock(tasks_output=[mock_task_output])

            result = manager.run()

            assert result.status_code == OrchestrationStatusCodeEnum.REWRITE_FAILED_SUMMARIZATION_OUTPUT_PARSING.value
            assert "Pydantic validation" in result.error_message

    @patch("aiservice.app.crews.content_rewrite_crew.uuid.uuid4")
    def test_run_fails_if_reconstruction_tool_crashes(self, mock_uuid, sample_rewrite_input):
        mock_uuid.side_effect = itertools.repeat("junk-uuid")
        with patch('aiservice.app.crews.content_rewrite_crew.Task'), \
             patch('aiservice.app.crews.content_rewrite_crew.ContentRewriteAgents') as MockAgentsFactory, \
             patch('aiservice.app.crews.content_rewrite_crew.Crew') as MockCrew:
            
            agent_instance = MockAgentsFactory.return_value
            agent_instance.content_processor_tool.reconstruct_content_from_summary.side_effect = Exception("Tool exploded")
            
            manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
            raw_output = '{"segments": [{"type": "text", "content": "Rewritten text."}]}'
            mock_task_output = MagicMock(spec=TaskOutput, raw=raw_output)
            MockCrew.return_value.kickoff.return_value = MagicMock(tasks_output=[mock_task_output])

            result = manager.run()

            assert result.status_code == OrchestrationStatusCodeEnum.REWRITE_FAILED_RECONSTRUCTION.value
            assert "Tool exploded" in result.error_message

    @patch("aiservice.app.crews.content_rewrite_crew.uuid.uuid4")
    def test_run_fails_if_crew_kickoff_crashes(self, mock_uuid, sample_rewrite_input):
        mock_uuid.side_effect = itertools.repeat("junk-uuid")
        with patch('aiservice.app.crews.content_rewrite_crew.Task'), \
             patch('aiservice.app.crews.content_rewrite_crew.ContentRewriteAgents'), \
             patch('aiservice.app.crews.content_rewrite_crew.Crew') as MockCrew:
            
            manager = ContentRewriteCrewManager(rewrite_input=sample_rewrite_input)
            MockCrew.return_value.kickoff.side_effect = Exception("Crew kickoff failed")

            result = manager.run()

            assert result.status_code == OrchestrationStatusCodeEnum.ERROR_CREW_EXECUTION_FAILED.value
            assert "Crew kickoff failed" in result.error_message