## Technical Design Document (TDD)

Product: Web-Based Knowledge Card System (v3)  
Version: 1.2 (Based on PRD v3.8)  
Date: 2025-05-10  
Status: Draft  
**1\. Introduction & Goals**

This document outlines the proposed technical architecture and design for implementing the Web-Based Knowledge Card System as defined in PRD v3.8. It translates the functional and non-functional requirements into a technical blueprint for the engineering team.

* **Goal Stage 1 (Local MVP \- Completed):** Implemented a locally runnable application focusing on core text-based block editing (with autosave), manual tagging, folder management, bulk card assignment, local keyword search, and JSON data export. Required local user setup (Node, Docker for PostgreSQL). Data stored locally in PostgreSQL. *Note: Significant page load latencies (5-10 seconds) were observed in this stage, requiring optimization before proceeding further.*  
* **Goal Stage 2 (GCP Production & Core AI Enhancements \- Current Focus):** Deploy the application to **Google Cloud Platform (GCP)**, building upon an optimized Stage 1 foundation. Implement a manual hashtag system. **Overhaul UI/UX for production, driven by Figma designs and implemented with Chakra UI.** Enable core AI features using **CrewAI** (AI-Powered "Create from Link", AI-Enhanced Card Generation & On-Demand Summarization). Implement cloud storage (Google Cloud Storage), Social Logins. Set up Semantic Search foundation (backend embeddings with pgvector on Google Cloud SQL). Conduct a "Database Rethink" for scalability. Establish robust DevOps practices on GCP (IaC, CI/CD, Monitoring).  
* **Goal Stage 2+ (Advanced Interaction & Features \- Future):** Build upon Stage 2 to add advanced knowledge synthesis features like RAG Chat, Semantic Search UI, Basic Dashboard Stats, Knowledge Visualizations, and other AI-driven insights.

*(Reference: PRD v3.8 Sections 1, 6\)*

1.A Pre-Stage 2 Optimizations (Addressing Stage 1 Performance Issues)

* Objective: To diagnose and resolve the significant page load latencies (reported as 5-10 seconds) in the Stage 1 MVP. This optimization phase is critical to ensure a performant foundation before building Stage 2 features and migrating to GCP.  
* Scope: Focus on the existing Stage 1 Next.js/React frontend, Next.js API routes, Prisma ORM, and local PostgreSQL database.  
* Target Outcome: Reduce average page load times for common views and interactions to an acceptable level (e.g., \< 2-3 seconds for typical page loads, \< 500ms for most interactions locally).  
* Actionable Steps for Optimization:  
  * A. Backend & API Optimization (Next.js API Routes):  
    1. Profiling API Routes:  
       * Identify slow API endpoints using browser developer tools (Network tab) or server-side logging.  
       * Measure response times for all critical API routes (e.g., fetching cards, folders, tags).  
    2. Review Business Logic:  
       * Analyze code within slow API routes for synchronous blocking operations or computationally expensive tasks.  
       * Refactor complex data transformations or manipulations to be more efficient.  
       * Consider offloading truly long-running, non-critical tasks to background jobs if any exist (though Stage 1 is primarily synchronous).  
    3. Middleware Review:  
       * Assess any custom Next.js middleware for performance impact.  
  * B. Database Query Optimization (Prisma & PostgreSQL):  
    1. Enable Query Logging:  
       * Configure Prisma to log all generated SQL queries (e.g., prisma.$on('query', ...)).  
    2. Analyze Slow Queries:  
       * For slow API responses, identify the corresponding database queries.  
       * Use EXPLAIN ANALYZE directly in PostgreSQL for these slow queries to understand their execution plans and identify bottlenecks (e.g., full table scans, inefficient joins).  
    3. Optimize Prisma Queries:  
       * Reduce Data Fetched: Use select and include options in Prisma sparingly and precisely to fetch only necessary data. Avoid over-fetching.  
       * Address N+1 Problems: Identify and refactor instances where multiple queries are made in a loop (e.g., fetching N cards and then N separate queries for their tags). Use Prisma's relation query capabilities or batching techniques.  
       * Efficient Filtering & Sorting: Ensure filters (where clauses) and sorting (orderBy clauses) can leverage database indexes.  
    4. Database Indexing:  
       * Verify that appropriate indexes exist on columns used in WHERE clauses, JOIN conditions, and ORDER BY clauses in PostgreSQL.  
       * Key columns to check: userId, folderId, tagId on Card and related tables; name on Tag and Folder; any foreign keys.  
       * Create missing indexes using Prisma migrations (@db.Index or raw SQL).  
    5. Connection Pooling:  
       * Ensure Prisma's database connection pooling is configured appropriately (though defaults are usually fine for local development, it's good to be aware of).  
  * C. Frontend Performance Optimization (Next.js, React, Chakra UI, Zustand):  
    1. Profiling Frontend Rendering:  
       * Use React Developer Tools Profiler to identify slow-rendering components and unnecessary re-renders.  
       * Analyze component mount times and update times.  
    2. Optimize Component Rendering:  
       * Memoization: Apply React.memo to functional components that render frequently with the same props.  
       * useCallback & useMemo: Use these hooks to memoize functions and values, preventing unnecessary re-creations and re-renders of child components.  
       * Virtualization for Long Lists: If displaying very long lists of cards or items, implement list virtualization (e.g., using react-window or react-virtualized) so only visible items are rendered.  
    3. Data Fetching on the Client:  
       * Review how data is fetched for pages/components (e.g., in useEffect). Ensure loading states are handled gracefully.  
       * Minimize data fetched initially; implement pagination or infinite scrolling for large datasets if not already present.  
       * (For future reference: Stage 2 will consider SWR/React Query for optimized client-side data fetching).  
    4. State Management (Zustand):  
       * Ensure Zustand store selectors are specific and optimized to prevent components from re-subscribing and re-rendering if the particular slice of state they depend on hasn't changed.  
       * Avoid putting excessively large or frequently changing volatile data directly into global state if it causes widespread re-renders.  
    5. Bundle Size Analysis (Next.js):  
       * Use next/bundle-analyzer to inspect the JavaScript bundle sizes for each page.  
       * Identify and optimize or code-split large dependencies or custom code chunks that might be slowing down initial page interactivity.  
    6. Chakra UI Usage:  
       * While generally performant, ensure that style props are not being used in a way that causes excessive re-computation on deeply nested or frequently updated components. For highly dynamic styles, consider alternatives like sx prop or pre-compiled styles if a bottleneck is identified.  
    7. Image Optimization (if applicable in Stage 1):  
       * Ensure any images are appropriately sized and compressed. Use Next.js Image component (next/image) for automatic optimization if images are a factor.  
  * D. BlockNote Editor Performance (if relevant):  
    1. If pages with the BlockNote editor are particularly slow, especially with large content:  
       * Investigate if rendering or hydration of the editor content is a bottleneck.  
       * Check for any known performance issues or optimization tips related to the version of BlockNote being used.  
  * E. General Debugging & Tools:  
    1. Browser Developer Tools: Extensively use the Network tab (to see API timings, payload sizes), Performance tab (to profile JavaScript execution and rendering), and Console (for errors).  
    2. Next.js Dev Toolbar: Pay attention to build indicators and information provided.  
* Documentation of Findings: Any significant optimizations or changes made should be briefly documented (e.g., in commit messages, or a short summary report) to inform future development and the "Database Rethink" activity.

**2\. High-Level Architecture**

The system will adopt a full-stack framework approach using Next.js with TypeScript.

* **Stage 1 (Completed):**  
  * Frontend: Next.js React components (App Router) served by the Next.js server.  
  * Backend: Next.js API Routes handling business logic.  
  * Database: Local PostgreSQL instance (managed via Docker Compose) accessed via Prisma ORM.  
  * State Management: Zustand for frontend state.  
  * Editing: Block-based editor component (BlockNote) integrated into the frontend, saving content as JSON.  
  * UI: Component library (Chakra UI).  
  * Execution: Ran locally via npm run dev.  
* **Stage 2 (Current Focus \- GCP):**  
  * Frontend: Remains Next.js React components. **UI development will be based on detailed Figma designs, implemented using the Chakra UI component library and its theming capabilities.**  
  * Backend:  
    * Next.js API Routes, deployed as containers (Docker) on scalable **GCP compute (e.g., Google Cloud Run, Google Kubernetes Engine \- GKE)**.  
    * **CrewAI (Python) services** for AI agent orchestration, likely deployed as separate containerized microservices on GCP (e.g., Cloud Run, GKE), invoked via API by the Next.js backend.  
  * Database: Managed PostgreSQL on **Google Cloud SQL for PostgreSQL**, with pgvector extension enabled.  
  * Vector Storage: Integrated within Cloud SQL PostgreSQL using pgvector.  
  * Caching: Managed Redis via **Google Cloud Memorystore for Redis** for API response caching and BullMQ job queue management.  
  * File Storage: **Google Cloud Storage** for media blocks (images, videos).  
  * Job Queue: BullMQ with Redis backend (Memorystore) for asynchronous AI tasks.  
  * AI Integration:  
    * **CrewAI** for AI agent orchestration.  
    * Abstracted AIService module connecting to LLM APIs (Provider TBD, see ADR-010), with API keys managed via **Google Secret Manager**.  
  * Infrastructure: Managed via Terraform on **GCP**. Includes Load Balancing (Google Cloud Load Balancing), CDN (Google Cloud CDN), scalable compute (Cloud Run/GKE), Cloud SQL, Memorystore, Cloud Storage, IAM, Secret Manager.  
  * DevOps: GitHub Actions (or Google Cloud Build) for full CI/CD pipeline (testing, build, deploy to GCP), Sentry (or Google Cloud Error Reporting) for error tracking, **Google Cloud's operations suite** (Cloud Monitoring, Cloud Logging) for monitoring/logging.  
* **Stage 2+ (Future):** Builds on Stage 2 GCP infrastructure, primarily adding more complex backend logic (RAG orchestration, advanced analysis) and corresponding frontend components.

*(Reference: PRD v3.8 Sections 5, 6; ADRs)*

**(Diagrams \- Placeholder):** Links to Component Diagram, Data Flow Diagrams (Auth, Create from Link with CrewAI, AI Regeneration, RAG Chat), Cloud Infrastructure Diagram (GCP) to be added here. **A section for UI Style Guide/Component Library documentation derived from Figma and Chakra UI theme should also be considered.**

**3\. Data Model / Schema Design**

(Based on Prisma, using PostgreSQL provider on Google Cloud SQL)  
Activity: A "Database Rethink" (NFR-DB-RETHINK-1) is planned for Stage 2 to review and optimize for performance and scalability on GCP.

* **User**: id, name, email (unique), password (hashed), createdAt, updatedAt. Relations: Card\[\], Folder\[\], File\[\] (Stage 2), Account\[\] (Stage 2), Session\[\] (Stage 2).  
* **Account**: (For NextAuth Social Logins \- Stage 2\) As defined by NextAuth Adapter. Relation: User.  
* **Session**: (For NextAuth DB Sessions \- Stage 2, if used instead of JWT) As defined by NextAuth Adapter. Relation: User.  
* **Card**: id, title (String), content (Jsonb \- BlockNote format), userId, folderId (String, optional, nullable, onDelete: SetNull), fileId (String, optional, nullable \- Stage 2), sourceUrl (String, optional, nullable), aiSummary (Jsonb, optional, nullable \- Stage 2, for AI generated summary/content from link or regeneration), aiSummaryForRag (Text, optional, nullable \- Stage 2, AI-generated distilled summary specifically for RAG indexing), embedding (vector type via pgvector \- Stage 2, for semantic search on full content or RAG summary), createdAt, updatedAt. Relations: User, Folder?, File?, Tag\[\]. Indexed fields: title (FTS), content (FTS via generated column/function), userId, folderId, embedding (HNSW/IVFFlat index \- Stage 2).  
* **Tag**: id, name (String, unique \- includes manual tags and hashtags like '\#project'). Relations: Card\[\]. Indexed fields: name.  
  * *Note:* Hashtags will be stored as regular tags, prefixed with '\#' in the name field to distinguish them if needed for specific UI treatment or filtering, but share the same underlying Tag model.  
* **Folder**: id, name (String), userId, parentId (String, optional, nullable, onDelete: Cascade), createdAt, updatedAt. Relations: User, Folder? (parent), Folder\[\] (children), Card\[\]. @@unique(\[userId, parentId, name\]). Indexed fields: userId, parentId.  
* **File**: (Stage 2 \- For Media Blocks) id, filename, mimeType, size, userId, storageBucket (String \- Google Cloud Storage bucket), storageKey (String \- object path in bucket), createdAt. Relation: User, Card?.

*(Reference: PRD v3.8 Section 2; ADRs)*

**4\. API Design (High-Level Contracts)**

(Standard RESTful principles. Authentication via NextAuth.js session/JWT)

* **Auth (/api/auth/...)**: Handled largely by NextAuth.js. Custom: /register, /me, /user/profile.  
* **Cards (/api/cards/...)**:  
  * POST /: Create card.  
  * GET /: List user's cards.  
  * GET /{cardId}: Get single card.  
  * PUT /{cardId}: Update card (title, content, tags/hashtags, folderId). Supports autosave triggers.  
  * DELETE /{cardId}: Delete card.  
  * **(Stage 2\)** POST /create-from-link: Trigger link processing via CrewAI (FR-CARD-3).  
    * Request: { "url": "string" }  
    * Response (async): { "jobId": "string", "status": "processing" } or direct card data if synchronous.  
  * **(Stage 2\)** POST /{cardId}/regenerate/title: Trigger AI title regeneration via CrewAI (FR-CARD-4).  
    * Response: { "suggestions": \["Title 1", "Title 2"\] } or { "newTitle": "string" } after diff/preview acceptance.  
  * **(Stage 2\)** POST /{cardId}/regenerate/tags: Trigger AI tags regeneration via CrewAI (FR-CARD-4).  
    * Response: { "suggestedTags": \["tag1", "\#hashtag2"\] } or updated card tags after diff/preview acceptance.  
  * **(Stage 2\)** POST /{cardId}/regenerate/content: Trigger AI content regeneration/summarization via CrewAI (FR-CARD-4).  
    * Response: { "regeneratedContent": { ...jsonb... } } for diff/preview, or updated card content.  
* **Folders (/api/folders/...)**: Standard CRUD.  
* **Tags (/api/tags/...)**: (Includes Hashtags)  
  * GET /: List user's unique tags/hashtags.  
  * (Potentially POST/PUT/DELETE if direct tag management beyond card association is needed).  
* **Bulk Ops (/api/bulk/...)**: (Stage 1 features).  
* **Search (/api/search/...)**:  
  * GET /: Keyword search (PostgreSQL FTS).  
  * **(Stage 2+)** GET /semantic: Semantic search.  
* **Data Export (/api/export)**: (Stage 1 feature).  
* **Data Import (/api/import)**: **(Stage 2\)** POST /: Import user data from JSON (FR-DATA-2).  
* **Files (/api/files/...)**: **(Stage 2\)** Endpoint for Google Cloud Storage pre-signed URLs for uploads.  
* **Health (/api/health)**: Basic health check.

*(Reference: PRD v3.8 Section 2\)*

**5\. Detailed Component Design (Key Areas)**

* **Frontend Components:**  
  * Development will be guided by **Figma designs** to ensure visual consistency and adherence to the desired UX. The "Production UI Overhaul" (FR-UX-PROD-UI) will involve refining existing components and creating new ones based on these Figma specifications, implemented using Chakra UI.  
  * Existing: BlockEditor (BlockNote), BlockRenderer, TagInput (to be enhanced for hashtags and Figma design alignment), FolderTree (design to be reviewed against Figma), CardList (design to be reviewed), CardDisplay (design to be reviewed), SearchInput/SearchResults, Modals (Create/Rename Folder, Delete Confirmation \- designs to be reviewed), ExportButton, OnboardingComponent (design to be reviewed).  
  * **Stage 2 New/Enhanced (all to be designed in Figma and implemented with Chakra UI):**  
    * HashtagInput: Component for creating/managing hashtags.  
    * CreateFromLinkModal: UI for URL input and displaying AI-generated card preview.  
    * AIRegenerationPanel: UI for triggering AI regeneration (title, content, tags) and displaying diff/preview with accept/cancel options.  
    * MediaBlockComponent: For handling image/video uploads and display, integrating with Google Cloud Storage.  
    * Comprehensive review and potential redesign of all core UI elements (navigation, layout, forms, buttons, etc.) as part of the FR-UX-PROD-UI.  
* **Backend Services/Modules (Conceptual):**  
  * Existing: AuthService, CardService, FolderService, TagService, SearchService (Keyword FTS), ExportService, BulkOperationsService.  
  * **Stage 2 New/Enhanced:**  
    * LinkProcessingService: Orchestrates CrewAI agents for "Create from Link."  
    * AIRegenerationService: Orchestrates CrewAI agents for title/content/tag regeneration.  
    * CrewAIOrchestrator (or similar): Module for interfacing with CrewAI Python services (e.g., making API calls to them).  
    * FileStorageService: Interacts with Google Cloud Storage for media.  
    * ImportService: Handles JSON data import.  
    * VectorEmbeddingService: Generates embeddings for Semantic Search Foundation.  
    * (Job Queue integration with BullMQ for async AI tasks).

*(Reference: PRD v3.8 Section 2\)*

**6\. Technology Choices & Rationale**

* Framework: Next.js w/ TypeScript  
* UI Library: **Chakra UI**. Chosen for its composability, theming capabilities (crucial for implementing custom Figma designs), and built-in accessibility. It will be used to translate Figma designs into functional React components.  
* State Management: Zustand  
* Block Editor: BlockNote  
* Database: **Google Cloud SQL for PostgreSQL** w/ Prisma ORM  
* Vector Storage: pgvector extension on Google Cloud SQL  
* Authentication: NextAuth.js  
* **AI Agent Orchestration: CrewAI (Python)**  
* **(Stage 2\)** Caching: **Google Cloud Memorystore for Redis**  
* **(Stage 2\)** File Storage: **Google Cloud Storage**  
* **(Stage 2\)** Job Queue: BullMQ w/ Redis (Memorystore backend)  
* **(Stage 2\)** AI LLM Provider: TBD (See ADR-010 \- e.g., Google Vertex AI, OpenAI)  
* DevOps: GitHub, **Google Cloud Build / GitHub Actions (for GCP)**, Docker, Terraform (for GCP), Sentry / **Google Cloud Error Reporting**, **Google Cloud's operations suite**.

*(Reference: PRD v3.8 Section 5; ADRs)*

**7\. Scalability Considerations**

* Stateless Backend (Next.js API routes, CrewAI services deployed as containers on Cloud Run/GKE).  
* Asynchronous Processing (BullMQ on GCP for AI tasks).  
* Caching (**Google Cloud Memorystore for Redis**).  
* Database (**Google Cloud SQL for PostgreSQL** scaling options, connection pooling, effective indexing from "Database Rethink").  
* Vector Search (pgvector indexing and query optimization).  
* CDN (**Google Cloud CDN**) for frontend assets and potentially cached API responses.  
* Load Balancing (**Google Cloud Load Balancing**).  
* Target: Define specific concurrent user and data volume targets for Stage 2 as part of NFRs.

**8\. Security Considerations**

* Authentication (NextAuth.js, Social Logins via GCP integration).  
* Authorization (ownership checks in APIs).  
* Input Validation (Zod).  
* Secrets Management (**Google Secret Manager** for API keys, DB credentials).  
* Dependencies (Scanning via CI/CD).  
* HTTPS.  
* Rate Limiting (via API Gateway or Load Balancer on GCP).  
* SSRF Protection for "Create from Link."  
* Cloud Security (GCP Security Groups/Firewall Rules, IAM, Least Privilege).  
* Secure interaction between Next.js backend and Python CrewAI services (e.g., private networking on GCP, authenticated API calls).

**9\. Deployment Strategy Overview**

* **Stage 1 (Completed):** Local development environment.  
* **Stage 2 (GCP):**  
  * Infrastructure on **GCP** managed via Terraform.  
  * CI/CD via **Google Cloud Build or GitHub Actions** deploying containerized applications (Next.js, Python/CrewAI services) to **Google Cloud Run or GKE**.  
  * Separate environments (dev, staging, production) on GCP.  
  * Database Migrations via prisma migrate deploy in the CI/CD pipeline.

**10\. Open Technical Questions**

* Final choice for LLM Provider (ADR-010).  
* Specific GCP compute services for Next.js backend and Python/CrewAI services (Cloud Run vs. GKE) \- detailed design needed.  
* Optimal pgvector indexing strategy and performance tuning on Cloud SQL (part of "Database Rethink").  
* Detailed API contract and communication pattern between Next.js backend and CrewAI Python services.  
* Specific outcomes and implementation details from the "Database Rethink."  
* Detailed prompt engineering strategies for CrewAI agents for all AI features.  
* Error handling and retry logic for distributed AI tasks involving CrewAI and external LLMs.  
* Scalability testing strategy for AI features on GCP.  
* Cost optimization strategies for GCP services, especially AI/LLM usage.  
* File metadata schema details for Google Cloud Storage integration.  
* **Workflow for translating Figma designs into Chakra UI components and theme; establishing a shared design language/system between Figma and the codebase.**

## Tech Lead Review & Assessment (TDD v1.2)

This TDD v1.2 has been significantly updated to reflect the project's shift to **Google Cloud Platform (GCP)** for Stage 2, the introduction of **CrewAI** for AI agent orchestration, alignment with **PRD v3.8**, and an **emphasis on Figma-driven UI design implemented with Chakra UI.**

**Key Updates Incorporated:**

* Complete transition from AWS to GCP for all cloud infrastructure, services, and DevOps tooling.  
* Integration of CrewAI as the primary framework for AI-powered features.  
* Updated Stage 2 goals to match PRD v3.8, including the manual hashtag system, **production UI/UX overhaul guided by Figma**, and the "Database Rethink" activity.  
* Data model changes to support hashtags and a potential dedicated RAG summary field.  
* Revised API design to include endpoints for new AI regeneration features.  
* Technology choices now accurately reflect the GCP stack, CrewAI, and the role of Chakra UI in implementing Figma designs.  
* Scalability, Security, and Deployment sections are now GCP-centric.  
* Open technical questions have been updated to focus on GCP specifics, CrewAI integration, LLM choices, and the Figma-to-ChakraUI workflow.

**Remaining Areas for Clarification / Detailed Design:**

1. **CrewAI Integration Architecture:** The precise mechanism for Next.js (Node.js) to invoke and manage CrewAI (Python) services needs detailed design.  
2. **Database Rethink Outcomes:** The TDD acknowledges this activity; its outcomes will lead to more specific schema and indexing decisions.  
3. **LLM Provider Selection (ADR-010):** This is a critical pending decision.  
4. **API Schema Detail:** Formal OpenAPI specifications for Stage 2 APIs are highly recommended.  
5. **Diagrams:** Core architecture, data flow, GCP infrastructure, and potentially UI component hierarchy/style guide diagrams are essential.  
6. **Detailed Component Design & Figma-to-Code Workflow:** While Figma is the design source and Chakra UI the tool, the process for translating designs, creating/customizing Chakra UI themes based on Figma, and ensuring component consistency needs to be established. This includes how AI coding assistants will be leveraged in this translation.

**TL Recommendations & Alternatives:**

* **Prioritize CrewAI Integration Design.**  
* **GCP Service Selection:** Conduct a trade-off analysis for compute services.  
* **Iterate on "Database Rethink."**  
* **Formalize API Specs.**  
* **Establish Figma-to-Chakra UI Workflow:** Define how design tokens, component styles, and responsive behaviors from Figma will be mapped to Chakra UI's theming system and component implementations. Consider creating a shared Chakra UI theme file that directly reflects the Figma design system.

**Draft Rating:**

* **Completion:** 4.8 / 5.0 (Very comprehensive, reflecting current project direction).  
* **Quality/Accuracy:** 4.8 / 5.0 (Accurately reflects strategic shifts. Key decisions and areas for further detail are well-identified).

This TDD v1.2 provides an even stronger technical blueprint for Stage 2\. The next steps should focus on resolving the key open questions and proceeding with detailed design for the prioritized Stage 2 features, including the detailed UI design in Figma and its translation strategy.