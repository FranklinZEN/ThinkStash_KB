#!/usr/bin/env python
# coding: utf-8
"""
Defines agents for the General Purpose Title Generation Crew.
Following V2.6 Development Plan - Iteration 1.2.
"""

from crewai import Agent
from langchain_openai import ChatOpenAI # For typing and direct use if needed
from textwrap import dedent
from typing import List, Optional, Any # Added Any
from crewai.tools import BaseTool, tool # Corrected import

# Corrected local imports assuming standard structure relative to 'app'
from aiservice.app.tools.content_processing_tools import FullTextContentExtractorTool
from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool
from aiservice.app.config.settings import Settings
# from ..config.llm_config import get_configured_llm # Use settings to get LLM

class TitleGenerationAgents:
    """Factory class to create agents for title generation."""

    def __init__(self, user_id: Optional[str] = "default_user_id_title_agents"):
        self.user_id = user_id
        self.settings = Settings()
        self.llm = self.settings.get_crew_llm() # Uses Gemini model from settings
        print(f"TitleGenerationAgents initialized with user_id: {self.user_id}")

        # Initialize tools
        self.full_text_extractor_tool = FullTextContentExtractorTool()
        self.optimized_llm_interaction_tool = OptimizedLLMInteractionTool(llm=self.llm)
        
        # Configuration for the agent - can be externalized
        self.title_crafter_model_name = "gemini-2.5-flash" # As per plan
        self.title_crafter_temperature = 0.2 # Default, can be tuned
        self.title_crafter_max_tokens = 100 # Default for a title, can be tuned


    def title_crafting_agent(self) -> Agent:
        """
        Creates the TitleCraftingAgent.
        This agent analyzes a content extract and generates a title using an LLM.
        """
        return Agent(
            role="Expert Title Writer",
            goal="Generate a concise, informative, and engaging title (under 15 words) for pre-processed text content "
                 "using the OptimizedLLMInteractionTool. Ensure the generated title is relevant to the input text. "
                 "If the input text is empty or seems to be an error message, indicate that no title can be generated.",
            backstory=(
                "As an Expert Title Writer, you possess a keen ability to distill complex information into "
                "captivating and precise titles. You understand the importance of a title in grabbing attention "
                "and conveying the essence of the content. You are now tasked with focusing solely on title "
                "creation based on text provided to you, using your LLM capabilities efficiently."
            ),
            tools=[self.full_text_extractor_tool, self.optimized_llm_interaction_tool], # Add the extractor tool
            llm=self.llm,
            verbose=True,
            allow_delegation=False, # No delegation needed for this focused task
            memory=False # No memory needed for this single-shot task based on direct input
        )

if __name__ == '__main__':
    # Example of how to instantiate and get an agent
    agents_factory = TitleGenerationAgents(user_id="test_user_title_agent")
    title_agent = agents_factory.title_crafting_agent()
    print(f"Title Agent Created: {title_agent.role}")
    # Now LLM and Tools should be configured
    print(f"Title Agent LLM: {title_agent.llm}")
    print(f"Title Agent Tools: {[tool.name for tool in title_agent.tools]}")
    print("Agent ready for integration into a crew.")

# To ensure the AppSettings and get_crew_llm() are working as expected,
# you might need to ensure that AppSettings is correctly loading your environment variables
# for GEMINI_API_KEY and any other relevant configurations.
# Example (conceptual, actual setup depends on your AppSettings implementation):
# settings = AppSettings()
# gemini_llm = settings.get_crew_llm()
# print(f"LLM for TitleGenerationAgents: {gemini_llm}") 