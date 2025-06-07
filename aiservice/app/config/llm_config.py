#!/usr/bin/env python
# coding: utf-8
"""Configuration and utility functions for initializing LLMs for CrewAI, using OpenAI library for Gemini."""

from typing import Any, Optional, Union, Dict, Literal
from aiservice.app.config.settings import settings # Corrected import
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field, validator

# Attempt to import the LangChain OpenAI LLM wrapper
# This requires `langchain-openai` to be installed.
try:
    from langchain_openai import ChatOpenAI
    LANGCHAIN_OPENAI_INSTALLED = True
except ImportError:
    LANGCHAIN_OPENAI_INSTALLED = False
    ChatOpenAI = None # Placeholder if not installed

# LLM client variable, can be initialized once
_llm_client = None

def get_configured_llm():
    """
    Initializes and returns the configured LLM client.
    Prioritizes Gemini via OpenAI compatibility layer if configured.
    """
    global _llm_client
    if _llm_client is not None:
        return _llm_client

    if settings.use_gemini_via_openai_compatibility:
        print("Attempting to initialize Gemini via OpenAI compatibility layer.")
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found for OpenAI compatibility mode.")
        if not settings.gemini_text_model_compat:
            raise ValueError("GEMINI_TEXT_MODEL_COMPAT not found for OpenAI compatibility mode.")
        if not settings.gemini_compatibility_base_url:
            raise ValueError("GEMINI_COMPATIBILITY_BASE_URL not found for OpenAI compatibility mode.")

        try:
            print(f"  Base URL: {settings.gemini_compatibility_base_url}")
            print(f"  Model: {settings.gemini_text_model_compat}")
            print(f"  API Key: ...{settings.gemini_api_key[-4:]}")
            
            _llm_client = ChatOpenAI(
                model_name=settings.gemini_text_model_compat,
                openai_api_key=settings.gemini_api_key,
                openai_api_base=settings.gemini_compatibility_base_url,
                temperature=0.5, # Default temperature
                # max_tokens=None, # Let the model decide or set explicitly if needed
            )
            print("Successfully initialized ChatOpenAI for Gemini compatibility.")
        except Exception as e:
            print(f"Error initializing ChatOpenAI for Gemini compatibility: {e}")
            raise
    elif settings.openai_api_key: # Fallback to direct OpenAI if that key is present and compatibility is off
        print("Attempting to initialize direct OpenAI LLM.")
        try:
            _llm_client = ChatOpenAI(
                model_name=settings.default_llm_model, # This would be an OpenAI model name like "gpt-3.5-turbo"
                openai_api_key=settings.openai_api_key,
                temperature=0.5
            )
            print(f"Successfully initialized direct ChatOpenAI with model: {settings.default_llm_model}")
        except Exception as e:
            print(f"Error initializing direct ChatOpenAI: {e}")
            raise
    else:
        raise ValueError("LLM configuration error: No suitable API key or strategy found. Check .env and settings.")

    return _llm_client

# To explicitly clear/reset the client, e.g., for testing or re-configuration
def reset_llm_client():
    global _llm_client
    _llm_client = None

def get_configured_llm_google():
    """Initializes and returns the configured LLM client (Gemini)."""
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables or .env file.")
    
    # Configure for Gemini using ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model=settings.default_llm_model, # e.g., "gemini-1.5-pro-latest" or "gemini-pro"
        google_api_key=settings.google_api_key,
        temperature=0.5, # Default temperature, can be overridden in tool/agent calls
        # convert_system_message_to_human=True # May be needed for some prompt structures, test this.
    )
    # print(f"Successfully initialized ChatGoogleGenerativeAI for model: {settings.default_llm_model}") # Optional: for debugging
    return llm

# Example of how an agent/crew might get the LLM:
# from aiservice.app.config.llm_config import get_configured_llm
# llm_instance = get_configured_llm()
# if llm_instance:
#     my_crew = MyCrew(llm=llm_instance)
# else:
#     # Handle LLM initialization failure
#     print("Failed to initialize LLM for the crew.") 