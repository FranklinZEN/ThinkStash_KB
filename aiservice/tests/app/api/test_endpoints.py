# aiservice/tests/app/api/test_endpoints.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, ANY # AsyncMock for async functions
from fastapi import HTTPException, BackgroundTasks
from aiservice.app.models.orchestration_models import OrchestrationStatusCodeEnum

# Modules to test
from aiservice.app.api import endpoints
from aiservice.app.models.insight_generation_models import RewriteContentInput, RewriteContentOutput, ContentBlock
from aiservice.app.models.pipeline_models import DocumentMetadata # Assuming this is the type
from aiservice.app.models.task_models import TaskStatus

# --- Test submit_rewrite_task ---
@pytest.mark.asyncio # For async test functions
@patch('aiservice.app.api.endpoints.uuid.uuid4')
@patch('aiservice.app.api.endpoints.get_db_connection') # Mock the DB connection getter from task_db_service
@patch('aiservice.app.api.endpoints.json.dumps')
async def test_submit_rewrite_task_success(mock_json_dumps, mock_get_db_conn, mock_uuid4):
    # Setup Mocks
    mock_uuid4.return_value = "test-uuid-123"
    mock_conn_obj = MagicMock()
    mock_get_db_conn.return_value = mock_conn_obj
    mock_cursor = MagicMock()
    mock_conn_obj.cursor.return_value.__enter__.return_value = mock_cursor # For 'with conn.cursor() as cur:'
    
    mock_json_dumps.return_value = '{"original_content_blocks": [], "document_metadata": null}'

    # Prepare Inputs
    payload_data = {
        "content_blocks_to_rewrite": [{
            "block_id": "b1",
            "type": "text",
            "user_id": "user123",
            "document_id": "doc_id_from_payload",
            "content": "test"
        }],
        "user_id": "user123"
    }
    payload = RewriteContentInput(**payload_data)
    
    # Mock BackgroundTasks and its add_task method
    mock_background_tasks = MagicMock(spec=BackgroundTasks)

    # Call the endpoint function
    response = await endpoints.submit_rewrite_task(payload, mock_background_tasks)

    # Assertions
    mock_get_db_conn.assert_called_once()
    mock_cursor.execute.assert_called_once() 
    mock_background_tasks.add_task.assert_called_once() # Check if add_task was called

    assert response["task_id"] == "test-uuid-123"
    assert "accepted for processing" in response["message"]
    
    args, kwargs = mock_cursor.execute.call_args
    assert "INSERT INTO \"AITask\"" in args[0]
    assert args[1][0] == "test-uuid-123" 
    assert args[1][2] == TaskStatus.PENDING.value

@pytest.mark.asyncio
@patch('aiservice.app.api.endpoints.get_db_connection')
async def test_submit_rewrite_task_db_connection_fails(mock_get_db_conn):
    mock_get_db_conn.side_effect = ConnectionError("Failed to connect")
    payload = RewriteContentInput(content_blocks_to_rewrite=[
        ContentBlock(block_id="1", type="text", user_id="test_user", document_id="test_doc", content="t")
    ])
    background_tasks = MagicMock(spec=BackgroundTasks)

    with pytest.raises(HTTPException) as exc_info:
        await endpoints.submit_rewrite_task(payload, background_tasks)
    assert exc_info.value.status_code == 503 # Service Unavailable due to ConnectionError
    assert "Database service is unavailable" in exc_info.value.detail

@pytest.mark.asyncio
@patch('aiservice.app.api.endpoints.get_db_connection')
async def test_submit_rewrite_task_db_insert_fails(mock_get_db_conn):
    mock_conn_obj = MagicMock()
    mock_get_db_conn.return_value = mock_conn_obj
    mock_cursor = MagicMock()
    mock_conn_obj.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.execute.side_effect = Exception("Insert failed") # Simulate INSERT failure

    payload = RewriteContentInput(content_blocks_to_rewrite=[
        ContentBlock(block_id="1", type="text", user_id="test_user", document_id="test_doc", content="t")
    ])
    background_tasks = MagicMock(spec=BackgroundTasks)

    with pytest.raises(HTTPException) as exc_info:
        await endpoints.submit_rewrite_task(payload, background_tasks)
    assert exc_info.value.status_code == 500
    assert "Failed to submit rewrite task" in exc_info.value.detail
    assert "Insert failed" in exc_info.value.detail


# --- Test process_rewrite_task_in_background ---
@pytest.mark.asyncio
@patch('aiservice.app.api.endpoints.get_db_connection')
@patch('aiservice.app.api.endpoints.update_task_status_processing')
@patch('aiservice.app.api.endpoints.update_task_status_completed')
@patch('aiservice.app.api.endpoints.update_task_status_failed')
@patch('aiservice.app.api.endpoints.ContentRewriteCrewManager')
async def test_process_rewrite_task_success(
    mock_crew_manager_class, mock_update_failed, 
    mock_update_completed, mock_update_processing, mock_get_db_conn):
    
    # Setup Mocks
    mock_conn_obj = MagicMock()
    mock_get_db_conn.return_value = mock_conn_obj
    
    mock_crew_instance = MagicMock()
    mock_crew_manager_class.return_value = mock_crew_instance
    
    mock_rewritten_block_data = {
        "block_id":"b1-rewritten", 
        "type":"text", 
        "user_id": "user_bg",
        "document_id": "doc_rewritten_placeholder",
        "content": "rewritten"
    }
    mock_rewritten_block = ContentBlock(**mock_rewritten_block_data)
    
    # This now needs to match the real RewriteContentOutput model
    crew_output = RewriteContentOutput(
        status_code=OrchestrationStatusCodeEnum.SUCCESS.value,
        rewritten_content_blocks=[mock_rewritten_block],
        usage_metrics={"tokens": 100},
        new_rewritten_document_id="doc_rewritten_placeholder"
    )
    mock_crew_instance.run.return_value = crew_output

    task_id = "bg_task_1"
    user_id = "user_bg"
    content_blocks_dict = [{
        "block_id": "b1", 
        "type": "text", 
        "user_id": user_id,
        "document_id": "doc_bg_task_1",
        "data": {"text": "original"}
    }] 
    doc_meta_dict = None

    await endpoints.process_rewrite_task_in_background(
        task_id, user_id, content_blocks_dict, doc_meta_dict, correlation_id=None
    )

    mock_get_db_conn.assert_called_once()
    mock_update_processing.assert_called_once_with(task_id, mock_conn_obj)
    
    args, kwargs = mock_crew_manager_class.call_args
    assert isinstance(kwargs['rewrite_input'], RewriteContentInput)
    assert kwargs['rewrite_input'].user_id == user_id
    assert len(kwargs['rewrite_input'].content_blocks_to_rewrite) == 1
    assert kwargs['rewrite_input'].content_blocks_to_rewrite[0].block_id == "b1"

    mock_crew_instance.run.assert_called_once()
    
    mock_update_completed.assert_called_once_with(task_id, crew_output.model_dump(), mock_conn_obj)
    mock_update_failed.assert_not_called()
    mock_conn_obj.close.assert_called_once()


@pytest.mark.asyncio
@patch('aiservice.app.api.endpoints.get_db_connection')
@patch('aiservice.app.api.endpoints.update_task_status_processing')
@patch('aiservice.app.api.endpoints.update_task_status_completed') 
@patch('aiservice.app.api.endpoints.update_task_status_failed')
@patch('aiservice.app.api.endpoints.ContentRewriteCrewManager')
async def test_process_rewrite_task_crew_fails(
    mock_crew_manager_class, mock_update_failed, 
    mock_update_completed, mock_update_processing, mock_get_db_conn):
    
    mock_conn_obj = MagicMock()
    mock_get_db_conn.return_value = mock_conn_obj
    
    mock_crew_instance = MagicMock()
    mock_crew_manager_class.return_value = mock_crew_instance
    crew_output = RewriteContentOutput(
        status_code="error_crew_execution_failed",
        error_message="Crew processing failed badly",
        rewritten_content_blocks=[],
        usage_metrics={}
    )
    mock_crew_instance.run.return_value = crew_output

    task_id = "bg_task_2"
    user_id = "user_crew_fail"
    content_blocks_dict = [{
        "block_id":"1",
        "type":"text",
        "user_id": user_id,
        "document_id": "doc_bg_task_2",
        "data":{"text":"t"}
    }]
    doc_meta_dict = None

    await endpoints.process_rewrite_task_in_background(
        task_id, user_id, content_blocks_dict, doc_meta_dict, correlation_id=None
    )

    mock_update_processing.assert_called_once_with(task_id, mock_conn_obj)
    mock_crew_instance.run.assert_called_once()
    mock_update_failed.assert_called_once_with(task_id, "Crew processing failed badly", mock_conn_obj)
    mock_update_completed.assert_not_called()
    mock_conn_obj.close.assert_called_once()

@pytest.mark.asyncio
@patch('aiservice.app.api.endpoints.get_db_connection')
@patch('aiservice.app.api.endpoints.update_task_status_processing')
@patch('aiservice.app.api.endpoints.ContentRewriteCrewManager') 
@patch('aiservice.app.api.endpoints.update_task_status_failed_background_error')
async def test_process_rewrite_task_generic_exception(
    mock_update_failed_bg_error, mock_crew_manager_class, 
    mock_update_processing, mock_get_db_conn):
    
    mock_conn_obj = MagicMock()
    mock_get_db_conn.return_value = mock_conn_obj
    
    mock_crew_instance = MagicMock()
    mock_crew_manager_class.return_value = mock_crew_instance
    mock_crew_instance.run.side_effect = Exception("Unexpected explosion in crew")

    task_id = "bg_task_3"
    user_id = "user_generic_exc"
    content_blocks_dict = [{
        "block_id":"1",
        "type":"text",
        "user_id": user_id,
        "document_id": "doc_bg_task_3",
        "content":"t"
    }]
    doc_meta_dict = None

    await endpoints.process_rewrite_task_in_background(
        task_id, user_id, content_blocks_dict, doc_meta_dict, correlation_id=None
    )

    mock_update_processing.assert_called_once_with(task_id, mock_conn_obj)
    mock_crew_instance.run.assert_called_once()
    mock_update_failed_bg_error.assert_called_once_with(task_id, "Background processing error: Unexpected explosion in crew", mock_conn_obj)
    mock_conn_obj.close.assert_called_once() 