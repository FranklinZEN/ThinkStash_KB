# File: aiservice/test_agent.py

# import asyncio # Not strictly needed for this version
from app.agents.content_acquisition_agent import ContentAcquisitionAgent
from app.models.content_models import AcquiredContent
import json
import os

# --- IMPORTANT: Configure API Keys if your LLM/CrewAI setup needs them ---
# If you have OpenAI API keys and want to avoid potential prompts or errors
# if CrewAI tries to initialize a default LLM, you can set them here.
# Otherwise, the ContentAcquisitionAgent is designed to work without directly using an LLM for its logic.
# Example:
# os.environ["OPENAI_API_KEY"] = "your_actual_openai_api_key"
# os.environ["OPENAI_MODEL_NAME"] = "gpt-4o-mini" # Or your preferred model

test_url = "chrome-extension://efaidnbmnnnibpcajpcglclefindmkaj/https://sdgs.un.org/sites/default/files/2022-06/3-Pager%20Information%20Brief__May%202022%20.pdf"

def run_agent_test():
    print(f"Instantiating ContentAcquisitionAgent...")
    # The agent's __init__ passes tools=[WebContentFetcherTool(), FileContentExtractorTool()]
    # verbose=True helps in seeing CrewAI logs if any were to occur.
    agent = ContentAcquisitionAgent(verbose=True)

    print(f"Attempting to acquire content from URL: {test_url}")

    source_details = {"url": test_url}

    try:
        acquired_data: AcquiredContent = agent.acquire_content(source_type="url", source_data=source_details)

        print("\n--- Agent Output ---")
        # Use .model_dump_json() for Pydantic V2, or .json() for Pydantic V1
        try:
            print(acquired_data.model_dump_json(indent=2))
        except AttributeError:
            print(acquired_data.json(indent=2)) # Fallback for Pydantic V1

        print(f"\nStatus: {acquired_data.status}")
        if acquired_data.error_message:
            print(f"Error Message: {acquired_data.error_message}")

        print(f"\nPage Title: {acquired_data.page_title}")

        if acquired_data.extracted_text:
            print(f"\nExtracted Text (first 1000 chars):\n{acquired_data.extracted_text[:1000]}...") # Increased char count
        else:
            print("\nNo text extracted.")

        if acquired_data.image_references:
            print(f"\nFound {len(acquired_data.image_references)} image references:")
            for i, img_ref in enumerate(acquired_data.image_references[:5]): # Print first 5
                print(f"  Image {i+1}:")
                # Check type using the 'type' field as defined in ImageRefUrl/ImageRefData
                if hasattr(img_ref, 'type') and img_ref.type == "url":
                    print(f"    Type: URL")
                    print(f"    URL: {getattr(img_ref, 'url', 'N/A')}")
                elif hasattr(img_ref, 'type') and img_ref.type == "data":
                    print(f"    Type: Data (bytes)")
                    print(f"    Filename Hint: {getattr(img_ref, 'filename_hint', 'N/A')}")
                    print(f"    MIME Type Hint: {getattr(img_ref, 'mime_type_hint', 'N/A')}")
                    if hasattr(img_ref, 'data_bytes'):
                        print(f"    Size (bytes): {len(img_ref.data_bytes)}")
                else: # Fallback if type field is missing or different (shouldn't happen with Pydantic)
                    if hasattr(img_ref, 'url'):
                        print(f"    Type: URL (assumed by field presence)")
                        print(f"    URL: {getattr(img_ref, 'url', 'N/A')}")
                    elif hasattr(img_ref, 'data_bytes'):
                        print(f"    Type: Data (bytes) (assumed by field presence)")
                        if hasattr(img_ref, 'data_bytes'):
                            print(f"    Size (bytes): {len(img_ref.data_bytes)}")
                print(f"    Alt Text: {getattr(img_ref, 'alt_text', 'N/A')}")
                print(f"    Caption: {getattr(img_ref, 'caption', 'N/A')}")
        else:
            print("\nNo image references found.")

    except Exception as e:
        print(f"An error occurred during agent execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_agent_test()