You are assisting with the development of backend AI features for "Thinkstash," a web-based knowledge card system, using **CrewAI** in Python. Focus on **Epic 1: Core AI Feature Backend Implementation (CrewAI)**.

**Overall Goal for Epic 1:** Design, develop, and prepare for local testing CrewAI agents and their orchestration for:

1. **"Create from Link":** AI-assisted creation of new knowledge cards from URLs (generating title, summary, and tags).  
2. "Tag Regeneration": AI-assisted suggestion of tags for existing knowledge cards.  
   This includes setting up CrewAI, developing agents with tools and tasks, defining crews, processing/storing generated content, and generating/storing vector embeddings using pgvector.

**Key Technologies & Frameworks:**

* **Orchestration:** CrewAI (Python)  
* **Core LLM Framework (used by CrewAI):** Langchain (Python)  
* **LLM Provider:** OpenAI. The target model is **gpt-4o-mini** (or a similar cost-effective and capable OpenAI model if gpt-4o-mini is not yet available via API). The OpenAI API key is available; ask if needed for placeholder/example configurations.  
* **API for AI Services:** FastAPI (Python)  
* **Secret Management:** Google Secret Manager (for cloud deployment). For local development, environment variables or a local .env file (added to .gitignore) should be used for API keys. **Ensure no secrets are ever committed to Git.**  
* **Database:** Google Cloud SQL (PostgreSQL) with the pgvector extension.  
* **Content Parsing/Fetching:** Python libraries like requests, BeautifulSoup, newspaper3k, or Mozilla Readability.

**Tasks (referencing ticket IDs from the "Thinkstash: AI Feature Implementation Plan"):**

1\. Foundational Setup (TS-AI-1, TS-AI-3):  
\* TS-AI-1: Python Project Structure & CrewAI Setup:  
\* Guide in setting up the Python project structure for CrewAI microservices (directories for agents, tools, tasks, crews, utils, api (for FastAPI), config).  
\* Assist with installing CrewAI, Langchain, FastAPI, Uvicorn, Pydantic, python-dotenv, and other base libraries in a Python virtual environment (e.g., using venv or conda). Provide a requirements.txt structure.  
\* Provide a simple "hello world" example of a CrewAI agent and crew running locally.  
\* Include a basic .gitignore file that excludes common Python artifacts, virtual environment folders, and .env files.  
\* TS-AI-3: Secure API Key Management:  
\* Show how to load the OpenAI API key from an environment variable (e.g., from a .env file using python-dotenv for local development) within the Python application.  
\* Later, for cloud deployment (Epic 3), integration with Google Secret Manager will be handled. For now, focus on local, secure key handling.  
2\. "Create from Link" Feature \- Agents & Crew (TS-AI-4 to TS-AI-8):  
\* TS-AI-4: Content Fetching Agent & Tool:  
\* Design and implement a CrewAI Tool (e.g., WebPageContentFetcherTool) and the Agent (ContentFetchingAgent) that uses it.  
\* The tool should fetch and parse the main readable content from a URL using requests and BeautifulSoup (or newspaper3k/Mozilla Readability).  
\* Implement robust error handling (timeouts, 404s, SSL issues, basic paywall detection hints if possible) and fallback behavior (returning URL and error message if parsing fails).  
\* TS-AI-5: Title Generation/Extraction Agent (for "Create from Link"):  
\* Design the TitleAgent (CrewAI Agent). Input: fetched content (text).  
\* It will use the OpenAI LLM (gpt-4o-mini). I will provide the specific prompt content. You should structure the agent to make the LLM call and process the response to extract/generate a single title string.  
\* TS-AI-6: Summarization Agent (for "Create from Link"):  
\* Design the SummarizationAgent. Input: fetched content (text).  
\* It will use the OpenAI LLM (gpt-4o-mini). I will provide the specific prompt content.  
\* The output summary must be structured as JSON, conforming to the application's block-based editor format (e.g., \[{"type": "paragraph", "content": "Summary text here."}\]). Help structure the agent and LLM call to ensure this JSON output.  
\* TS-AI-7: Tag Suggestion Agent (for "Create from Link"):  
\* Design the TaggingAgent. Input: fetched content, generated title, and/or summary.  
\* It will use the OpenAI LLM (gpt-4o-mini). I will provide the specific prompt content.  
\* Output: a list of suggested tags and hashtags (e.g., \["python", "\#AI", "development"\]).  
\* TS-AI-8: Orchestrate "Create from Link" Crew:  
\* Define a CrewAI Crew (WebCardCreationCrew) orchestrating the ContentFetchingAgent, TitleAgent, SummarizationAgent, and TaggingAgent.  
\* Define the Tasks for each agent within this crew.  
\* Show data flow management between agents.  
\* Input: URL. Output: structured JSON (title, block-format summary, list of tags, source URL).  
\* Advise on handling partial successes within the crew's process.  
3\. AI-Enhanced Card Tag Regeneration (TS-AI-10):  
\* TS-AI-10: Tag Regeneration Agent (TagRegenerationAgent):  
\* Design a CrewAI Agent (or a new Task for an existing agent) using the OpenAI LLM (gpt-4o-mini). I will provide specific prompt content.  
\* Input: existing card title and content.  
\* Output: list of suggested new tags/hashtags.  
4\. API Endpoints (FastAPI) & Database Integration (TS-AI-12, TS-AI-13):  
\* TS-AI-12: FastAPI Endpoints (Revised):  
\* Define FastAPI app structure (main.py), routers, and Pydantic models for request/response schemas.  
\* Endpoints:  
\* POST /api/v1/cards/create-from-link (accepts: {"url": "string"}). Returns card data from WebCardCreationCrew.  
\* POST /api/v1/cards/{card\_id}/regenerate-tags (accepts: {"title": "string", "content": "string or block\_json"}). Returns tag suggestions from TagRegenerationAgent.  
\* TS-AI-13: Database Interaction (Conceptual for now):  
\* Briefly discuss how the FastAPI service would typically hand off the AI-generated data to the main Next.js backend for database persistence. For now, the AI service itself won't directly write to Cloud SQL. Focus on returning structured data from the API endpoints.  
5\. Vector Embeddings (TS-AI-14):  
\* TS-AI-14: pgvector Integration:  
\* Guide on integrating an embedding model (e.g., OpenAI's text-embedding-3-small or text-embedding-3-large, or a Sentence Transformer model like all-MiniLM-L6-v2 for local/cost-effective use).  
\* Show how to generate embeddings for text fields (e.g., title, AI summary from "Create from Link", user content) within the Python service after content generation (e.g., as a final step in the WebCardCreationCrew or as a utility function called by the API endpoint handlers).  
\* The FastAPI endpoints should include these embeddings in their response if applicable, so the Next.js backend can store them. Provide example Python code for generating embeddings and structuring them in the API response.  
Start with TS-AI-1 (Python Project Structure & CrewAI Setup, including .gitignore and .env for API key).  
Then proceed to TS-AI-4 (Content Fetching Agent & Tool) as the first agent to build for the "Create from Link" feature.