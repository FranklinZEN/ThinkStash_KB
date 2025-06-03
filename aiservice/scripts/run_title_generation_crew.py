import uuid
import os
import sys
from typing import List
import asyncio

# Add project root to sys.path to allow direct script execution
# This assumes the script is in aiservice/scripts and project root is aiservice's parent
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from aiservice.app.models.orchestration_models import ContentBlock
from aiservice.app.crews.title_generation_crew import GeneralPurposeTitleGenerationCrew

# Helper to create ContentBlock instances for the run script
def create_sample_content_blocks() -> List[ContentBlock]:
    """Creates a list of sample ContentBlock objects for testing."""
    blocks = [
        ContentBlock(
            block_id=str(uuid.uuid4()), tmp_id=str(uuid.uuid4()), user_id="run_script_user", document_id="doc_script_test",
            type="heading", order_index=0, content="The Wonders of Modern Technology", level=1
        ),
        ContentBlock(
            block_id=str(uuid.uuid4()), tmp_id=str(uuid.uuid4()), user_id="run_script_user", document_id="doc_script_test",
            type="text", order_index=1, 
            content="Modern technology has revolutionized the way we live, work, and interact. From smartphones to artificial intelligence, the pace of innovation continues to accelerate, offering unprecedented opportunities and challenges."
        ),
        ContentBlock(
            block_id=str(uuid.uuid4()), tmp_id=str(uuid.uuid4()), user_id="run_script_user", document_id="doc_script_test",
            type="list", order_index=2, 
            items=["Smartphones and Mobile Computing", "Artificial Intelligence and Machine Learning", "Internet of Things (IoT)", "Renewable Energy Solutions"],
            ordered=False
        ),
        ContentBlock(
            block_id=str(uuid.uuid4()), tmp_id=str(uuid.uuid4()), user_id="run_script_user", document_id="doc_script_test",
            type="text", order_index=3, 
            content="These advancements promise a future of enhanced connectivity, efficiency, and sustainability."
        )
    ]
    return blocks

if __name__ == "__main__":
    print("Starting title generation crew run script...")
    
    sample_blocks = create_sample_content_blocks()
    print(f"Created {len(sample_blocks)} sample content blocks.")

    # Instantiate the crew
    # The crew should use the actual LLM as configured in llm_config.py via TitleGenerationAgents
    title_generation_service = GeneralPurposeTitleGenerationCrew(user_id="script_runner")
    print("GeneralPurposeTitleGenerationCrew instantiated.")

    print("\nRunning title generation crew...")
    try:
        suggested_title = title_generation_service.run(content_blocks=sample_blocks)
        print("\n--------------------------------------------------")
        print(f"Suggested Title by Crew: {suggested_title}")
        print("--------------------------------------------------")
    except Exception as e:
        print(f"\nAn error occurred while running the title generation crew: {e}")
        import traceback
        traceback.print_exc()

    print("\nTitle generation crew run script finished.")

# To run this script (assuming you are in the project root, e.g., /e%3A/ThinkStash/):
# Ensure necessary environment variables are set for LLM access (e.g., GOOGLE_API_KEY)
# python aiservice/scripts/run_title_generation_crew.py 