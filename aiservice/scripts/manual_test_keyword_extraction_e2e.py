#!/usr/bin/env python
# coding: utf-8
"""
End-to-end test script for the GeneralPurposeKeywordExtractionCrew.
Accepts a JSON file path via command-line argument for flexibility.

Example Usage:
  python -m aiservice.scripts.test_keyword_extraction_e2e --e2e-json-file /path/to/your/output.json
"""
import os
import sys
import json
import argparse 
from typing import List, Dict, Any
import asyncio

# --- Python Path Setup (REMOVED as we will try running with -m) ---
# SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# PROJECT_ROOT_FOR_IMPORTS = os.path.dirname(os.path.dirname(SCRIPT_DIR))
# 
# if PROJECT_ROOT_FOR_IMPORTS not in sys.path:
#     sys.path.append(PROJECT_ROOT_FOR_IMPORTS)
# 
# print(f"DEBUG: PROJECT_ROOT_FOR_IMPORTS: {PROJECT_ROOT_FOR_IMPORTS}")
# print(f"DEBUG: sys.path after modification: {sys.path}")
# --- End Python Path Setup ---

# Debug prints to understand the execution environment for imports
print(f"DEBUG: Script __file__: {__file__}")
print(f"DEBUG: Current Working Directory: {os.getcwd()}")
print(f"DEBUG: sys.path before aiservice import: {sys.path}")

# Imports should work if script is run as a module from project root
# print(f"DEBUG: Current sys.path before aiservice import: {sys.path}") # This was the old debug line
from aiservice.app.config.logging_config import get_logger
from aiservice.app.crews.keyword_extraction_crew import GeneralPurposeKeywordExtractionCrew
from aiservice.app.models.orchestration_models import ContentBlock

# Initialize logger for this script
logger = get_logger("__main__")

def load_content_blocks_from_json(file_path: str) -> List[Dict[str, Any]]:
    """Loads content blocks from a JSON file that contains an 'original_content_blocks' key."""
    logger.info(f"Loading content blocks from: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'original_content_blocks' in data and isinstance(data['original_content_blocks'], list):
            logger.info(f"Successfully loaded {len(data['original_content_blocks'])} blocks.")
            return data['original_content_blocks'] 
        else:
            logger.error(f"'original_content_blocks' key not found or not a list in {file_path}")
            return []
    except FileNotFoundError:
        logger.error(f"Test data file not found: {file_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading test data: {e}")
        return []

def run_keyword_extraction_test(json_input_path: str):
    logger.info(f"--- Starting Keyword Extraction E2E Test for: {json_input_path} ---")

    raw_content_blocks = load_content_blocks_from_json(json_input_path)

    if not raw_content_blocks:
        logger.error("No content blocks loaded. Aborting test.")
        print("\n--- Keyword Extraction Test FAILED: No content blocks loaded ---")
        return

    logger.info("Initializing GeneralPurposeKeywordExtractionCrew...")
    try:
        keyword_crew = GeneralPurposeKeywordExtractionCrew(content_blocks=raw_content_blocks)
    except Exception as e:
        logger.error(f"Error initializing GeneralPurposeKeywordExtractionCrew: {e}", exc_info=True)
        print(f"\n--- Keyword Extraction Test FAILED: Crew initialization error: {e} ---")
        return

    logger.info("Running keyword extraction crew...")
    try:
        results = keyword_crew.run()
    except Exception as e:
        logger.error(f"Error during keyword_crew.run(): {e}", exc_info=True)
        print(f"\n--- Keyword Extraction Test FAILED: Crew execution error: {e} ---")
        return

    logger.info("\n--- Keyword Extraction Results ---")
    if isinstance(results, list):
        logger.info(f"Successfully extracted {len(results)} keywords:")
        for i, keyword in enumerate(results):
            logger.info(f"  {i+1}. {keyword}")
        print(f"\nSuggested Keywords: {results}")
    elif isinstance(results, str) and results.startswith("Error:"):
        logger.error(f"Keyword extraction failed with an error message: {results}")
        print(f"\n--- Keyword Extraction Test FAILED: {results} ---")
    else:
        logger.warning(f"Keyword extraction returned an unexpected result type or content: {results}")
        print(f"\n--- Keyword Extraction Test COMPLETED WITH UNEXPECTED OUTPUT: {results} ---")
    
    logger.info("---------------------------------")
    print("---------------------------------")

if __name__ == "__main__":
    # Update example usage for -m flag
    # python -m aiservice.scripts.test_keyword_extraction_e2e --e2e-json-file aiservice/scripts/your_file.json (when run from project root)
    parser = argparse.ArgumentParser(description="Run E2E test for Keyword Extraction Crew.")
    parser.add_argument(
        '--e2e-json-file',
        type=str,
        required=True,
        help='Path to the input JSON file containing content blocks (output from orchestrator).'
    )
    args = parser.parse_args()

    test_json_path = args.e2e_json_file

    if not os.path.exists(test_json_path):
        logger.error(f"CRITICAL: Test data file NOT FOUND at: {test_json_path}")
        logger.error("Please ensure the JSON file path provided via --e2e-json-file is correct.")
        print(f"CRITICAL: Test data file NOT FOUND at: {test_json_path}")
    else:
        run_keyword_extraction_test(test_json_path)

    # Example for another test file (if you have one for a different document):
    # test_json_path_2 = os.path.join(SCRIPT_DIR, "e2e_test_output_another_file.json")
    # if os.path.exists(test_json_path_2):
    #     run_keyword_extraction_test(test_json_path_2) 