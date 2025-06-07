import sys
from pathlib import Path
import json # For pretty printing dicts

# Adjust sys.path to include the project root directory
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from aiservice.app.agents.web_url_acquisition_agent import WebURLContentAcquisitionAgent
from aiservice.app.models.web_acquisition_models import WebAcquisitionInput
from aiservice.app.tools.web_tools import WebContentFetcherTool
from aiservice.app.tools.utility_tools import DataStoreAccessTool # For initializing agent

def run_web_test_case(agent: WebURLContentAcquisitionAgent, test_name: str, url: str, processing_level: str = "full_content"):
    print(f"--- Running Web Test Case: {test_name} ---")
    input_data = WebAcquisitionInput(
        url=url,
        processing_level=processing_level
    )
    print(f"Input: {input_data.model_dump_json(indent=2)}")

    # The agent's method directly returns the Pydantic model instance
    output_model = agent.execute_comprehensive_url_processing(input_data)
    
    print(f"Output Model Status: {output_model.status}")
    print(f"Page Title: {output_model.page_title_from_web}")
    print(f"Final URL: {output_model.final_url_after_redirects}")
    print(f"Text Content Ref: {output_model.extracted_text_content_ref}")
    print(f"Image List Ref: {output_model.extracted_image_url_list_with_ids_ref}")
    print(f"PDF Ref: {output_model.downloaded_pdf_path_ref}")
    print(f"Is Paywalled: {output_model.is_paywalled}")
    if output_model.error_message:
        print(f"Error Message: {output_model.error_message}")
    
    # If data was stored, let's try to retrieve and print a snippet (optional)
    if output_model.extracted_text_content_ref:
        text_content = agent.data_store_tool._run(action="get", key=output_model.extracted_text_content_ref)
        print(f"  Retrieved Text Snippet (first 200 chars): {text_content[:200] if text_content else 'N/A'}...")
    
    if output_model.extracted_image_url_list_with_ids_ref:
        image_list = agent.data_store_tool._run(action="get", key=output_model.extracted_image_url_list_with_ids_ref)
        print(f"  Retrieved Image List (first 2 images): {json.dumps(image_list[:2], indent=2) if image_list else 'N/A'}")

    print("--- Web Test Case End --- \n")

if __name__ == "__main__":
    # This script can now be run manually.
    web_fetcher = WebContentFetcherTool()
    data_store = {}
    data_store_tool_instance = DataStoreAccessTool(data_store=data_store) 
    web_agent = WebURLContentAcquisitionAgent(
        web_content_fetcher_tool=web_fetcher, 
        data_store_tool=data_store_tool_instance
    )
    test_urls = [
        ("Blog Post - DeepLearning.AI", "https://www.deeplearning.ai/the-batch/issue-301/", "full_content"),
        ("News Article - NYT (Paywall Example)", "https://www.nytimes.com/2023/10/26/business/media/new-york-times-earnings.html", "full_content"),
        ("PDF URL", "https://www.africau.edu/images/default/sample.pdf", "full_content"),
    ]
    for name, url, processing_level_str in test_urls:
        run_web_test_case(web_agent, name, url, processing_level_str)
    
    print("\n--- All Web Tests Attempted ---") 