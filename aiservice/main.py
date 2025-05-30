from fastapi import FastAPI

# Import the API router
from aiservice.app.api import endpoints as insight_api_router

app = FastAPI(
    title="ThinkStash AI Service",
    description="Provides AI-powered functionalities including content reconstruction and insight generation.",
    version="0.1.0"
)

# Include the insight generation API router
app.include_router(insight_api_router.router, prefix="/api/v1/ai", tags=["AI Insights"])

@app.get("/")
async def root():
    return {"message": "Welcome to the ThinkStash AI Service!"}

# Add other application setup, middleware, event handlers etc. here if needed

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) # Added reload=True for development 