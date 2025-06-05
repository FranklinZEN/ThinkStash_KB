# aiservice/tests/app/services/test_task_db_service.py
import pytest
from unittest.mock import patch, MagicMock, ANY # ANY is useful for some params
import datetime

# Modules to test
from aiservice.app.services import task_db_service
from aiservice.app.models.task_models import TaskStatus

# --- Test get_db_connection ---
@patch('aiservice.app.services.task_db_service.psycopg2.connect')
@patch('aiservice.app.services.task_db_service.settings')
def test_get_db_connection_success(mock_settings, mock_connect):
    mock_settings.database_url = "postgresql://test_url"
    mock_connection_obj = MagicMock()
    mock_connect.return_value = mock_connection_obj

    conn = task_db_service.get_db_connection()

    mock_connect.assert_called_once_with("postgresql://test_url")
    assert conn == mock_connection_obj

@patch('aiservice.app.services.task_db_service.settings')
def test_get_db_connection_no_url(mock_settings):
    mock_settings.database_url = None
    with pytest.raises(ValueError, match="Database configuration error: DATABASE_URL not set."):
        task_db_service.get_db_connection()

@patch('aiservice.app.services.task_db_service.psycopg2.connect')
@patch('aiservice.app.services.task_db_service.settings')
def test_get_db_connection_failure(mock_settings, mock_connect):
    mock_settings.database_url = "postgresql://test_url"
    mock_connect.side_effect = Exception("DB connection failed")

    with pytest.raises(ConnectionError, match="Database connection error: DB connection failed"):
        task_db_service.get_db_connection()

# --- Test _execute_update (Indirectly tested via public functions, but can be tested directly if needed) ---
# For brevity, direct test of _execute_update is skipped here, but follows similar patching.

# --- Test update_task_status_processing ---
@patch('aiservice.app.services.task_db_service._execute_update')
def test_update_task_status_processing(mock_execute_update):
    mock_conn = MagicMock()
    task_id = "test_task_123"

    task_db_service.update_task_status_processing(task_id, mock_conn)

    expected_sql = 'UPDATE "AITask" SET status = %s, "updatedAt" = %s WHERE id = %s'
    # Using ANY for datetime as it's hard to match exactly
    expected_params = (TaskStatus.PROCESSING.value, ANY, task_id)
    mock_execute_update.assert_called_once_with(mock_conn, expected_sql, expected_params, task_id, "update status to PROCESSING")

# --- Test update_task_status_completed ---
@patch('aiservice.app.services.task_db_service.json.dumps')
@patch('aiservice.app.services.task_db_service._execute_update')
def test_update_task_status_completed(mock_execute_update, mock_json_dumps):
    mock_conn = MagicMock()
    task_id = "test_task_456"
    result_data = {"key": "value", "blocks": [{"id": "b1"}]}
    mock_json_dumps.return_value = '{"key": "value", "blocks": [{"id": "b1"}]}' # Mocked JSON string

    task_db_service.update_task_status_completed(task_id, result_data, mock_conn)
    
    mock_json_dumps.assert_called_once_with(result_data)
    expected_sql = 'UPDATE "AITask" SET status = %s, "resultData" = %s, "errorMessage" = NULL, "updatedAt" = %s WHERE id = %s'
    expected_params = (TaskStatus.COMPLETED.value, mock_json_dumps.return_value, ANY, task_id)
    mock_execute_update.assert_called_once_with(mock_conn, expected_sql, expected_params, task_id, "update status to COMPLETED with results")

# --- Test update_task_status_failed ---
@patch('aiservice.app.services.task_db_service._execute_update')
def test_update_task_status_failed(mock_execute_update):
    mock_conn = MagicMock()
    task_id = "test_task_789"
    error_message = "Something went wrong"

    task_db_service.update_task_status_failed(task_id, error_message, mock_conn)

    expected_sql = 'UPDATE "AITask" SET status = %s, "errorMessage" = %s, "updatedAt" = %s WHERE id = %s'
    expected_params = (TaskStatus.FAILED.value, error_message, ANY, task_id)
    mock_execute_update.assert_called_once_with(mock_conn, expected_sql, expected_params, task_id, "update status to FAILED with error message")
    
# --- Test update_task_status_failed_background_error ---
# This currently calls update_task_status_failed, so it's indirectly tested.
# If its logic diverges, add a specific test.
@patch('aiservice.app.services.task_db_service.update_task_status_failed') # Mock the function it calls
def test_update_task_status_failed_background_error(mock_update_task_status_failed):
    mock_conn = MagicMock()
    task_id = "test_task_bg_err"
    error_message = "Background error"

    task_db_service.update_task_status_failed_background_error(task_id, error_message, mock_conn)
    mock_update_task_status_failed.assert_called_once_with(task_id, error_message, mock_conn) 