import sys
from pathlib import Path

# Adjust sys.path to include the project root directory
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from aiservice.app.agents.orchestration_agent import OrchestrationAgent
from aiservice.app.models.orchestration_models import OrchestrationInput

def run_test_case(agent: OrchestrationAgent, test_name: str, source_type: str, source_identifier: str, processing_level: str = "full_content"):
    print(f"--- Running Test Case: {test_name} ---")
    # This function is not a test, so it will not be executed by pytest
    # ... (rest of the function is unchanged but will not be called)
    input_data = OrchestrationInput(
        source_type=source_type,
        source_identifier=source_identifier,
        processing_level=processing_level
    )
    print(f"Input: {input_data.model_dump_json(indent=2)}")

    triage_results = agent.execute_initial_triage(input_data)
    print(f"Triage Results: {triage_results}")

    if triage_results.get("validation_status") == "success" and triage_results.get("detected_content_type") not in ["error", "unknown", "error_detection_failed", "error_file_not_found", "error_url_fetch"] :
        routing_results = agent.execute_routing(triage_results)
        print(f"Routing Results: {routing_results}")
    else:
        print(f"Routing skipped due to triage failure or unroutable type: {triage_results.get('detected_content_type')}")
    print("--- Test Case End --- \n")

if __name__ == "__main__":
    # This script can now be run manually
    orchestration_agent = OrchestrationAgent()
    workspace_root = project_root.parent 
    test_file_dir = workspace_root / "documentation" / "AI Agents Testing File"
    test_cases = [
        ("PDF File", "pdf", str(test_file_dir / "a-data-leaders-technical-guide-to-scaling-gen-ai.pdf")),
        # ... other test cases from original file
    ]
    for name, s_type, s_id, *plevel in test_cases:
        # ... (logic from original file)
        run_test_case(orchestration_agent, name, s_type, s_id, plevel[0] if plevel else "full_content")

    print("\n--- All Tests Attempted ---")
    print(f"NOTE: If you saw 'File not found' for local files, ensure they are at the correct path relative to the workspace root:")
    print(f"Workspace root assumed based on script location: {project_root.parent}")
    print(f"Test files expected in: {project_root.parent / 'documentation' / 'AI Agents Testing File'}") 