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
from textwrap import dedent # Added missing import
import uuid

# Import tools. Adjust path if necessary.
from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool, FastContentBlockProcessorTool

# LLM Configuration (using the shared configuration)
from aiservice.app.config.llm_config import get_configured_llm

# Actual ContentBlock import
from aiservice.app.models.orchestration_models import ContentBlock

class ContentRewriteAgents:
    """Factory class or container for creating and configuring content rewrite agents."""

    def __init__(self, user_id: Optional[str] = "default_user_id_agents", document_id_for_output_blocks: Optional[str] = None):
        self.llm = get_configured_llm() # Now configured for ChatGoogleGenerativeAI
        self.user_id = user_id # Store user_id
        self.document_id_for_output_blocks = document_id_for_output_blocks if document_id_for_output_blocks else str(uuid.uuid4()) # Ensure it has a value
        print(f"ContentRewriteAgents initialized with user_id: {self.user_id}, document_id_for_output_blocks: {self.document_id_for_output_blocks}") # For debugging
        self.optimized_llm_tool = OptimizedLLMInteractionTool(llm_client=self.llm) 
        self.content_processor_tool = FastContentBlockProcessorTool(
            user_id=self.user_id, 
            document_id=self.document_id_for_output_blocks
        )
        self.summarizer_temperature = 0.0
        self.summarizer_max_tokens = 500000

    def summarization_agent(self) -> Agent:
        """
        Agent responsible for making a single, highly optimized LLM call 
        to summarize the text provided by the ContentPrepperAgent.
        """
        return Agent(
            role="Expert Summarizer",
            goal=dedent(f"""\
                Generate a concise, high-quality summary of the provided text.
                You must use your 'Optimized LLM Interaction Tool' for this.
                When using the tool, you must set the 'temperature' parameter to {self.summarizer_temperature} and the 'max_tokens' parameter to {self.summarizer_max_tokens}.
                Your final output MUST be a Pydantic object of type 'SummarizerTaskOutput' containing the 'summarized_text' as a string.
                """),
            backstory=dedent("""\
                You are a world-class summarization expert, capable of distilling complex information into clear, concise summaries.
                You are adept at following precise instructions on structuring your output and referencing supplementary materials like images.
                You aim for efficiency and accuracy in one go.
                """),
            tools=[self.optimized_llm_tool],
            llm=self.llm,
            allow_delegation=False,
            verbose=True,
            max_iter=1 # Force single iteration
        )

    def output_constructor_agent(self) -> Agent:
        """
        Agent responsible for reconstructing the final content blocks from summarized text and image metadata.
        This agent should ONLY use its tool and return the direct output.
        """
        return Agent(
            role="Output Reconstruction Architect",
            goal=(
                "Given summarized text, a list of essential image metadata, and a document ID, "
                "use the FastContentBlockProcessorTool with the 'reconstruct_content_from_summary' operation "
                "to create a new list of ContentBlock objects. You MUST use the tool and output its result directly."
            ),
            backstory=(
                "You are a specialized agent focused on meticulously reconstructing structured content. "
                "You do not engage in creative writing or summarization yourself. Your sole function is to "
                "accurately process inputs through your designated tool and return the tool's direct output."
            ),
            tools=[self.content_processor_tool],
            llm=self.llm, # Assign the configured LLM to prevent OpenAI client instantiation issues
            allow_delegation=False,
            verbose=True,
        )

# Example usage (for testing or integration into a crew)
if __name__ == '__main__':
    agents_factory = ContentRewriteAgents()
    summarizer = agents_factory.summarization_agent()
    constructor = agents_factory.output_constructor_agent()

    print(f"Created agent: {summarizer.role}")
    print(f"Created agent: {constructor.role}") 