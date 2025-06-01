#!/usr/bin/env python
# coding: utf-8
"""
Defines agents for the General Purpose Title Generation Crew.
Following V2.6 Development Plan - Iteration 1.2.
"""

from crewai import Agent
from textwrap import dedent
from typing import Optional

# Import tools
from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool
from aiservice.app.tools.content_processing_tools import FullTextContentExtractorTool

# LLM Configuration
from aiservice.app.config.llm_config import get_configured_llm

class TitleGenerationAgents:
    """Factory class to create agents for title generation."""

    def __init__(self, user_id: Optional[str] = "default_user_id_title_agents"):
        self.user_id = user_id
        self.llm = get_configured_llm()
        print(f"TitleGenerationAgents initialized with user_id: {self.user_id}")

        # Initialize tools
        self.full_text_extractor_tool = FullTextContentExtractorTool()
        self.optimized_llm_tool = OptimizedLLMInteractionTool(llm_client=self.llm)
        
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
            role="Expert Title Crafter",
            goal=(
                "Analyze the full text content provided (extracted from content blocks) and generate a short, informative, and engaging title "
                "(under 15 words) that accurately reflects the main topic of the content. "
                "You must use the FullTextContentExtractorTool to get the text from content_blocks, and then use the OptimizedLLMInteractionTool with a crafted prompt to generate the title."
            ),
            backstory=(
                "As an Expert Title Crafter, you possess a keen ability to distill complex information into concise and compelling titles. "
                "You understand the importance of a title that grabs attention while accurately representing the core message of the text. "
                "You are adept at identifying key themes and crafting titles that are optimized for clarity and impact. "
                "You methodically use available tools to first extract all text, then use an LLM interaction tool to generate the title based on that text."
            ),
            tools=[
                self.full_text_extractor_tool,
                self.optimized_llm_tool 
            ],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            memory=False # Titles are generated per request, no memory needed
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