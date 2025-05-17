# **Thinkstash: AI Feature Implementation Plan (CrewAI & GCP) \- Revised**

This document outlines the Epics and JIRA-style tickets for implementing the AI-powered features using CrewAI, deploying them as microservices on Google Cloud Run, integrating with the frontend, and setting up public accessibility. This revision reflects a focused approach on AI for new content creation from links and tag assistance for existing content, deferring direct AI modification of existing user-authored titles and summaries. All epics listed below are part of Stage 2, which signifies the work done after the initial foundational GCP deployment and setup.

**PRD Reference:** Version 3.8, Stage 2 (GCP Production & Core AI Enhancements), with scope adjustments as per user feedback.

## **Stage 2 \- Epic 1: Core AI Feature Backend Implementation (CrewAI)**

Description: This epic covers the design, development, and local testing of all CrewAI agents and their orchestration for the core AI features. It includes setting up the CrewAI framework, developing individual agents, defining crews, and ensuring generated content can be processed and stored, including vector embeddings. The focus is on AI-assisted creation of new cards from URLs and tag generation for all cards.  
PRD References: FR-CARD-3 (Create from Link), relevant parts of FR-CARD-4 (Tag Regeneration), TC-STACK-6, FR-SEARCH-2

### **User Stories / Tasks for Stage 2 \- Epic 1:**

1. **TS-AI-1 (Task): Setup CrewAI Development Environment**  
   * **Description:** Install CrewAI, Langchain, and necessary Python libraries (e.g., for web requests, content parsing). Establish a basic Python project structure for CrewAI development (agents, tools, tasks, crews).  
   * **Acceptance Criteria (AC):**  
     * CrewAI and its dependencies are installed in a virtual environment.  
     * A basic "hello world" CrewAI agent and crew can be run locally.  
     * Project directory structure for AI microservices is defined and initialized.  
2. **TS-AI-2 (Task): Research & Decision on Initial LLM Provider(s)**  
   * **Description:** Evaluate and select the initial LLM provider(s) (e.g., Google Vertex AI \- Gemini, OpenAI API, etc.) to be used with CrewAI. Consider model capabilities for summarization, title generation, tagging, cost, and ease of integration. *This is an interactive process for you to decide.*  
   * **AC:**  
     * Primary LLM provider(s) for Stage 2 AI features selected.  
     * Basic understanding of API access, model names, and integration with Langchain/CrewAI for the chosen provider(s).  
   * **PRD Reference:** ADR-010  
3. **TS-AI-3 (Task): Setup Secure API Key Management for LLMs**  
   * **Description:** Implement secure storage and runtime access for LLM API keys using Google Secret Manager. Ensure Python services can fetch these keys.  
   * **AC:**  
     * LLM API keys are stored securely in Google Secret Manager.  
     * Python application (CrewAI services) can retrieve and use these keys at runtime without hardcoding.  
   * **PRD Reference:** TC-STACK-6, NFR-SEC-1  
4. **TS-AI-4 (Story): Design & Develop "Content Fetching Agent" for "Create from Link"**  
   * **Description:** Create a CrewAI agent with a tool responsible for securely fetching and parsing the main readable content from a given URL. Must include robust error handling and fallback mechanisms.  
   * **AC:**  
     * Agent accepts a URL as input.  
     * Tool successfully extracts main article text from various web pages (e.g., using libraries like requests, BeautifulSoup, newspaper3k, or Mozilla Readability).  
     * Handles common errors (e.g., 404s, timeouts, SSL issues, paywalls) gracefully.  
     * Implements fallback behavior as per FR-CARD-3 (e.g., creating a card with URL and title only if full processing fails).  
   * **PRD Reference:** FR-CARD-3  
5. **TS-AI-5 (Story): Design & Develop "Title Generation/Extraction Agent" for "Create from Link"**  
   * **Description:** Create a CrewAI agent that, given fetched web content, either extracts an existing title or generates a concise and relevant title using an LLM. *Prompts and LLM model choice are part of your interactive decision process.* (This applies to new cards from links).  
   * **AC:**  
     * Agent processes fetched content (text).  
     * Outputs a single, relevant title string.  
     * Placeholder for defined LLM prompt and model selection.  
   * **PRD Reference:** FR-CARD-3  
6. **TS-AI-6 (Story): Design & Develop "Summarization Agent" for "Create from Link"**  
   * **Description:** Create a CrewAI agent that generates a concise summary of fetched web content, outputting it in the application's specified block format (JSON). *Prompts and LLM model choice are part of your interactive decision process.* (This applies to new cards from links).  
   * **AC:**  
     * Agent processes fetched content (text).  
     * Outputs a summary structured as JSON conforming to the block-based editor format.  
     * Placeholder for defined LLM prompt and model selection.  
   * **PRD Reference:** FR-CARD-3  
7. **TS-AI-7 (Story): Design & Develop "Tag Suggestion Agent" for "Create from Link"**  
   * **Description:** Create a CrewAI agent that suggests relevant tags (including hashtags) based on fetched web content, title, and/or summary. *Prompts and LLM model choice are part of your interactive decision process.* (This applies to new cards from links).  
   * **AC:**  
     * Agent processes content/title/summary.  
     * Outputs a list of suggested tags/hashtags (e.g., as a list of strings).  
     * Placeholder for defined LLM prompt and model selection.  
   * **PRD Reference:** FR-CARD-3, FR-CARD-2  
8. **TS-AI-8 (Story): Orchestrate "Create from Link" Crew**  
   * **Description:** Define a CrewAI "Crew" that orchestrates the Content Fetching, Title, Summarization, and Tagging agents to perform the "Create from Link" functionality. Define the sequential or parallel execution of tasks and data flow between agents.  
   * **AC:**  
     * A Crew is defined that takes a URL as input.  
     * The Crew successfully executes the sequence of agents.  
     * The Crew outputs a structured result containing the AI-generated title, summary (block format), and tags, along with the source URL.  
     * Handles partial successes and errors from individual agents gracefully.  
9. **TS-AI-10 (Story): Design & Develop "Tag Regeneration Agent" for Existing Cards** (Previously TS-AI-10, ID kept for consistency if already in use)  
   * **Description:** Create a CrewAI agent (or task) that regenerates card tags based on its existing title and content. *Prompts and LLM model choice are part of your interactive decision process.*  
   * **AC:**  
     * Agent accepts card title and content as input.  
     * Outputs a list of suggested new tags/hashtags.  
     * Placeholder for defined LLM prompt and model selection.  
   * **PRD Reference:** FR-CARD-4 (Tag Regeneration part)  
10. **TS-AI-12 (Task): Define API Endpoints for AI Services** (Revised)  
    * **Description:** Design the API endpoints (e.g., using FastAPI for the Python AI services) that the Next.js backend will call. Define request/response schemas.  
    * **AC:**  
      * OpenAPI/Swagger specification (or similar) for AI service endpoints.  
      * Endpoints defined for:  
        * "Create from Link" (accepts URL, returns card data including AI title, summary, tags).  
        * "Regenerate Tags" (accepts card ID/content, returns new tags).  
11. **TS-AI-13 (Task): Integrate AI Services with Database (Cloud SQL)**  
    * **Description:** Ensure that the AI services can interact with the main PostgreSQL database (Google Cloud SQL) to store the newly created/updated card data. This might be indirect (AI service returns data to Next.js backend, which then writes to DB) or direct if necessary.  
    * **AC:**  
      * Clear data flow defined for how AI-generated content updates the database.  
      * If AI services write directly, connection to Cloud SQL is established and secure.  
      * Schema updates (if any) for storing AI-generated fields are implemented.  
12. **TS-AI-14 (Task): Setup Vector Embeddings for AI Content (pgvector)**  
    * **Description:** Implement logic to generate vector embeddings for relevant card content (e.g., AI-generated summaries from "Create from Link", titles, user content) and store them in the pgvector extension within Google Cloud SQL. Choose an embedding model.  
    * **AC:**  
      * Embedding model selected (e.g., from Sentence Transformers, OpenAI, Vertex AI).  
      * Process defined and implemented to generate embeddings when cards are created/updated by AI or manually.  
      * Embeddings are stored correctly in the pgvector column.  
    * **PRD Reference:** FR-SEARCH-2, TC-STACK-3

## **Stage 2 \- Epic 2: Frontend Integration for AI Features**

Description: This epic covers all frontend work required to interact with the AI services, display AI-generated content, and provide user controls for AI features, focusing on "Create from Link" and "Tag Regeneration".  
PRD References: FR-CARD-3, relevant parts of FR-CARD-4, FR-UX-PROD-UI

### **User Stories / Tasks for Stage 2 \- Epic 2:**

1. **TS-FE-1 (Story): Implement UI for "Create from Link"**  
   * **Description:** Develop the frontend components for users to paste a URL, trigger the "Create from Link" AI process, and see loading/feedback states. Optionally include a preview step before final card creation.  
   * **AC:**  
     * Input field for URL.  
     * Button to initiate AI card creation.  
     * Loading indicators while AI processing occurs.  
     * Display of success/error messages.  
     * On success (and optional user confirmation via diff/preview), the new card (with AI-generated title, summary, tags) is displayed or added to the user's card list.  
2. **TS-FE-2 (Story): Implement UI Button for AI-Enhanced Tag Generation** (Revised)  
   * **Description:** Add an "AI" button to the card interface for regenerating tags as per the revised FR-CARD-4.  
   * **AC:**  
     * "AI" button visible near the card tags section.  
     * Clicking this button triggers the backend AI tag regeneration call.  
     * Loading states are shown during AI processing.  
3. **TS-FE-3 (Story): Develop Diff/Preview UI for AI Tag Suggestions (and optionally "Create from Link")** (Revised Scope)  
   * **Description:** Create a UI component that presents AI-regenerated tags alongside the original, allowing users to compare and then "Accept" or "Cancel" the changes. This UI might also be used for the "Create from Link" feature if a preview of the AI-generated card is desired before saving.  
   * **AC:**  
     * Modal or inline UI clearly shows "Original Tags" and "AI Suggested Tags".  
     * "Accept" button applies the AI tag changes to the card.  
     * "Cancel" button discards AI suggestions and keeps the original tags.  
     * If used for "Create from Link", it previews the full AI-generated card (title, summary, tags).  
     * UI is intuitive and easy to use.  
   * **PRD Reference:** FR-CARD-4 (Diff/Preview UI for tags)  
4. **TS-FE-4 (Task): Connect Frontend to Backend AI Service APIs**  
   * **Description:** Implement the client-side logic (e.g., in Next.js/React components using Zustand for state management) to make API calls to the revised AI service endpoints defined in TS-AI-12.  
   * **AC:**  
     * Frontend successfully calls all defined AI endpoints ("Create from Link", "Regenerate Tags").  
     * Requests and responses are handled correctly.  
     * Error handling for API call failures is implemented.  
     * State management updates correctly based on API responses.

## **Stage 2 \- Epic 3: Deployment & CI/CD for AI Microservices (Cloud Run)**

Description: This epic covers containerizing the Python-based CrewAI services and deploying them to Google Cloud Run with a CI/CD pipeline.  
PRD References: TC-STACK-2, TC-STACK-6, TC-STACK-7, NFR-DEPLOY-1

### **User Stories / Tasks for Stage 2 \- Epic 3:**

1. **TS-DEP-1 (Task): Containerize CrewAI Python Application**  
   * **AC:** Dockerfile builds, container runs locally, fetches secrets.  
2. **TS-DEP-2 (Task): Configure Cloud Run Service(s) for AI Microservices**  
   * **AC:** Cloud Run service created, container deployed, IAM set.  
3. **TS-DEP-3 (Task): Setup CI/CD Pipeline for AI Microservices**  
   * **AC:** CI/CD pipeline configured, automated build & deployment.  
4. **TS-DEP-4 (Task): Implement Basic Monitoring & Logging for AI Services**  
   * **AC:** Logs in Cloud Logging, basic metrics in Cloud Monitoring.  
   * **PRD Reference:** TC-STACK-8

## **Stage 2 \- Epic 4: Public Accessibility & SSL for Thinkstash (Cloud Run \- Entire App)**

Description: This epic focuses on making the entire Thinkstash application (Next.js frontend and potentially how it securely communicates with backend AI services) publicly accessible via a custom domain with Google-managed SSL. This assumes your Next.js app is also deployed on Cloud Run.  
PRD References: Stage 2 (GCP Production), NFR-SEC-1

### **User Stories / Tasks for Stage 2 \- Epic 4:**

1. **TS-SSL-1 (Task): Acquire/Configure Custom Domain for Thinkstash**  
   * **AC:** Domain registered, DNS access available.  
2. **TS-SSL-2 (Task): Map Custom Domain to Cloud Run (Next.js Frontend Service)**  
   * **AC:** Domain mapped in Cloud Run, DNS records added.  
3. **TS-SSL-3 (Task): Verify Google-Managed SSL Certificate Provisioning**  
   * **AC:** App accessible via https://yourcustomdomain.com with valid SSL.  
4. **TS-SSL-4 (Task): Secure Communication between Frontend and AI Services**  
   * **AC:** Secure and efficient communication path established.

## **Stage 2 \- Epic 6: Comprehensive Testing, Deployment Strategy & Operational Excellence**

Description: This epic focuses on establishing, implementing, and continuously improving a robust testing and deployment strategy across all stages of development (local, staging/shadow, production). It includes defining processes for various testing types, setting up environments, and establishing clear fallback, reversion, and monitoring mechanisms for all services (Frontend, Backend, AI). Note: While presented sequentially, the planning and definition tasks (e.g., TS-TEST-1, TS-TEST-2) within this epic should be initiated early in Stage 2, concurrently with development epics like "Stage 2 \- Epic 1". The execution of these strategies is an ongoing effort throughout Stage 2 and beyond, and is critical for the stability and quality of all Stage 2 releases.  
PRD References: NFR-PERF-1, NFR-SCALE-1, NFR-REL-1, NFR-DEPLOY-1, TC-STACK-8

### **User Stories / Tasks for Stage 2 \- Epic 6:**

1. **TS-TEST-1 (Task): Review and Document Existing Testing Practices**  
   * **Description:** Analyze current testing procedures (if any) and document them as a baseline. Identify gaps.  
   * **AC:** Document outlining current testing state and identified gaps.  
2. **TS-TEST-2 (Task): Define Comprehensive Testing Strategy & Standards**  
   * **Description:** Create a formal testing strategy document covering unit, integration, end-to-end (E2E), and user acceptance testing (UAT) for all application components. Define coding standards for testability.  
   * **AC:** Testing strategy document approved and shared.  
3. **TS-TEST-3 (Story): Develop/Enhance Unit Test Suites**  
   * **Description:** Write and maintain unit tests for critical functions and components in the frontend (React/Next.js) and backend (Next.js API routes, Python/CrewAI services). Aim for target code coverage.  
   * **AC:** Unit tests implemented for key modules; CI pipeline runs unit tests automatically.  
4. **TS-TEST-4 (Story): Develop/Enhance Integration Test Suites**  
   * **Description:** Implement integration tests to verify interactions between different parts of the system (e.g., Frontend \<-\> Next.js Backend, Next.js Backend \<-\> AI Microservices, AI Microservices \<-\> Database/LLM APIs).  
   * **AC:** Integration tests implemented for key workflows; CI pipeline runs integration tests.  
5. **TS-TEST-5 (Task): Investigate and Plan for Shadow Mode/Canary Releases for AI Features**  
   * **Description:** Research and plan the implementation of shadow mode (running new AI models/logic alongside old ones without affecting user output, logging differences) or canary releases for AI features to test them in production with minimal risk.  
   * **AC:** Feasibility study and implementation plan for shadow mode/canary releases for AI.  
6. **TS-TEST-6 (Task): Define Staging Environment Setup and Testing Procedures on GCP**  
   * **Description:** Plan and document the setup of a staging environment on GCP that mirrors production as closely as possible. Define procedures for deploying to and testing in staging.  
   * **AC:** Staging environment plan and testing procedures documented. CI/CD deploys to staging.  
7. **TS-TEST-7 (Task): Define Production Release Process & Checklist (CRQ \- Change Request Quality Process)**  
   * **Description:** Document the step-by-step process for releasing new versions to production, including pre-release checks, a formal Change Request Quality (CRQ) process, deployment steps, and post-release monitoring. This includes defining integration testing, E2E testing, and shadow run requirements as part of the CRQ.  
   * **AC:** Production release process (including CRQ elements) and checklist documented and adopted.  
8. **TS-TEST-8 (Task): Develop and Document Fallback and Reversion Mechanisms**  
   * **Description:** For Cloud Run services (Frontend & AI), establish and document clear procedures for quickly rolling back to a previous stable version in case of a faulty deployment or critical issues in production.  
   * **AC:** Documented and tested rollback procedures for all Cloud Run services.  
9. **TS-TEST-9 (Task): Develop and Document Data Migration and Rollback Strategies**  
   * **Description:** For any database schema changes, define a strategy for data migration and, importantly, how to roll back schema changes and data if a release fails.  
   * **AC:** Data migration and rollback strategy documented.  
10. **TS-TEST-10 (Task): Establish Performance Testing and Monitoring for AI Features**  
    * **Description:** Define and implement performance tests for AI features to measure latency and resource consumption. Set up specific monitoring in Google Cloud Monitoring for AI service performance and error rates.  
    * **AC:** Performance test suite for AI features; key AI performance metrics monitored with alerts.  
11. **TS-TEST-11 (Task): User Acceptance Testing (UAT) Process Definition**  
    * **Description:** Define a formal process for UAT, including how to select testers (e.g., your friends for initial small-batch testing), gather feedback, and sign off on features before wider release.  
    * **AC:** UAT process documented and implemented for new feature releases.

## **Stage 2 \- Epic 5: Advanced Interaction \- RAG Chat & Collaborative Card Creation (Future \- Stage 2+)**

Description: This epic outlines the future development of an in-house chat system powered by an LLM. The system will leverage existing knowledge cards via RAG (using the pgvector setup from Epic 1), incorporate web search capabilities, and allow users to collaboratively create new knowledge cards through the chat interface. This is envisioned for Stage 2+ or a later phase and will require dedicated GCP infrastructure planning.  
PRD References: Future Vision Note, Stage 2+ (Chat with Knowledge Base, AI Collection Summaries, AI "Spark" Prompts)

### **User Stories / Tasks for Stage 2 \- Epic 5:**

1. **TS-CHAT-1 (Task): Design RAG Chat System Architecture**  
   * **Description:** Define the overall architecture for the RAG chat system, including how CrewAI agents will interact, data flow, context management, and integration with existing knowledge card data and vector store. Identify necessary GCP services (e.g., Cloud Run for chat backend, potentially Pub/Sub for asynchronous tasks, Memorystore for chat history/session state).  
   * **AC:** Architectural diagram and design document for the chat system.  
2. **TS-CHAT-2 (Story): Develop RAG Retrieval Agent/Tool**  
   * **Description:** Create a CrewAI agent/tool specifically for querying the pgvector database to retrieve relevant knowledge card snippets based on chat context or user queries.  
   * **AC:** Agent/tool successfully retrieves relevant context from the vector store.  
3. **TS-CHAT-3 (Story): Develop Web Search Agent/Tool for Chat**  
   * **Description:** Create or integrate a CrewAI agent/tool that can perform web searches to gather external information relevant to the chat conversation.  
   * **AC:** Agent/tool successfully fetches and processes web search results.  
4. **TS-CHAT-4 (Story): Develop Chat Interaction Management Agent(s)**  
   * **Description:** Design and implement CrewAI agent(s) responsible for managing the flow of conversation, interpreting user intent, delegating tasks to retrieval/search agents, and synthesizing information for response generation.  
   * **AC:** Core chat logic and agent interaction flow established.  
5. **TS-CHAT-5 (Story): Design & Develop Collaborative Card Creation Flow via Chat**  
   * **Description:** Define and implement the process by which a user can interact with AI agents via chat to iteratively research, draft, and refine content for a new knowledge card. This includes how the AI presents information and how the user provides feedback or directs the creation process.  
   * **AC:** User can guide AI through chat to generate content for a new knowledge card.  
6. **TS-CHAT-6 (Story): Develop Frontend UI for Chat Interface**  
   * **Description:** Design and implement the user interface for the chat system within the Thinkstash application.  
   * **AC:** Functional chat UI allowing users to send messages and receive responses.  
7. **TS-CHAT-7 (Task): Integrate Chat with Knowledge Card System**  
   * **Description:** Implement the functionality to save collaboratively generated content from the chat interface as a new knowledge card in the user's database.  
   * **AC:** New knowledge cards can be successfully created and saved from the chat system.  
8. **TS-CHAT-8 (Task): Plan GCP Deployment for Chat Services**  
   * **Description:** Detail the deployment strategy for all components of the chat system on GCP, including CI/CD, scaling, monitoring, and cost considerations.  
   * **AC:** Deployment plan for chat services on GCP documented.

This revised plan aligns with your new direction, focusing AI assistance on areas that augment user efforts without potentially overwriting their core intent in existing notes, and adds epics for future advanced features and robust testing.