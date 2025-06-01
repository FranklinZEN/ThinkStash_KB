#!/usr/bin/env python
# coding: utf-8
"""
Defines the agent(s) responsible for keyword extraction.
"""

from crewai import Agent
from aiservice.app.tools.content_processing_tools import FullTextContentExtractorTool
from aiservice.app.tools.llm_interaction_tools import OptimizedLLMInteractionTool
# from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool # Corrected import path

# Initialize tools
full_text_extractor = FullTextContentExtractorTool()
# Assuming OptimizedLLMInteractionTool is configured globally or doesn't need specific init args here
# If it needs specific model name or other params, they should be passed or configured.
llm_tool = OptimizedLLMInteractionTool()

class KeywordIdentificationAgent(Agent):
    """
    An agent specialized in identifying and extracting relevant keywords from a given text.
    It uses a full text extractor to get the content and an LLM interaction tool
    to generate the keywords.
    """
    def __init__(self):
        super().__init__(
            role="Keyword Extraction Specialist",
            goal="Identify and extract 5-7 key terms or concepts that represent the core topics of the provided content. Keywords should be concise and relevant.",
            backstory=(
                "As a seasoned Keyword Extraction Specialist, you have a knack for distilling complex information "
                "into its most essential terms. You understand the nuances of language and can quickly pinpoint "
                "the concepts that best represent any given text. Your goal is to provide a concise yet comprehensive "
                "set of keywords that would be useful for tagging, indexing, or understanding the content's essence."
            ),
            verbose=True,
            allow_delegation=False,
            tools=[full_text_extractor, llm_tool],
            # llm=ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.7) # Example LLM config
            # For Gemini, this would be configured differently, likely via the OptimizedLLMInteractionTool
            # or a specific llm instance passed to the crew.
            # The plan specifies "gemini-2.5-flash" to be used by the crew/tool.
        )

# Example of how to instantiate the agent (for testing or crew assembly)
# keyword_agent = KeywordIdentificationAgent() 