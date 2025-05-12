## Architecture Decision Records (ADRs) \- Knowledge Card System

Date: 2025-05-10 (Originally 2025-04-21)  
Status: Draft (Updated for GCP, CrewAI, and new priorities)

### ADR-001: Choice of Web Framework

* **Status:** Accepted  
* **Context:** We need a modern, robust framework for building the full-stack web application (frontend and backend API) with good developer experience, performance, and community support. The application requires server-side rendering (SSR) for initial load performance and SEO, client-side interactivity, and API route handling.  
* **Decision:** We will use **Next.js** with the **App Router**.  
* **Consequences:**  
  * **Pros:** Integrated full-stack development, excellent performance features (Server Components, SSR, SSG, ISR), strong TypeScript support, large community, modern App Router patterns, good deployment integration with various cloud platforms including GCP.  
  * **Cons:** Potential learning curve for App Router, can be overkill for very simple sites, build times might increase with application size.  
* **Alternatives Considered:** Create React App \+ Express/NestJS, Remix, SvelteKit.

### ADR-002: Choice of Database and ORM

* **Status:** Accepted (Pending further review during "Database Rethink" spike)  
* **Context:** The application requires a persistent relational database for core data (users, cards, folders, tags) and their relationships. We need efficient and type-safe database interaction from our Node.js backend. The database must be scalable and manageable in a cloud environment for Stage 2\.  
* **Decision:** We will use **PostgreSQL** as the relational database and **Prisma** as the ORM. For Stage 2, this will be a managed instance on **Google Cloud Platform (GCP), specifically Google Cloud SQL for PostgreSQL.**  
* **Consequences:**  
  * **Pros:**  
    * PostgreSQL is a powerful, open-source RDBMS with strong support for JSONB (for card content), full-text search, and extensions like pgvector.  
    * Prisma offers excellent developer experience, type safety, and an intuitive query API.  
    * Google Cloud SQL provides a managed, scalable, and reliable PostgreSQL service, reducing operational overhead.  
  * **Cons:**  
    * Requires a local PostgreSQL instance (e.g., via Docker) for Stage 1 local development.  
    * Prisma introduces an abstraction layer and requires explicit schema migrations.  
    * Optimal schema design and indexing strategies for performance at scale, especially with AI features and search, will require careful consideration during the "Database Rethink" (see ADR-XXX: Database Rethink Approach).  
* **Alternatives Considered:** MySQL, MongoDB (NoSQL), TypeORM/Sequelize (ORMs).  
* **Further Actions:** The "Database Rethink" spike will further evaluate schema design, indexing, and potential performance optimizations for PostgreSQL on GCP.

### ADR-003: Choice of Vector Search Solution

* **Status:** Accepted (Pending performance review during "Database Rethink")  
* **Context:** Stage 2 requires semantic search capabilities, which rely on generating and searching vector embeddings from card content. We need a scalable, cost-effective, and well-integrated solution within our chosen database and cloud environment.  
* **Decision:** We will use the **pgvector** extension within our primary **Google Cloud SQL for PostgreSQL** database. Embeddings will be generated externally (e.g., via selected LLM provider API \- see ADR-009).  
* **Consequences:**  
  * **Pros:**  
    * Simplifies infrastructure by co-locating vector data with relational data, reducing the need to manage a separate vector database service initially.  
    * Cost-effective compared to dedicated vector databases, especially at moderate scale.  
    * Ensures data consistency between relational metadata and vector embeddings.  
    * Prisma support for pgvector is emerging/available, allowing for unified data access.  
  * **Cons:**  
    * Potential performance limitations at very large scale or with extremely high query throughput compared to specialized dedicated vector databases.  
    * May cause resource contention on the primary database server if vector search load is very high. This will be monitored.  
    * The "Database Rethink" will assess indexing strategies (e.g., HNSW, IVFFlat) and performance implications for pgvector on Cloud SQL.  
* **Alternatives Considered:** Pinecone, Weaviate, Milvus, Qdrant (dedicated vector databases), Google Vertex AI Matching Engine. (Vertex AI Matching Engine could be a future option if pgvector proves insufficient).

### ADR-004: Choice of Content Storage Format for Knowledge Cards

* **Status:** Accepted  
* **Context:** Knowledge card content will be created and edited using a block-based editor (e.g., BlockNote). We need a storage format that preserves the structured nature of this content, is flexible, and can be reasonably queried or processed.  
* **Decision:** Card content will be stored as **JSON (specifically jsonb type in PostgreSQL)**, reflecting the native output format of the chosen block editor.  
* **Consequences:**  
  * **Pros:**  
    * High flexibility to represent diverse block types and nested structures.  
    * jsonb in PostgreSQL allows for efficient querying and indexing of JSON content.  
    * Standardized format, easily consumed and produced by frontend editors and backend services (including AI agents processing content).  
  * **Cons:**  
    * Potential parsing overhead compared to plain text (though jsonb is optimized).  
    * Requires robust validation of the JSON structure on input.  
    * Can be larger in storage size compared to highly compressed formats, though jsonb is binary.  
* **Alternatives Considered:** HTML String, Markdown String, XML.

### ADR-005: Strategy for Stage 1 to Stage 2 Data Migration

* **Status:** Accepted  
* **Context:** Users developing content in the local Stage 1 prototype may wish to transfer this data to the cloud-based Stage 2 application on GCP.  
* **Decision:** There will be **no automated migration tool** developed for transitioning data from the local Stage 1 prototype to the Stage 2 GCP environment. We will rely on a **manual user-initiated JSON export feature (from Stage 1\) and a corresponding JSON import feature (in Stage 2\)**. Clear communication will be provided to users that Stage 1 is a prototype with this manual migration path.  
* **Consequences:**  
  * **Pros:**  
    * Significantly reduces development effort and complexity for a one-time (per-user) transition from a prototype.  
    * Allows the team to focus on core Stage 2 features and GCP deployment.  
  * **Cons:**  
    * User inconvenience for transferring data.  
    * Potential for user error during manual export/import.  
    * Risk of some data not being perfectly transferable if schema evolution between local and cloud versions is not carefully managed (though JSON provides flexibility).  
* **Alternatives Considered:** Automated Migration Script/Tool, No Migration Path (requiring users to start fresh).

### ADR-006: Choice of UI Library

* **Status:** Accepted  
* **Context:** We need a React component library for building a consistent, accessible, and professional user interface for the Knowledge Card System, integrating well with Next.js.  
* **Decision:** We will use **Chakra UI**.  
* **Consequences:**  
  * **Pros:** Excellent accessibility features, highly composable components, good developer experience with style props, easy theme customization, strong community, and good integration with the React/Next.js ecosystem.  
  * **Cons:** May have fewer highly specialized, complex components out-of-the-box compared to some alternatives (though composition addresses this), team familiarity if primarily used to other libraries.  
* **Alternatives Considered:** Material UI, Tailwind CSS (with Headless UI/Radix), Ant Design.

### ADR-007: Choice of Background Job Queue System

* **Status:** Accepted (Decision to use BullMQ on GCP, specific GCP integration to be detailed)  
* **Context:** For Stage 2 on GCP, the application requires a system to reliably handle asynchronous background tasks, such as AI processing via CrewAI (e.g., "Create from Link," content regeneration), notifications, or other long-running operations. The system needs to integrate with our Node.js backend and leverage managed GCP services.  
* **Decision:** We will use **BullMQ**. It will utilize a managed **Google Cloud Memorystore for Redis** instance as its backend datastore in the Stage 2 GCP environment. Worker processes for BullMQ will be deployed on scalable GCP compute services (e.g., **Google Cloud Run or Google Kubernetes Engine (GKE)**).  
* **Consequences:**  
  * **Pros:**  
    * BullMQ is feature-rich (job prioritization, delayed jobs, rate limiting, progress tracking, repeatable jobs), well-suited for Node.js/TypeScript.  
    * Leverages Redis, a fast in-memory datastore; Memorystore provides a managed Redis service on GCP.  
    * Allows for decoupling of long-running tasks from the main request-response cycle, improving API responsiveness.  
  * **Cons:**  
    * Requires managing a Redis instance (Memorystore simplifies this but still has costs and configuration).  
    * Requires deploying and managing separate worker processes on Cloud Run/GKE, adding to architectural complexity and operational overhead compared to purely synchronous operations or simpler GCP-native task queues for basic needs.  
    * Integration and configuration of workers on GCP services need careful planning.  
* **Alternatives Considered:**  
  * **Google Cloud Tasks:** Simpler GCP-native solution for basic task queuing and HTTP target invocation. Might be sufficient if advanced BullMQ features (like progress tracking directly via the queue) are not critical.  
  * **Google Cloud Pub/Sub \+ Cloud Functions/Cloud Run:** Highly scalable, event-driven approach. Pub/Sub acts as a message broker, triggering serverless functions or containerized services for processing. Offers more decoupling but can be more complex to set up for job queue semantics.  
  * **Celery (with Python workers):** Powerful but primarily Python-focused. Considered if AI agents were to be exclusively Python services, but BullMQ fits better with a primarily Node.js backend.

### ADR-008: Choice of Cloud Provider

* **Status:** Accepted  
* **Context:** For Stage 2, the application requires a robust, scalable, and feature-rich cloud platform to host the backend, database, storage, AI agent workloads, and other production services. Previous considerations included AWS.  
* **Decision:** We will use **Google Cloud Platform (GCP)** for Stage 2 and beyond.  
* **Consequences:**  
  * **Pros:**  
    * Strong offerings in AI/ML (Vertex AI, foundational models) which align with our AI-centric features.  
    * Comprehensive data analytics and database services (Cloud SQL, BigQuery, Spanner).  
    * Scalable compute options (Cloud Run, GKE, App Engine).  
    * Global infrastructure and robust networking.  
    * Potentially favorable pricing or credits for startups/specific workloads.  
    * Integrated ecosystem for monitoring, logging, CI/CD (Cloud's operations suite, Cloud Build).  
  * **Cons:**  
    * Team familiarity: If the team has more extensive experience with another provider (e.g., AWS), there will be a learning curve for GCP-specific services and best practices.  
    * Market share: AWS has a larger market share, which sometimes translates to a wider range of third-party tools or community resources, though GCP's ecosystem is rapidly growing.  
    * Service-to-service mapping: Specific services might have different feature sets or operational nuances compared to equivalents on other clouds.  
* **Alternatives Considered:** Amazon Web Services (AWS), Microsoft Azure.

### ADR-009: AI Agent Orchestration Framework

* **Status:** Accepted  
* **Context:** We require a framework to structure, manage, and execute multi-agent AI systems for features like "Create from Link" (fetching, summarizing, tagging content) and AI-driven content regeneration (title, summary, tags).  
* **Decision:** We will use **CrewAI**.  
* **Consequences:**  
  * **Pros:**  
    * Specifically designed for orchestrating role-playing, autonomous AI agents.  
    * Promotes a clear structure with Roles, Goals, Tasks, and Tools.  
    * Python-based, aligning with the common language for AI/ML development and many LLM SDKs.  
    * Allows for complex workflows by breaking them down into manageable agent tasks.  
    * Open source with an active community.  
  * **Cons:**  
    * CrewAI is a Python library. Our primary backend is Node.js/TypeScript. This necessitates an integration strategy:  
      * **Option A (Preferred):** Run CrewAI agents as separate Python microservices (e.g., on Cloud Run or GKE) invoked via API calls from the Next.js backend. This maintains separation of concerns but adds inter-service communication.  
      * **Option B (Less Preferred for Production):** Explore experimental ways to call Python from Node.js (e.g., python-shell), which can be complex to manage in production for non-trivial applications.  
    * Learning curve for CrewAI concepts and best practices.  
    * Managing dependencies for both Node.js and Python environments if co-located or closely interacting.  
* **Alternatives Considered:** LangChain (more general-purpose LLM framework, can build agents but less opinionated on orchestration), Microsoft Autogen, building a custom orchestration layer (high effort), direct LLM calls without an agent framework (less scalable for complex tasks).  
* **Further Actions:** Define the specific integration pattern between the Next.js backend and CrewAI Python services (likely API-based).

### ADR-010: Primary LLM Provider and Model Strategy

* **Status:** Draft (Requires further research and decision)  
* **Context:** CrewAI agents require access to Large Language Models (LLMs) to perform their tasks (e.g., summarization, title generation, tagging, content analysis). We need to select a primary LLM provider and a strategy for choosing specific models, considering factors like capability, cost, speed, context window size, data privacy, and ease of integration, especially within GCP.  
* **Decision:** *(To be determined. Options include but are not limited to:)*  
  * **Option A: Google Vertex AI Foundational Models:** Leverage models like Gemini directly within the GCP ecosystem.  
    * *Pros:* Deep integration with GCP, potential for better performance/latency within GCP, unified billing, data governance within GCP.  
    * *Cons:* Model capabilities and pricing compared to other leading models need careful evaluation.  
  * **Option B: OpenAI Models via API (e.g., GPT-4, GPT-4o, GPT-3.5-turbo):** Utilize OpenAI's established models.  
    * *Pros:* High capability, widely used, extensive documentation and community support.  
    * *Cons:* External API calls (latency, data egress), separate billing and vendor management, data privacy considerations for sending data outside GCP (unless using Azure OpenAI Service with VNet integration).  
  * **Option C: Other Third-Party Models (e.g., Anthropic Claude, Cohere):** Access via their respective APIs.  
    * *Pros:* May offer specific strengths or pricing advantages for certain tasks.  
    * *Cons:* Similar to OpenAI regarding external API calls and vendor management.  
  * **Option D: Open Source Models Hosted on GCP (e.g., on Vertex AI Model Garden or GKE):**  
    * *Pros:* Maximum control, potential cost savings at scale, data privacy.  
    * *Cons:* Significant operational overhead for hosting, scaling, and maintaining models; typically requires more MLOps expertise.  
  * **Option E: Hybrid Approach:** Use different providers/models for different tasks based on a cost/benefit/capability analysis.  
    * *Pros:* Optimizes for specific needs.  
    * *Cons:* Increased complexity in managing multiple integrations and decision logic.  
* **Consequences:** (Will depend on the chosen option)  
  * Cost structure for AI features.  
  * Performance and quality of AI-generated content.  
  * Development effort for integration.  
  * Operational complexity.  
  * Data privacy and compliance implications.  
* **Alternatives Considered:** Sticking to a single model for all tasks vs. task-specific models.  
* **Further Actions:** Conduct a comparative analysis of leading LLM options based on the specific needs of FR-CARD-3, FR-CARD-4, and the AI-enhanced regeneration features. Make a decision and document it.

ADR Process:  
Store ADRs as markdown files (e.g., in /docs/adrs or a dedicated ADRs section in the project wiki/documentation). Review changes and additions via Pull Requests if in a Git repository, or via team review meetings. This ensures versioning and collaborative agreement.