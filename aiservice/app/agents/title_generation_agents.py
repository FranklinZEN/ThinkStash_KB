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
from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool, FastContentBlockProcessorTool

# LLM Configuration
from aiservice.app.config.llm_config import get_configured_llm

class TitleGenerationAgents:
    """Factory class to create agents for title generation."""

    def __init__(self, user_id: Optional[str] = "default_user_id_title_agents"):
        self.user_id = user_id
        self.llm = get_configured_llm() 
        print(f"TitleGenerationAgents initialized with user_id: {self.user_id}")

        # Initialize tools
        self.optimized_llm_tool = OptimizedLLMInteractionTool(llm_client=self.llm)
        self.fast_content_processor_tool = FastContentBlockProcessorTool(user_id=self.user_id)
        
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
            goal=dedent("""
                Analyze the provided content extract and generate a concise, informative,
                and engaging title that accurately reflects the main topic of the content.
                The title should be suitable for a knowledge card.
                """),
            backstory=dedent("""
                You are a master wordsmith, renowned for your ability to distill the essence
                of any piece of content into a compelling title. You understand the nuances
                of language and how to capture attention while maintaining accuracy. Your titles
                are short, punchy, and highly relevant.
                """),
            verbose=True,
            memory=False, 
            llm=self.llm, # Pass the configured LLM
            tools=[self.optimized_llm_tool, self.fast_content_processor_tool], # Pass instantiated tools
            allow_delegation=False,
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