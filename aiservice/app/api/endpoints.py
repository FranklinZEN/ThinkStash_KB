from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional

# Pydantic Models for request/response bodies
from aiservice.app.models.insight_generation_models import (
    RewriteContentInput, RewriteContentOutput,
    GenerateTitleInput, GenerateTitleOutput,
    GenerateKeywordsInput, GenerateKeywordsOutput
)
from aiservice.app.models.orchestration_models import ContentBlock # For type hinting in crew results

# LLM Configuration
from aiservice.app.config.llm_config import get_configured_llm

# Crews
from aiservice.app.crews.content_rewrite_crew import ContentRewriteCrew
from aiservice.app.crews.general_purpose_crews import GeneralPurposeTitleGenerationCrew, GeneralPurposeKeywordExtractionCrew

router = APIRouter()

# --- AI Insight Generation Endpoints --- #

@router.post("/rewrite-content", response_model=RewriteContentOutput,
              summary="Rewrite/Summarize Content Blocks",
              description="Takes a list of content blocks and uses an AI crew to rewrite or summarize them.")
async def rewrite_content(payload: RewriteContentInput = Body(...)) -> RewriteContentOutput:
    """
    Endpoint to rewrite content using the ContentRewriteCrew.
    Performance Target for this "Rewrite Content" action: P99 latency under 30 seconds, average latency 10-15 seconds.
    """
    llm = get_configured_llm()
    if not llm:
        raise HTTPException(status_code=500, detail="LLM service not available or configured correctly.")

    rewrite_crew = ContentRewriteCrew(llm=llm)
    
    try:
        rewritten_blocks: List[ContentBlock] = rewrite_crew.run(
            original_content_blocks=payload.content_blocks_to_rewrite,
            document_metadata=payload.document_metadata
        )
        
        if not rewritten_blocks:
            # This case might occur if the crew completes but produces no valid output (e.g., empty list from run method)
            raise HTTPException(status_code=500, detail="Content rewrite crew did not produce valid output.")
            
        return RewriteContentOutput(
            ai_rewritten_content_blocks=rewritten_blocks,
            status_message="Content rewrite completed successfully."
        )
    except Exception as e:
        # Catch any other unexpected errors from the crew execution
        print(f"Error during content rewrite: {e}") # Log the full error for debugging
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during content rewriting: {str(e)}")

@router.post("/generate-title", response_model=GenerateTitleOutput,
              summary="Generate AI-Suggested Title",
              description="Generates an AI-suggested title for the given content blocks.")
async def generate_title(payload: GenerateTitleInput = Body(...)) -> GenerateTitleOutput:
    llm = get_configured_llm()
    if not llm:
        raise HTTPException(status_code=500, detail="LLM service not available or configured correctly.")

    title_crew = GeneralPurposeTitleGenerationCrew(llm=llm)
    try:
        suggested_title_str: Optional[str] = title_crew.run(
            content_blocks=payload.content_blocks,
            document_metadata=payload.document_metadata
        )
        
        if not suggested_title_str:
            raise HTTPException(status_code=500, detail="Title generation crew did not produce a valid title.")
            
        return GenerateTitleOutput(suggested_title=suggested_title_str)
    except Exception as e:
        print(f"Error during title generation: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during title generation: {str(e)}")

@router.post("/generate-keywords", response_model=GenerateKeywordsOutput,
              summary="Generate AI-Suggested Keywords",
              description="Generates a list of AI-suggested keywords for the given content blocks.")
async def generate_keywords(payload: GenerateKeywordsInput = Body(...)) -> GenerateKeywordsOutput:
    llm = get_configured_llm()
    if not llm:
        raise HTTPException(status_code=500, detail="LLM service not available or configured correctly.")

    keyword_crew = GeneralPurposeKeywordExtractionCrew(llm=llm)
    try:
        suggested_keywords_list: Optional[List[str]] = keyword_crew.run(
            content_blocks=payload.content_blocks,
            document_metadata=payload.document_metadata
        )
        
        if not suggested_keywords_list:
            raise HTTPException(status_code=500, detail="Keyword generation crew did not produce valid keywords.")
            
        return GenerateKeywordsOutput(suggested_keywords=suggested_keywords_list)
    except Exception as e:
        print(f"Error during keyword generation: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during keyword generation: {str(e)}")

# Remove the example hello_world endpoint if it's no longer needed
# @router.get("/hello")
# async def hello_world():
#     return {"message": "Hello from AI Service API"}

# Endpoint for Content Rewrite (Iteration 1.1)
# @router.post("/rewrite-content", response_model=RewriteContentOutput) # Define RewriteContentOutput model
# async def rewrite_content(payload: RewriteContentInput): # Define RewriteContentInput model
#     # Logic to call ContentRewriteCrew
#     pass

# Endpoint for Title Generation (Iteration 1.2)
# @router.post("/generate-title", response_model=GenerateTitleOutput)
# async def generate_title(payload: GenerateTitleInput):
#     # Logic to call GeneralPurposeTitleGenerationCrew
#     pass

# Endpoint for Keyword Generation (Iteration 1.3)
# @router.post("/generate-keywords", response_model=GenerateKeywordsOutput)
# async def generate_keywords(payload: GenerateKeywordsInput):
#     # Logic to call GeneralPurposeKeywordExtractionCrew
#     pass 