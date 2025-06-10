import unittest
from unittest.mock import patch, MagicMock, call, ANY
import json
import psycopg2

# We need to add the project root to the path to import the worker
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from worker import process_single_task, get_db_connection

class TestWorker(unittest.TestCase):

    @patch('worker.get_db_connection')
    @patch('worker.run_pipeline')
    def test_process_single_task_success(self, mock_run_pipeline, mock_get_db_connection):
        # --- Setup Mocks ---
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock fetching a single task
        mock_task_record = {'id': 'task-123', 'payload': {'sourceUrl': 'http://example.com'}}
        mock_cursor.fetchone.return_value = mock_task_record

        # Mock the pipeline execution result
        mock_run_pipeline.return_value = {'cardId': 'card-456'}

        # --- Call the function ---
        process_single_task()

        # --- Assertions ---
        # 1. Check that a connection was established
        mock_get_db_connection.assert_called_once()

        # 2. Check that the correct sequence of SQL commands was executed
        self.assertEqual(mock_cursor.execute.call_count, 3)
        
        # Check that we selected a task and locked the row
        mock_cursor.execute.assert_any_call(
            unittest.mock.ANY,
        ) # The exact query string is long, so we just check it was called.

        # Check that the task was updated to PROCESSING
        mock_cursor.execute.assert_any_call(
            'UPDATE "Task" SET status = %s, "progressMessage" = %s WHERE id = %s',
            ('PROCESSING', 'Worker picked up task', 'task-123')
        )

        # 3. Check that the pipeline was called correctly
        mock_run_pipeline.assert_called_once_with(mock_conn, 'task-123', {'sourceUrl': 'http://example.com'})

        # 4. Check that the task was updated to COMPLETED with the correct result
        mock_cursor.execute.assert_any_call(
            'UPDATE "Task" SET status = %s, "progressMessage" = %s, result = %s WHERE id = %s',
            ('COMPLETED', 'Task finished successfully', '{"cardId": "card-456"}', 'task-123')
        )

        # 5. Check that the transaction was committed
        mock_conn.commit.assert_called()


    @patch('worker.get_db_connection')
    @patch('worker.run_pipeline')
    def test_process_single_task_failure(self, mock_run_pipeline, mock_get_db_connection):
        # --- Setup Mocks ---
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_task_record = {'id': 'task-789', 'payload': {'sourceUrl': 'http://fail.com'}}
        mock_cursor.fetchone.return_value = mock_task_record

        # Mock the pipeline to raise an exception
        pipeline_error = Exception("Something went wrong in the pipeline")
        mock_run_pipeline.side_effect = pipeline_error

        # --- Call the function ---
        process_single_task()

        # --- Assertions ---
        # 1. Check that the pipeline was called
        mock_run_pipeline.assert_called_once_with(mock_conn, 'task-789', {'sourceUrl': 'http://fail.com'})

        # 2. Check that the transaction was rolled back
        mock_conn.rollback.assert_called_once()
        
        # 3. Check that the task was updated to FAILED with error details
        error_payload = json.dumps({
            "userMessage": "An unexpected error occurred during processing.",
            "errorCode": "PIPELINE_FAILURE",
            "details": str(pipeline_error)
        })
        mock_cursor.execute.assert_any_call(
            'UPDATE "Task" SET status = %s, error = %s WHERE id = %s',
            ('FAILED', error_payload, 'task-789')
        )

        # 4. Check that the final state was committed
        mock_conn.commit.assert_called()


    @patch('worker.get_db_connection')
    @patch('worker.run_pipeline')
    def test_no_pending_tasks(self, mock_run_pipeline, mock_get_db_connection):
        # --- Setup Mocks ---
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock fetching a task to return None
        mock_cursor.fetchone.return_value = None

        # --- Call the function ---
        process_single_task()

        # --- Assertions ---
        # 1. Assert that the task selection query was made
        mock_cursor.execute.assert_called_once()

        # 2. Assert that the pipeline was NEVER called
        mock_run_pipeline.assert_not_called()

        # 3. Assert that no status updates were made
        self.assertEqual(mock_cursor.execute.call_count, 1) # Only the SELECT call

        # 4. Assert the connection was closed
        mock_conn.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()