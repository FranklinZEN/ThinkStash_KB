import sys
import os
from pathlib import Path

# Adjust sys.path to include the project root directory (aiservice)
# This allows for imports like `from app.agents...`
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.agents.orchestration_agent import OrchestrationAgent
from app.models.orchestration_models import OrchestrationInput

def run_test_case(agent: OrchestrationAgent, test_name: str, source_type: str, source_identifier: str, processing_level: str = "full_content"):
    print(f"--- Running Test Case: {test_name} ---")
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
    # Instantiate the agent - tools are initialized within the agent currently
    orchestration_agent = OrchestrationAgent()

    # Define file paths relative to the workspace root (assuming /e:/ThinkStash/ is workspace)
    # The user provided these files under "documentation/AI Agents Testing File/"
    # The script is in "aiservice/scripts/", so we need to adjust paths accordingly or use absolute.
    # For simplicity, we'll construct paths relative to the project_root identified earlier.
    # project_root for this script is /e:/ThinkStash/aiservice/
    # The test files are in /e:/ThinkStash/documentation/AI Agents Testing File/
    
    # To make this work correctly, we need to go up one level from project_root (aiservice) to ThinkStash, then down to documentation.
    workspace_root = project_root.parent 
    test_file_dir = workspace_root / "documentation" / "AI Agents Testing File"

    # Test cases
    test_cases = [
        ("PDF File", "pdf", str(test_file_dir / "a-data-leaders-technical-guide-to-scaling-gen-ai.pdf")),
        ("MD File", "md", str(test_file_dir / "Product Requirement Document - Knowledge Card System v3.8.md")),
        ("DOCX File", "docx", str(test_file_dir / "Fulfillment Planning Deep Research Paper.docx")),
        ("TXT File", "txt", str(test_file_dir / "Test.txt")),
        ("URL - HTML", "url", "https://www.google.com"),
        ("URL - PDF Content", "url", "https://www.africau.edu/images/default/sample.pdf"),
        ("URL - Non-existent", "url", "http://nonexistenturl12345zzzz.com"),
        ("URL - No Scheme", "url", "example.com/somepage"),
        ("File - Non-existent", "pdf", "non_existent_file.pdf"),
        ("File - Unknown Extension by source_type hint", "xyz_ext", "documentation/AI Agents Testing File/Test.txt"), # Tool should still try to classify based on content/path if is_file is not forced
        ("URL - Image PNG", "url", "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"),
        ("URL - Text Only Processing", "url", "https://example.com", "text_only"),
        ("PDF File - Text Only Processing", "pdf", str(test_file_dir / "a-data-leaders-technical-guide-to-scaling-gen-ai.pdf"), "text_only"),
    ]

    for name, s_type, s_id, *plevel in test_cases:
        proc_level = plevel[0] if plevel else "full_content"
        # Check if the file exists for local file test cases before running
        if s_type in ["pdf", "md", "docx", "txt"] and not s_id.startswith("http"):
             if not Path(s_id).exists():
                 print(f"--- SKIPPING Test Case: {name} ---")
                 print(f"File not found: {s_id}")
                 print(f"Please ensure the file exists at the specified path relative to your workspace root or that the path is correct.")
                 print("--- Test Case End --- \n")
                 continue
        run_test_case(orchestration_agent, name, s_type, s_id, proc_level)

    print("\n--- All Tests Attempted ---")
    print(f"NOTE: If you saw 'File not found' for local files, ensure they are at the correct path relative to the workspace root:")
    print(f"Workspace root assumed based on script location: {workspace_root}")
    print(f"Test files expected in: {test_file_dir}") 