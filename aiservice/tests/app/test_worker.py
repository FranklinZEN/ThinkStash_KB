import unittest
from unittest.mock import patch, MagicMock, call
import json
import psycopg2

# We need to add the project root to the path to import the worker
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from worker import process_single_task, get_db_connection

class TestWorker(unittest.TestCase):

    @patch('aiservice.worker.run_pipeline')
    @patch('aiservice.worker.get_db_connection')
    def test_process_single_task_success(self, mock_get_db_connection, mock_run_pipeline):
        """
        Tests the successful processing of a single task.
        - Mocks the database connection to return a pending task.
        - Mocks the run_pipeline to return a successful result.
        - Verifies that the task status is updated to PROCESSING and then to COMPLETED.
        """
        # --- Setup Mocks ---
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Mock fetching a task
        task_id = 'test-task-123'
        task_payload = {'sourceUrl': 'http://example.com'}
        mock_cur.fetchone.return_value = {'id': task_id, 'payload': task_payload}
        
        # Mock the pipeline result
        pipeline_result = {'cardId': 'card-abc-456'}
        mock_run_pipeline.return_value = pipeline_result

        # --- Run the function to test ---
        process_single_task()

        # --- Assertions ---
        mock_get_db_connection.assert_called_once()
        
        # Verify the sequence of database calls
        self.assertEqual(mock_cur.execute.call_count, 3)
        
        # 1. Lock the task and set to PROCESSING
        mock_cur.execute.assert_any_call(
            'UPDATE "Task" SET status = %s, "progressMessage" = %s WHERE id = %s',
            ('PROCESSING', 'Worker picked up task', task_id)
        )
        
        # 2. Call the pipeline
        mock_run_pipeline.assert_called_once_with(mock_conn, task_id, task_payload)
        
        # 3. Set task to COMPLETED with the result
        mock_cur.execute.assert_any_call(
            'UPDATE "Task" SET status = %s, "progressMessage" = %s, result = %s WHERE id = %s',
            ('COMPLETED', 'Task finished successfully', json.dumps(pipeline_result), task_id)
        )
        
        # Verify transaction management
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called_once()


    @patch('aiservice.worker.run_pipeline')
    @patch('aiservice.worker.get_db_connection')
    def test_process_single_task_pipeline_failure(self, mock_get_db_connection, mock_run_pipeline):
        """
        Tests the failure handling when the pipeline raises an exception.
        - Mocks the database connection to return a pending task.
        - Mocks the run_pipeline to raise an exception.
        - Verifies that the task status is updated to FAILED with error details.
        """
        # --- Setup Mocks ---
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        task_id = 'test-task-fail-456'
        task_payload = {'sourceUrl': 'http://fail.com'}
        mock_cur.fetchone.return_value = {'id': task_id, 'payload': task_payload}
        
        # Mock the pipeline to fail
        error_message = "Pipeline failed spectacularly"
        mock_run_pipeline.side_effect = Exception(error_message)

        # --- Run the function to test ---
        process_single_task()

        # --- Assertions ---
        mock_get_db_connection.assert_called_once()
        mock_run_pipeline.assert_called_once_with(mock_conn, task_id, task_payload)
        
        # Verify transaction rollback
        mock_conn.rollback.assert_called_once()

        # Verify task is updated to FAILED
        expected_error_payload = json.dumps({
            "userMessage": "An unexpected error occurred during processing.",
            "errorCode": "PIPELINE_FAILURE",
            "details": error_message
        })
        mock_cur.execute.assert_any_call(
            'UPDATE "Task" SET status = %s, error = %s WHERE id = %s',
            ('FAILED', expected_error_payload, task_id)
        )
        
        mock_conn.commit.assert_called() # Should be called after setting the failure state
        mock_conn.close.assert_called_once()

    @patch('aiservice.worker.get_db_connection')
    def test_no_pending_tasks(self, mock_get_db_connection):
        """
        Tests that nothing happens when there are no pending tasks.
        """
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db_connection.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Mock no task being found
        mock_cur.fetchone.return_value = None

        process_single_task()

        # Verify we selected tasks but did not update anything
        mock_cur.execute.assert_called_once_with(
            """
                    BEGIN;
                    SELECT id, payload FROM "Task" WHERE status = 'PENDING' ORDER BY "createdAt" ASC LIMIT 1 FOR UPDATE SKIP LOCKED;
                """
        )
        # Ensure no status updates were attempted
        self.assertEqual(mock_cur.execute.call_count, 1)
        mock_conn.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()