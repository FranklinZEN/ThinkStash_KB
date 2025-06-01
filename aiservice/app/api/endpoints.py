from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional

# Pydantic Models for request/response bodies
from aiservice.app.models.insight_generation_models import (
    RewriteContentInput, RewriteContentOutput,
    GenerateTitleInput, GenerateTitleOutput,
    GenerateKeywordsInput, GenerateKeywordsOutput,
    TitleGenerationRequest, TitleGenerationResponse,
    KeywordExtractionRequest, KeywordExtractionResponse
)
from aiservice.app.models.orchestration_models import ContentBlock # For type hinting in crew results

# LLM Configuration
from aiservice.app.config.llm_config import get_configured_llm

# Crews
from aiservice.app.crews.content_rewrite_crew import ContentRewriteCrew
from aiservice.app.crews.title_generation_crew import GeneralPurposeTitleGenerationCrew as TitleGenerationCrew
from aiservice.app.crews.keyword_extraction_crew import GeneralPurposeKeywordExtractionCrew

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

@router.post("/generate-title", response_model=TitleGenerationResponse,
              summary="Generate AI-Suggested Title",
              description="Generates an AI-suggested title for the given content blocks.")
async def generate_title_endpoint(request_data: TitleGenerationRequest = Body(...)) -> TitleGenerationResponse:
    """
    Receives a list of content blocks and returns an AI-generated title.
    Processes the request using the GeneralPurposeTitleGenerationCrew.
    Endpoint aligns with V2.6 Plan - Iteration 1.2.
    """
    if not request_data.content_blocks:
        raise HTTPException(status_code=400, detail="No content blocks provided.")

    try:
        # Assuming user_id might be extracted from a JWT token or similar in a real app
        # For now, using a placeholder or deriving if possible. The crew itself has a default.
        # user_id_for_crew = "api_user" # Placeholder
        # title_crew = GeneralPurposeTitleGenerationCrew(user_id=user_id_for_crew)
        
        # Per Iteration 1.2, the crew takes content_blocks in its run method.
        # The crew constructor might take user_id if needed, but the run method is key for data.
        title_crew = TitleGenerationCrew() # Use default user_id from crew if not passed
        
        suggested_title_str = title_crew.run(content_blocks=request_data.content_blocks)

        if suggested_title_str.startswith("Error:"):
            # Log the error server-side as well
            print(f"Error from TitleGenerationCrew: {suggested_title_str}")
            # Return a more generic error to the client for now, or a specific one if appropriate
            raise HTTPException(status_code=500, detail=f"AI title generation failed: {suggested_title_str}")

        return TitleGenerationResponse(suggested_title=suggested_title_str)
    
    except HTTPException as http_exc: # Re-raise HTTPException
        raise http_exc
    except Exception as e:
        print(f"Error in /generate-title endpoint: {e}")
        # import traceback # For detailed logging
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during title generation: {str(e)}")

@router.post("/generate-keywords", response_model=KeywordExtractionResponse,
              summary="Generate AI-Suggested Keywords",
              description="Generates a list of AI-suggested keywords for the given content blocks.")
async def generate_keywords_endpoint(request_data: KeywordExtractionRequest = Body(...)) -> KeywordExtractionResponse:
    """
    Receives a list of content blocks and returns AI-generated keywords.
    Processes the request using the GeneralPurposeKeywordExtractionCrew.
    Endpoint aligns with V2.6 Plan - Iteration 1.3.
    """
    if not request_data.content_blocks:
        raise HTTPException(status_code=400, detail="No content blocks provided.")

    try:
        keyword_crew = GeneralPurposeKeywordExtractionCrew() # Instantiate the correct crew
        
        suggested_keywords_list: List[str] = keyword_crew.run(
            content_blocks=request_data.content_blocks
        )
        
        # The crew's run method should return an empty list if no keywords are found or an error occurs internally that it handles.
        # If it can raise an exception that we want to specifically catch, that would be done here.
        # For now, assume it returns a list (possibly empty).

        return KeywordExtractionResponse(suggested_keywords=suggested_keywords_list)
    
    except HTTPException as http_exc: # Re-raise HTTPException
        raise http_exc
    except Exception as e:
        print(f"Error in /generate-keywords endpoint: {e}")
        # import traceback
        # traceback.print_exc()
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