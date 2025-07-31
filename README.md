# ThinkStash: Your Intelligent, AI-Powered Personal Knowledge Base

ThinkStash is a modern web application designed to be a "second brain." It empowers users to build a consolidated, personal knowledge hub by capturing information from various sources. More than just a note-taking app, ThinkStash uses a sophisticated AI agentic backend to analyze, process, and enrich content, laying the groundwork for a future where you can have intelligent conversations with your own knowledge.

This project serves as a portfolio piece to showcase the development of a full-stack, AI-native application from concept to execution.

---

### Key Features

*   **🧠 Multi-Source Knowledge Capture:** Create "Knowledge Cards" by manually writing notes, uploading PDF documents, or instantly parsing content from any URL.
*   **🤖 AI-Powered Content Enrichment:**
    *   **Auto-Title Generation:** Let AI suggest a concise, relevant title for your content.
    *   **Keyword & Tag Extraction:** Automatically identify and tag key concepts within your notes for better organization and discovery.
    *   **Content Summarization & Rewrite:** Refine and condense lengthy articles or notes into brief, memorable summaries.
*   **✍️ Rich Text Editing:** A powerful, intuitive block-based editor for crafting and formatting notes.
*   **🗂️ Folder Organization:** Structure your knowledge with a simple and effective folder management system.
*   **🔐 User Authentication:** Secure user accounts and private knowledge bases.
*   **🚀 Future-Ready for RAG:** The entire system is architected to eventually use your personal knowledge base as a source for Retrieval-Augmented Generation (RAG), enabling you to query your own data.

---

### How It Works: The AI Agentic Pipeline

The power of ThinkStash lies in its backend, where a team of specialized AI agents, built with **`crewAI`** and **`Langchain`**, work together to process information.

#### Workflow Overview:

1. **User Input** → URL, PDF, or Manual Text
2. **Content Fetcher Agent** → Scrapes and extracts raw content
3. **Knowledge Card Creation** → Stores initial content in database
4. **AI Agent Crew Assembly** → Orchestrates multiple specialized agents:
   - **Title Generation Agent** → Creates concise, relevant titles
   - **Keyword Extraction Agent** → Identifies key concepts and tags
   - **Content Rewrite Agent** → Summarizes and refines content
5. **Enriched Knowledge Card** → Returns enhanced content to user

#### Technical Flow:
```
User Input (URL/PDF/Text)
    ↓
Content Fetcher Agent (Python + Playwright/PyMuPDF)
    ↓
Raw Content → Knowledge Card (PostgreSQL)
    ↓
Trigger AI Enrichment Tasks (Celery Queue)
    ↓
AI Agent Crew (crewAI + Langchain)
    ├── Title Generation Agent
    ├── Keyword Extraction Agent
    └── Content Rewrite Agent
    ↓
Enriched Knowledge Card → Frontend (Next.js)
```

1.  **Capture:** The user provides input (e.g., a URL).
2.  **Fetch & Parse:** The `Content Fetcher Agent` scrapes the URL, cleans the HTML, and extracts the core article text.
3.  **Enrich (On-Demand):** The user can then trigger various AI enrichment tasks. A "crew" of agents is assembled to:
    *   Generate a fitting title.
    *   Extract relevant keywords.
    *   Rewrite the content for brevity and clarity.
4.  **Store:** The final, enriched content is saved as a structured "Knowledge Card" in the database.

---

### Core Architecture

ThinkStash is built on a modern, decoupled architecture designed for scalability and maintainability.

*   **Frontend Webapp:** A responsive user interface built with **Next.js**, **React**, **TypeScript**, and **Chakra UI**. It communicates with a backend-for-frontend (BFF) via API routes.
*   **Backend API (BFF):** **Next.js API Routes** handle user authentication, data fetching, and serve as the gateway to the AI microservice.
*   **AI Microservice:** A powerful, asynchronous backend service built with **Python**, **FastAPI**, and **Celery**. This is the heart of the AI capabilities, orchestrating the `crewAI` and `Langchain` agents to perform complex content processing tasks.
*   **Database:** **PostgreSQL** serves as the primary data store, with **Prisma** as the ORM for type-safe database access.
*   **File Storage:** **Google Cloud Storage (GCS)** is used for securely storing user-uploaded files like PDFs and images.
*   **Task Queue:** **Redis** and **Celery** manage the queue for long-running AI tasks, ensuring the user interface remains fast and responsive.

---

### A Note on the Development Process: Built with Cursor AI

This entire project was developed from ideation to implementation without any human coding, serving as a personal case study in AI-assisted software development.

*   **The Vision:** The goal was to test the limits of "vibe-driven development"—translating a product vision directly into functional code by writing high-level prompts and guiding an AI partner.
*   **The Process:** I acted as the product manager and architect, defining requirements, designing the system, and engineering prompts. **Cursor AI** served as the programmer, generating the code, debugging, and refactoring across the entire full-stack application.
*   **The Learning:** This project was an invaluable learning experience in human-AI collaboration. It provided deep insights into prompt engineering, iterative development with LLMs, and a practical, hands-on understanding of how to build and orchestrate AI agentic workflows using frameworks like `crewAI` and `Langchain`.

---

### Tech Stack

| Category           | Technologies                                                                                             |
| ------------------ | -------------------------------------------------------------------------------------------------------- |
| **Frontend**       | `Next.js`, `React`, `TypeScript`, `Chakra UI`, `Zustand`, `BlockNote (Editor)`, `SWR`                       |
| **Backend (API)**  | `Next.js API Routes`, `NextAuth.js`, `Prisma ORM`, `Zod`                                                   |
| **AI Microservice**| `Python`, `FastAPI`, `Celery`, `crewAI`, `Langchain`, `Pydantic`                                            |
| **Database**       | `PostgreSQL`, `pgvector` (for future semantic search)                                                    |
| **File Handling**  | `Google Cloud Storage`, `Playwright` (Scraping), `PyMuPDF` (PDFs), `OpenCV` (Image Proc.)                   |
| **DevOps & Tools** | `Docker`, `ESLint`, `Prettier`, `Jest`, `Pytest`                                                           |

---

### Local Development Setup

Follow these steps to run the complete ThinkStash stack on your local machine.

#### 1. Environment Variable Setup

You will need to create two environment files. **These files should not be committed to git.**

A. **Webapp Environment (`.env.local`):**
   - In the project root directory, create a file named `.env.local`.
   - Add the following content:
     ```
     DATABASE_URL="postgresql://user:password@localhost:5433/knowledge_cards?sslmode=disable"
     NEXTAUTH_SECRET="a-secret-for-local-development"
     ```

B. **AI Worker Environment (`aiservice/.env.worker`):**
   - In the `aiservice/` directory, create a file named `.env.worker`.
   - You will need to get your own `GEMINI_API_KEY` and set up a GCS bucket.
     ```
     # In aiservice/.env.worker
     DATABASE_URL="postgresql://user:password@localhost:5433/knowledge_cards?sslmode=disable"
     GEMINI_API_KEY="your-google-ai-api-key"
     GCS_BUCKET_NAME="your-gcs-bucket-name"
     PYTHONUNBUFFERED=1
     PYTHONDONTWRITEBYTECODE=1
     ```

#### 2. Running the Application

Follow these steps in order.

1.  **Start the Local Database:**
    - Open a terminal in the project root.
    - Run the following command to start the PostgreSQL database in a Docker container.
      ```bash
      docker-compose up -d postgres
      ```

2.  **Set Up the Database Schema:**
    - This command applies any pending migrations to the local database.
      ```bash
      npx prisma migrate dev
      ```

3.  **Start the Webapp:**
    - In a new terminal, run the Next.js development server.
      ```bash
      npm install
      npm run dev
      ```
    - The web application will be available at `http://localhost:3000`.

4.  **Start the AI Worker:**
    - In another new terminal, navigate to the `aiservice` directory and run the worker startup script. (You may need to set up a Python virtual environment and run `pip install -r requirements.txt` first).
      ```bash
      # First-time setup for the worker
      python -m venv .venv
      source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
      pip install -r requirements.txt

      # Run the worker
      sh ./run_local_worker.sh # On Windows, you can run the .ps1 script
      ```
    - This will start the Python worker, which listens for background tasks.
