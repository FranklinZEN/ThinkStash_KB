#!/usr/bin/env python
# coding: utf-8
"""
Defines the agents for the Content Rewrite Crew, including:
- ContentPrepperAgent: Prepares content for summarization.
- SummarizationAgent: Interacts with the LLM to summarize content.
- OutputConstructorAgent: Reconstructs content blocks from the LLM output.
"""

from crewai import Agent
from typing import List, Dict, Any, Optional
from pydantic import BaseModel # Added for the removed placeholder if it was used for type hinting Base Agent

# Import tools. Adjust path if necessary.
from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool, FastContentBlockProcessorTool

# LLM Configuration (using the shared configuration)
from aiservice.app.config.llm_config import get_configured_llm

# Actual ContentBlock import
from aiservice.app.models.orchestration_models import ContentBlock

class ContentRewriteAgents:
    """Factory class or container for creating and configuring content rewrite agents."""

    def __init__(self, user_id: Optional[str] = "default_user_id_agents"):
        self.llm = get_configured_llm() # Now configured for ChatGoogleGenerativeAI
        self.user_id = user_id # Store user_id
        print(f"ContentRewriteAgents initialized with user_id: {self.user_id}") # For debugging
        self.optimized_llm_tool = OptimizedLLMInteractionTool(llm_client=self.llm) 
        self.content_processor_tool = FastContentBlockProcessorTool(user_id=self.user_id) # Pass user_id
        self.summarizer_temperature = 0.0
        self.summarizer_max_tokens = 5000

    def summarization_agent(self) -> Agent:
        """
        Agent responsible for making a single, highly optimized LLM call 
        to summarize the text provided by the ContentPrepperAgent.
        """
        return Agent(
            role="Expert Summarizer",
            goal=(
                "Using the provided concatenated text and essential image metadata, generate a concise summary. "
                "The LLM prompt will guide you to refer to images by their identifiers if they are "
                "contextually important for the summary. Aim for a single, fast LLM call that produces "
                "a high-quality summary output."
            ),
            backstory=(
                "You are a world-class summarization expert, capable of distilling complex information "
                "into clear, concise summaries. You are adept at following precise instructions on structuring "
                "your output and referencing supplementary materials like images."
            ),
            llm=self.llm,
            tools=[self.optimized_llm_tool], # Primarily uses the LLM tool
            allow_delegation=False,
            verbose=True,
            memory=False
        )

    def output_constructor_agent(self) -> Agent:
        """
        Agent responsible for parsing the LLM's summarized output and 
        reconstructing the final List[ContentBlock], interspersing images correctly.
        This agent uses Python-only tools and does NOT make LLM calls.
        """
        return Agent(
            role="Content Reconstruction Architect",
            goal=(
                "Your SOLE responsibility is to take a textual summary and optional image metadata, "
                "and then invoke the 'FastContentBlockProcessorTool' using the 'reconstruct_content_from_summary' operation "
                "with this data. The tool will perform the reconstruction into the final list of ContentBlock objects. "
                "DO NOT attempt to generate the ContentBlock list yourself. Your output MUST be the direct result of the tool call."
            ),
            backstory=(
                "You are a meticulous architect specializing in content structures. "
                "You understand that precise formatting is paramount and rely exclusively on specialized tools "
                "to ensure the integrity of the ContentBlock schema. You do not deviate from this process."
            ),
            llm=None, # This agent uses tools only, no LLM calls needed for output construction.
            tools=[self.content_processor_tool],
            allow_delegation=False,
            verbose=True,
            memory=False, # Consider if memory is needed or could interfere - keeping False for now
            return_direct=True
        )

# Example usage (for testing or integration into a crew)
if __name__ == '__main__':
    agents_factory = ContentRewriteAgents()
    summarizer = agents_factory.summarization_agent()
    constructor = agents_factory.output_constructor_agent()

    print(f"Created agent: {summarizer.role}")
    print(f"Created agent: {constructor.role}") 