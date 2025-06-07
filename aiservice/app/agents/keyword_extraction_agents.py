#!/usr/bin/env python
# coding: utf-8
"""
Defines the agent(s) responsible for keyword extraction.
"""

from crewai import Agent
# from aiservice.app.tools.content_processing_tools import FullTextContentExtractorTool # Not directly used by KeywordExtractionAgents class
# from aiservice.app.tools.llm_interaction_tools import OptimizedLLMInteractionTool # Not directly used by KeywordExtractionAgents class
from langchain_openai import ChatOpenAI # Or your preferred LLM provider
from aiservice.app.tools.formatting_tools import KeywordToTagFormatterTool
# from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool # Corrected import path
from aiservice.app.config.settings import Settings # Corrected import
# from ..config.llm_config import get_configured_llm # Use settings to get LLM

# Unused tool initializations - remove if not needed globally for other purposes in this file
# full_text_extractor = FullTextContentExtractorTool()
# llm_tool = OptimizedLLMInteractionTool()

class KeywordExtractionAgents:
    def __init__(self, llm_client=None):
        # If no llm_client is provided, a default can be instantiated or an error raised.
        # For this structure, it's better if the LLM is injected when the crew is defined.
        self.llm = llm_client if llm_client else ChatOpenAI(model_name="gemini-2.5-flash", temperature=0.7)
        # Note: Actual model name might be 'gemini-2.5-flash-preview-05-20' based on logs.
        # Adjust temperature and other parameters as needed for keyword extraction.

    def keyword_identifier_agent(self) -> Agent:
        """
        Agent responsible for:
        1. Analyzing text to identify 5-7 key terms or concepts.
        2. Formatting these terms into standardized tags using KeywordToTagFormatterTool.
        """
        return Agent(
            role="Expert Keyword Analyst and Subject Matter Specialist",
            goal=(
                "Analyze the provided text to deeply understand its core concepts, themes, and arguments. "
                "Your goal is to identify 5-7 highly specific and relevant keywords or keyphrases that capture the very essence of the content. "
                "Avoid generic, high-level terms. Instead, focus on the most unique and defining concepts presented in the text. "
                "After identifying these specific terms, you MUST format them into standardized tags using your available tools."
            ),
            backstory=(
                "As an Expert Keyword Analyst, you are more than a simple term extractor; you are a subject matter expert with a profound ability to discern the crucial topics within any text. "
                "You are skilled at distilling complex information down to its most specific and meaningful keywords, ignoring superficial or overly broad terms. "
                "You understand that the best keywords are those that would help an expert in the field quickly grasp the content's primary focus. "
                "You are meticulous in formatting these keywords correctly as standardized tags."
            ),
            tools=[
                KeywordToTagFormatterTool()
            ],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            # Memory is not explicitly required for this agent if each task is self-contained with full text.
            memory=False 
        )

# Example of how this agent might be instantiated and used (for conceptual understanding):
# if __name__ == '__main__':
#     # This is a simplified llm_client for example purposes.
#     # In a real scenario, it would be properly initialized and configured.
#     from app.config.llm_config import get_default_text_llm
#     llm_instance = get_default_text_llm() # Assuming this function returns your configured Gemini client

#     agents = KeywordExtractionAgents(llm_client=llm_instance)
#     keyword_agent = agents.keyword_identifier_agent()

#     # To test the agent, you would typically create a Task and a Crew.
#     # The agent's prompt for the LLM would be part of the Task description.
#     # Example direct tool usage (not how agent uses it directly but how tool works):
#     # formatter = KeywordToTagFormatterTool()
#     # raw_kws = ["artificial intelligence", "data science", "customer experience optimization"]
#     # formatted_kws = formatter.run(raw_kws)
#     # print(f"Raw: {raw_kws}")
#     # print(f"Formatted: {formatted_kws}")
#     # Expected: Formatted: ['#AI', '#DataScience', '#CustomerExperienceOptimization']

#     print(f"Agent '{keyword_agent.role}' is configured and ready.")
#     print(f"Agent tools: {[tool.name for tool in keyword_agent.tools]}")

# Example of how to instantiate the agent (for testing or crew assembly)
# keyword_agent = KeywordIdentificationAgent() 