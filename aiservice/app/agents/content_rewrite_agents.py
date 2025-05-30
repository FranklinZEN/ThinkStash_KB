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

    def __init__(self):
        self.llm = get_configured_llm() # Now configured for ChatGoogleGenerativeAI
        self.optimized_llm_tool = OptimizedLLMInteractionTool(llm_client=self.llm) 
        self.content_processor_tool = FastContentBlockProcessorTool()

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
                "Parse the LLM's summarized output. Reconstruct the final list of content blocks by "
                "integrating the summarized text with the original essential image blocks, based on the "
                "LLM output or image references. Ensure accurate block reconstruction and logical flow."
            ),
            backstory=(
                "You are a meticulous architect of digital content. You can take raw textual output from an LLM "
                "and precisely reconstruct it into well-structured content blocks, seamlessly integrating "
                "images and ensuring a polished final product. Speed and precision are your hallmarks."
            ),
            llm=None, # This agent uses tools only, no LLM calls needed for output construction.
            tools=[self.content_processor_tool], 
            allow_delegation=False,
            verbose=True,
            memory=False
        )

# Example usage (for testing or integration into a crew)
if __name__ == '__main__':
    agents_factory = ContentRewriteAgents()
    summarizer = agents_factory.summarization_agent()
    constructor = agents_factory.output_constructor_agent()

    print(f"Created agent: {summarizer.role}")
    print(f"Created agent: {constructor.role}") 