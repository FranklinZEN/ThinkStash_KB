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
                Adhere meticulously to all criteria outlined in the task description to produce a high-fidelity, detailed, and stylistically nuanced summary.
                Your goal is to not just summarize, but to rewrite the content in a more compelling and clear manner, while staying true to the original's core message and tone.
                This includes: achieving minimum 90% information retention, preserving key data points and nuances, using original terminology where appropriate,
                maintaining contextual integrity, and correctly integrating CRUCIAL images using the specified '[IMAGE: <image_id_ref_value>]' placeholder format.
                
                IMPORTANT FORMATTING RULE: For structuring the content, use Heading 2 for main sections and Heading 3 for subsections. NEVER use Heading 1.

                You must use your 'Optimized LLM Interaction Tool' for this, ensuring the 'temperature' is {self.summarizer_temperature} and 'max_tokens' is {self.summarizer_max_tokens}.
                Your final output for the task MUST be a single, valid JSON string that conforms to the 'StructuredSummary' format (an object with a 'segments' key, where 'segments' is a list of objects, each having 'type' and either 'content' or 'image_id_ref'), as detailed in the task description.
                """),
            backstory=dedent("""\
                You are an advanced AI language model, a master of stylistic and substantive content analysis. You are a specialist in deep content analysis and synthesis with extreme fidelity.
                Your expertise lies not just in deconstructing complex information, but in understanding the underlying voice, tone, and intent. You identify critical elements and reconstruct them into comprehensive summaries that are not only accurate but also more engaging and context-aware.
                You have an exceptional ability to retain a high percentage of information, maintain factual accuracy, and preserve the nuances and subtleties of the original text.
                Furthermore, you are adept at contextually integrating visual elements (images) seamlessly into textual summaries using precise placeholder notations as instructed.
                You operate with a commitment to accuracy, detail, and adherence to specific formatting and output requirements, always striving to elevate the clarity and impact of the original content.
                """),
            tools=[self.optimized_llm_tool],
            llm=self.llm,
            allow_delegation=False,
            verbose=True,
            max_iter=1 # Force single iteration
        )

    # def output_constructor_agent(self) -> Agent: # Method removed
    #     """ # Method removed
    #     Agent responsible for reconstructing the final content blocks from summarized text and image metadata.
    #     This agent should ONLY use its tool and return the direct output.
    #     """ # Method removed
    #     return Agent( # Method removed
    #         role="Output Reconstruction Architect", # Method removed
    #         goal=( # Method removed
    #             "Given summarized text, a list of essential image metadata, and a document ID, " # Method removed
    #             "use the FastContentBlockProcessorTool with the 'reconstruct_content_from_summary' operation " # Method removed
    #             "to create a new list of ContentBlock objects. You MUST use the tool and output its result directly."
    #         ), # Method removed
    #         backstory=( # Method removed
    #             "You are a specialized agent focused on meticulously reconstructing structured content. " # Method removed
    #             "You do not engage in creative writing or summarization yourself. Your sole function is to " # Method removed
    #             "accurately process inputs through your designated tool and return the tool's direct output."
    #         ), # Method removed
    #         tools=[self.content_processor_tool], # Method removed
    #         llm=self.llm, # Method removed
    #         allow_delegation=False, # Method removed
    #         verbose=True, # Method removed
    #         max_iter=1 # Method removed
    #     ) # Method removed

# Example usage (for testing or integration into a crew)
if __name__ == '__main__':
    agents_factory = ContentRewriteAgents()
    summarizer = agents_factory.summarization_agent()
    # constructor = agents_factory.output_constructor_agent() # Updated example usage

    print(f"Created agent: {summarizer.role}")
    # print(f"Created agent: {constructor.role}") # Updated example usage 