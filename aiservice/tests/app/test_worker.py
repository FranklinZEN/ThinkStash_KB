import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from aiservice.main import app, get_db_connection

# Create a TestClient instance
client = TestClient(app)

# --- Fixtures ---

@pytest.fixture(scope="function")
def mock_db_conn():
    """Mocks the database connection and cursor."""
    with patch('aiservice.main.get_db_connection') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        yield mock_cursor

@pytest.fixture(scope="function")
def mock_run_pipeline():
    """Mocks the orchestrator pipeline."""
    with patch('aiservice.main.run_pipeline') as mock_run:
        yield mock_run

# --- Helper ---

def get_headers():
    """Returns the authorization headers for the test client."""
    return {"X-ThinkStash-Worker-Key": "your-very-secret-key-that-will-be-a-secret"}

# --- Tests ---

def test_invoke_worker_success(mock_db_conn, mock_run_pipeline):
    """
    Tests the successful processing of a single task.
    """
    # Arrange: Mock the database to return one pending task
    mock_db_conn.fetchone.return_value = {
        'id': 'test-task-123',
        'payload': {'sourceUrl': 'http://example.com'}
    }
    # Arrange: Mock the pipeline to return a successful result
    mock_run_pipeline.return_value = {'cardId': 'new-card-456'}

    # Act: Call the /invoke endpoint
    response = client.post("/invoke", headers=get_headers())

    # Assert: Check the response
    assert response.status_code == 200
    assert response.json() == {"status": "success", "processed_task_id": "test-task-123"}

    # Assert: Verify database calls
    assert mock_db_conn.fetchone.called
    # Check that status is updated to PROCESSING
    mock_db_conn.execute.assert_any_call(
        'UPDATE "Task" SET status = %s, "progressMessage" = %s WHERE id = %s',
        ('PROCESSING', 'Worker picked up task', 'test-task-123')
    )
    # Check that pipeline was called correctly
    mock_run_pipeline.assert_called_once()
    # Check that status is updated to COMPLETED
    mock_db_conn.execute.assert_any_call(
        'UPDATE "Task" SET status = %s, "progressMessage" = %s, result = %s WHERE id = %s',
        ('COMPLETED', 'Task finished successfully', '{"cardId": "new-card-456"}', 'test-task-123')
    )

def test_invoke_worker_no_pending_tasks(mock_db_conn, mock_run_pipeline):
    """
    Tests the case where there are no pending tasks to process.
    """
    # Arrange: Mock the database to return no tasks
    mock_db_conn.fetchone.return_value = None

    # Act: Call the /invoke endpoint
    response = client.post("/invoke", headers=get_headers())

    # Assert: Check the response
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "No pending tasks."}

    # Assert: Verify that the pipeline was NOT called
    mock_run_pipeline.assert_not_called()

def test_invoke_worker_pipeline_failure(mock_db_conn, mock_run_pipeline):
    """
    Tests the case where the pipeline fails during execution.
    """
    # Arrange: Mock the database to return one pending task
    mock_db_conn.fetchone.return_value = {
        'id': 'test-task-fail-789',
        'payload': {'sourceUrl': 'http://example.com/fail'}
    }
    # Arrange: Mock the pipeline to raise an exception
    mock_run_pipeline.side_effect = Exception("Pipeline processing error")

    # Act: Call the /invoke endpoint
    response = client.post("/invoke", headers=get_headers())

    # Assert: Check the response
    assert response.status_code == 500
    assert "Failed to process task test-task-fail-789" in response.json()['detail']

    # Assert: Verify database calls for failure
    mock_db_conn.execute.assert_any_call(
        'UPDATE "Task" SET status = %s, error = %s WHERE id = %s',
        ('FAILED', '{"userMessage": "An unexpected error occurred during processing.", "errorCode": "PIPELINE_FAILURE", "details": "Pipeline processing error"}', 'test-task-fail-789')
    )

def test_invoke_unauthorized(mock_db_conn):
    """Tests that the endpoint returns 401 Unauthorized without the correct key."""
    response = client.post("/invoke", headers={"X-ThinkStash-Worker-Key": "wrong-key"})
    assert response.status_code == 401

def test_health_check():
    """Tests the /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"} 