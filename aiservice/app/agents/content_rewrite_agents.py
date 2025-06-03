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
from langchain_community.tools.tavily_search import TavilySearchResults
# from langchain_openai import ChatOpenAI # For direct use if needed, but crew uses its own LLM instance

# Local application imports
from aiservice.app.tools.insight_generation_tools import OptimizedLLMInteractionTool, FastContentBlockProcessorTool # Corrected import
from aiservice.app.config.settings import Settings # Corrected import
# from ..config.llm_config import get_configured_llm # Use settings to get LLM
from aiservice.app.config.llm_config import get_configured_llm # Corrected import
from aiservice.app.config.logging_config import get_logger # Added missing import

# Models - If agents directly interact with Pydantic models for type hinting or data shaping
from aiservice.app.models.orchestration_models import ContentBlock # Corrected import

# Get a logger instance
logger = get_logger(__name__)

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
            role="AI Detailed Content Analysis and High-Fidelity Summarization Specialist",
            goal=dedent(f"""\
                Adhere meticulously to all criteria outlined in the task description to produce a high-fidelity, detailed, and accurate summary.
                This includes: achieving minimum 90% information retention, preserving key data points and nuances, using original terminology,
                maintaining contextual integrity, and correctly integrating CRUCIAL images using the specified '[IMAGE: <image_id_ref_value>]' placeholder format.
                You must use your 'Optimized LLM Interaction Tool' for this, ensuring the 'temperature' is {self.summarizer_temperature} and 'max_tokens' is {self.summarizer_max_tokens}.
                Your final output MUST be a Pydantic object of type 'SummarizerTaskOutput', containing the 'summary_text' as a single string.
                """),
            backstory=dedent("""\
                You are an advanced AI language model, a specialist in deep content analysis and synthesis with extreme fidelity.
                Your expertise lies in deconstructing complex information, identifying critical elements, and reconstructing them into comprehensive yet concise summaries.
                You have an exceptional ability to retain a high percentage of information, maintain factual accuracy, and preserve the nuances of the original text.
                Furthermore, you are adept at contextually integrating visual elements (images) seamlessly into textual summaries using precise placeholder notations as instructed.
                You operate with a commitment to accuracy, detail, and adherence to specific formatting and output requirements.
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