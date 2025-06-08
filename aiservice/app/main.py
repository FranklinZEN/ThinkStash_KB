from fastapi import FastAPI
from .config.settings import settings
# Import routers later when we create them
# from .api import some_router # Example

app = FastAPI(
    title="Thinkstash AI Service",
    description="Provides AI-powered features for Thinkstash using CrewAI.",
    version="0.1.0"
)

@app.on_event("startup")
def startup_event():
    print("AI Service starting up...")
    print(f"OpenAI Model: {settings.openai_model_name}")
    if settings.gemini_api_key:
        print("Gemini API Key is configured.")
    else:
        print("Gemini API Key is NOT configured.")
    # You can add other startup logic here

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Thinkstash AI Service"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Include API routers from the api sub-package later
# app.include_router(some_router.router, prefix="/api/v1/items", tags=["Items"])

# To run this app (from the 'aiservice' directory):
# Ensure you have a .env file with OPENAI_API_KEY and OPENAI_MODEL_NAME
# Make sure your virtual environment is activated.
# uvicorn app.main:app --reload 