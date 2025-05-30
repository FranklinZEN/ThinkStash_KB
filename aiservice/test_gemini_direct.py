#!/usr/bin/env python
# coding: utf-8
import os
import sys

# --- BEGIN Python Path Fix ---
# Get the directory of the current script (aiservice)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory of the current script (E:\ThinkStash)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
# Add the project root to the Python path
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# --- END Python Path Fix ---

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from aiservice.app.config.settings import settings

# Load environment variables from .env file in the aiservice directory
# The path fix above ensures that aiservice.app.config.settings can be imported,
# which itself loads the .env from aiservice/.env
# So, an explicit load_dotenv here might be redundant if settings does it, 
# but it's harmless to call it again if it checks for existing vars.
dotenv_path = os.path.join(SCRIPT_DIR, '.env')
load_dotenv(dotenv_path, override=True) # Override ensures this .env takes precedence if loaded elsewhere

api_key = settings.gemini_api_key
model_name_compat = settings.gemini_text_model_compat
base_url_compat = settings.gemini_compatibility_base_url

if not api_key:
    print("Error: GEMINI_API_KEY not found via settings. Ensure it's in .env file.")
    exit()
if not model_name_compat:
    print("Error: GEMINI_TEXT_MODEL_COMPAT not found via settings.")
    exit()
if not base_url_compat:
    print("Error: GEMINI_COMPATIBILITY_BASE_URL not found via settings.")
    exit()

print(f"Using API Key: ...{api_key[-4:]}")
print(f"Using Model (from settings.gemini_text_model_compat): {model_name_compat}")
print(f"Using Base URL (from settings.gemini_compatibility_base_url): {base_url_compat}")

try:
    print("Initializing ChatOpenAI for Gemini compatibility layer...")
    llm = ChatOpenAI(
        model_name=model_name_compat,
        openai_api_key=api_key,
        openai_api_base=base_url_compat,
        temperature=0.5
    )
    print("ChatOpenAI initialized successfully.")

    print("\nAttempting to invoke the LLM...")
    response = llm.invoke("Hello, what is the capital of France?")
    
    print("\nLLM Invocation successful!")
    print("Response:")
    print(response)
    if hasattr(response, 'content'):
        print("\nResponse content:")
        print(response.content)

except Exception as e:
    print(f"\n--- An error occurred ---")
    import traceback
    traceback.print_exc() 