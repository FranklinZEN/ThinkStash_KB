## **Technical Design Document (TDD) \- REVISED**

Product: Web-Based Knowledge Card System (v3)  
Version: 1.1 (Based on PRD v3.6 Rev 1\)  
Date: 2025-04-21  
Status: Draft (Revised)  
**1\. Introduction & Goals**

This document outlines the proposed technical architecture and design for implementing the Web-Based Knowledge Card System as defined in PRD v3.6 Rev 1\. It translates the functional and non-functional requirements into a technical blueprint for the engineering team.

* **Goal Stage 1 (Local MVP):** Implement a locally runnable application focusing on core text-based block editing (with autosave), manual tagging, folder management (hierarchy, create, rename, delete \- with safe delete behavior, move folder), bulk card assignment (folder/tag), keyword search, basic dashboard stats, and JSON data export. Requires local user setup (Node, Docker for PostgreSQL). Data stored locally in PostgreSQL.  
* **Goal Stage 2 (Cloud & Foundational AI/Synthesis):** Deploy the application to AWS, support manual data import (via JSON), implement cloud storage (S3), enable foundational AI features (Title Suggestion, Link-to-Card w/ Summary/Tags using OpenAI), Semantic Search backend (using PostgreSQL/pgvector), initial visualizations (Topic Clouds, Network Graphs), and robust DevOps practices (IaC, CI/CD, Monitoring).  
* **Goal Stage 2+ (Advanced Interaction):** Build upon Stage 2 to add advanced knowledge synthesis features like RAG Chat, Semantic Search UI, AI Spark Prompts, Concept Juxtaposition, etc.

*(Reference: PRD v3.6 Rev 1 Sections 1, 6\)*

**2\. High-Level Architecture**

The system will adopt a full-stack framework approach using Next.js with TypeScript.

* **Stage 1:**  
  * Frontend: Next.js React components (App Router) served by the Next.js server.  
  * Backend: Next.js API Routes handling business logic.  
  * Database: Local PostgreSQL instance (managed via Docker Compose) accessed via Prisma ORM.  
  * State Management: Zustand for frontend state.  
  * Editing: Block-based editor component (primary: BlockNote) integrated into the frontend, saving content as JSON, with autosave functionality.  
  * UI: Component library (primary: Chakra UI).  
  * Execution: Runs locally via npm run dev after user setup. Includes JSON data export feature.  
* **Stage 2:**  
  * Frontend: Remains Next.js React components.  
  * Backend: Next.js API Routes, deployed as containers (Docker) on AWS ECS/Fargate. Introduction of background workers (BullMQ/Redis) for asynchronous tasks.  
  * Database: Managed PostgreSQL (AWS RDS) in the cloud, with pgvector extension enabled.  
  * Vector Storage: Integrated within RDS PostgreSQL using pgvector extension.  
  * Caching: Managed Redis (AWS ElastiCache) for API response caching and BullMQ job queue management.  
  * File Storage: AWS S3 for media blocks.  
  * Job Queue: BullMQ with Redis backend.  
  * AI Integration: Abstracted AIService module initially connecting to OpenAI API (text-embedding-ada-002 for embeddings) via preferred secure method (e.g., direct API calls with keys from Secrets Manager, considering MCP standard). Requires secure API key management.  
  * Infrastructure: Managed via Terraform on AWS. Includes Load Balancer (ALB), potentially CDN (CloudFront), ECS, RDS, ElastiCache, S3, IAM, Secrets Manager.  
  * DevOps: GitHub Actions for full CI/CD pipeline (testing, build, deploy to AWS), Sentry for error tracking, CloudWatch for monitoring/logging.  
* **Stage 2+:** Builds on Stage 2 infrastructure, primarily adding more complex BE logic (RAG orchestration, advanced analysis) and corresponding FE components (Chat UI, advanced visualizations).

*(Reference: PRD v3.6 Rev 1 Sections 5, 6; Stakeholder Decisions)*

**(Diagrams \- Placeholder):** Links to Component Diagram, Data Flow Diagrams (Auth, Link-to-Card, RAG Chat), Cloud Infrastructure Diagram (AWS) to be added here.

**3\. Data Model / Schema Design**

(Based on Prisma, using PostgreSQL provider)

* **User**: id, name, email (unique), password (hashed), createdAt, updatedAt. Relations: Card\[\], Folder\[\], File\[\] (Stage 2), Account\[\] (Stage 2), Session\[\] (Stage 2). *(Optional: hasCompletedOnboarding \- Boolean)*  
* **Account**: (For NextAuth Social Logins \- Stage 2\) As defined by NextAuth Adapter. Relation: User.  
* **Session**: (For NextAuth DB Sessions \- Stage 2, if used instead of JWT) As defined by NextAuth Adapter. Relation: User.  
* **Card**: id, title (String), content (Jsonb), userId, folderId (String, optional, nullable, onDelete: SetNull), fileId (String, optional, nullable \- Stage 2), sourceUrl (String, optional, nullable), aiSummary (String, optional, nullable \- Stage 2), embedding (vector type via pgvector \- Stage 2), createdAt, updatedAt. Relations: User, Folder?, File?, Tag\[\]. Indexed fields: title (FTS), content (FTS via generated column/function), userId, folderId, embedding (HNSW/IVFFlat index \- Stage 2).  
* **Tag**: id, name (String, unique \- consider case handling strategy). Relations: Card\[\]. Indexed fields: name.  
* **Folder**: id, name (String), userId, parentId (String, optional, nullable, onDelete: Cascade), createdAt, updatedAt. Relations: User, Folder? (parent), Folder\[\] (children), Card\[\]. @@unique(\[userId, parentId, name\]). Indexed fields: userId, parentId.  
* **File**: (Stage 2 \- For Media Blocks) id, filename, mimeType, size, userId, s3Bucket, s3Key, createdAt. Relation: User, Card?.

*(Reference: PRD v3.6 Rev 1 Section 2; TDD Tickets KC-3.1, KC-20.1-BLOCK, KC-20.2, KC-40)*

**4\. API Design (High-Level Contracts)**

(Standard RESTful principles. Authentication via NextAuth.js session/JWT)

* **Auth (/api/auth/...)**: Handled largely by NextAuth.js. Custom: /register, /me, /user/profile.  
* **Cards (/api/cards/...)**:  
  * POST /: Create card (KC-23-BLOCK).  
  * GET /: List user's cards (KC-CARD-BE-4-BLOCK).  
  * GET /{cardId}: Get single card (KC-CARD-BE-1-BLOCK).  
  * PUT /{cardId}: Update card (title, content, tags, folderId) (KC-CARD-BE-2-BLOCK, KC-44, KC-CARD-AUTOSAVE-BE-1). Supports autosave triggers.  
  * DELETE /{cardId}: Delete card (KC-CARD-BE-3-BLOCK).  
  * *(Stage 2\)* POST /create-from-link: Trigger link processing (FR-CARD-3).  
* **Folders (/api/folders/...)**:  
  * POST /: Create folder (KC-42.1).  
  * GET /: List user's folders (flat or nested TBD) (KC-ORG-BE-1).  
  * PUT /{folderId}: Rename or Move folder (update name and/or parentId) (KC-42.2, KC-ORG-BE-2).  
  * DELETE /{folderId}: Delete folder (checks if empty of sub-folders, orphans cards) (KC-42.3).  
* **Tags (/api/tags/...)**:  
  * GET /: List user's unique tags.  
* **Bulk Ops (/api/bulk/...)**: *(Stage 1\)*  
  * POST /assign-folder: Assign multiple cards to folder (KC-BULK-OPS-BE-1).  
  * POST /assign-tag: Add tag to multiple cards (KC-BULK-OPS-BE-1).  
* **Search (/api/search/...)**:  
  * GET /: Keyword search using PostgreSQL FTS (KC-51/52 \- PG Version). Params: q.  
  * *(Stage 2+)* GET /semantic: Semantic search using pgvector. Params: q.  
* **Analytics (/api/analytics/...)**:  
  * GET /stats: Get basic stats (KC-61).  
* **Data Export (/api/export)**: *(Stage 1\)*  
  * GET /: Export user data as JSON (KC-DATA-EXPORT-BE-1).  
* **AI (/api/ai/...)**: *(Stage 2+)* Endpoints for Title Suggestion, Summarization, RAG Chat, etc. (As previously listed).  
* **Files (/api/files/...)**: *(Stage 2\)* Endpoint for S3 pre-signed URLs (KC-STORAGE-BE-2).  
* **Health (/api/health)**: Basic health check endpoint (KC-INFRA-BE-1).

*(Reference: PRD v3.6 Rev 1 Section 2; TDD JIRA Tickets)*

**5\. Detailed Component Design (Key Areas)**

* **Frontend Components:** BlockEditor (with autosave integration), BlockRenderer, TagInput, FolderTree (with DND for move folder), CardList (with multi-select for bulk ops), CardDisplay, SearchInput/SearchResults, DashboardStats, StatsCard, CreateFolderModal, RenameFolderModal, DeleteConfirmationDialog, BulkActionToolbar, ExportButton, OnboardingComponent. *(Stage 2 adds Media Blocks, Visualizations)*.  
* **Backend Services/Modules (Conceptual):** AuthService, CardService (handles update/autosave), FolderService (handles move logic, circular checks, safe delete), TagService, SearchService (Keyword FTS query logic), AnalyticsService, ExportService, BulkOperationsService. *(Stage 2 adds AI, LinkProcessing, FileStorage, JobQueue, VectorSearch services)*.

*(Reference: PRD v3.6 Rev 1 Section 2; TDD JIRA Tickets)*

**6\. Technology Choices & Rationale**

* Framework: Next.js w/ TypeScript  
* UI Library: Chakra UI  
* State Management: Zustand  
* Block Editor: BlockNote  
* Database: PostgreSQL w/ Prisma ORM  
* Vector Storage: pgvector extension on PostgreSQL (Rationale: Simplifies Stage 2 infra by co-locating vectors with relational data; suitable for moderate scale; avoids managing separate DB service initially).  
* Authentication: NextAuth.js  
* *(Stage 2\)* Caching: Redis (via AWS ElastiCache)  
* *(Stage 2\)* File Storage: AWS S3  
* *(Stage 2\)* Job Queue: BullMQ w/ Redis  
* *(Stage 2\)* AI Provider: OpenAI (via AIService abstraction, considering MCP standard)  
* *(Stage 2\)* Visualization: react-flow (Network Graphs), others TBD.  
* DevOps: GitHub, GitHub Actions, Docker, Terraform (AWS \- Stage 2), Sentry (Stage 2), CloudWatch (Stage 2).

*(Reference: PRD v3.6 Rev 1 Section 5; Stakeholder Decisions)*

**7\. Scalability Considerations**

*(Largely unchanged, emphasizes Stage 2\)* Stateless Backend, Asynchronous Processing (BullMQ), Caching (Redis), Database (RDS scaling options, connection pooling, appropriate indexing including GIN/GIST for FTS and HNSW/IVFFlat for pgvector), CDN, Load Balancing. Target: 100 concurrent users initially for Stage 2\.

*(Reference: PRD v3.6 Rev 1 Section 3 \- NFR-SCALE-1; NFR Document)*

**8\. Security Considerations**

*(Largely unchanged)* Authentication (NextAuth), Authorization (ownership checks in APIs), Input Validation (Zod), Secrets Management (AWS Secrets Manager \- Stage 2), Dependencies (Scanning via CI/CD), HTTPS, Rate Limiting (Stage 2+), SSRF Protection (Stage 2 Link-to-Card), Cloud Security (Security Groups, IAM \- Stage 2). Local data security relies on user environment and Docker setup.

*(Reference: PRD v3.6 Rev 1 Section 3 \- NFR-SEC-1)*

**9\. Deployment Strategy Overview**

* **Stage 1:** Local development environment using Docker Compose for PostgreSQL. Application run via npm run dev requiring user setup. No packaged distribution planned. Manual data migration via JSON export/import planned for Stage 2 transition.  
* **Stage 2:** Infrastructure on AWS managed via Terraform. CI/CD via GitHub Actions deploying containerized app to ECS/Fargate. Staging environment recommended. DB Migrations via Prisma Migrate in pipeline.

*(Reference: PRD v3.6 Rev 1 Section 6; Stakeholder Decisions)*

**10\. Open Technical Questions**

*(Revised based on decisions)*

* BlockNote vs. alternatives: Final confirmation/PoC for integration complexity.  
* Chakra UI vs. alternatives: Final confirmation if concerns arise.  
* File metadata schema: Finalize details for Stage 2 Media Blocks.  
* PostgreSQL FTS Indexing: Finalize specific strategy (generated column vs function index) for content field and confirm performance.  
* pgvector Indexing: Choose optimal index type (HNSW vs IVFFlat) and parameters based on data/query patterns (Stage 2).  
* AI Prompt Engineering: Detailed strategies needed for Stage 2+ features.  
* Network Graph Logic: Specific algorithm/weighting for relationships (Stage 2).  
* Serendipity Mode Logic: Algorithm details (Stage 2+).  
* Async Job Error Handling: Detailed retry/failure logic (Stage 2).  
* AI Service Abstraction: Finalize specific interface/methods based on MCP considerations and chosen AI features.  
* RAG Implementation Details (Stage 2+): Chunking, context window, prompt template, citations, streaming?  
* Visualization Library (Topic Cloud): Research and select library/approach (Stage 2).

## **Tech Lead Review & Assessment (TDD v1.1)**

This revised TDD (v1.1) aligns well with the updated PRD (v3.6 Rev 1\) and incorporates key technical decisions made recently.

**Key Updates:**

* Stage 1 scope now correctly includes Autosave, Move Folder, Bulk Ops, and JSON Export.  
* Vector storage strategy updated to pgvector on RDS PostgreSQL.  
* Folder deletion behavior clarified (orphan cards, prevent delete if sub-folders exist).  
* Data migration strategy clarified (manual via export/import).  
* Stage 1 execution method clarified (local setup required).  
* AI integration notes updated regarding MCP standard.  
* Open questions list refined.

**Remaining Areas for Clarification / Potential Issues:**

1. **FTS/pgvector Indexing Strategy:** While pgvector is chosen, the *specific* indexing strategy for both FTS on JSONB content and the vector embeddings needs detailed design and testing (likely during Stage 2 implementation) to ensure performance meets NFRs. This involves choosing index types (GIN, HNSW, IVFFlat) and potentially creating helper functions or generated columns.  
2. **API Schema Detail:** API contracts are still high-level. Formal OpenAPI specs would be beneficial for development and AI assistance.  
3. **Diagrams:** Placeholder exists; creating core architecture and data flow diagrams is important for shared understanding.  
4. **Component Design Detail:** Section 5 is conceptual; detailed prop definitions and internal logic will emerge during implementation.

**Questions for PM/Stakeholders:**

1. **"Create from Link" Retry Mechanism (FR-CARD-3):** *(Carry-over from PRD review)* For Stage 2 MVP, is the user-initiated retry (if initial AI fails) mandatory, or can it be added later? *(TL Recommendation: Include in MVP for better UX.)*  
2. **NFR Targets:** *(Carry-over from PRD review)* Please review the upcoming NFR document draft to confirm/adjust specific targets for Stage 2\.  
3. **Visualization Details (Stage 2):** *(Carry-over from PRD review)* When should we prioritize gathering detailed requirements and UX design for Topic Cloud and Network Graph features? *(TL Recommendation: Begin UX exploration soon.)*

**TL Recommendations & Alternatives:**

* **Technology Choices:** The current stack (Next.js, Postgres/pgvector, Prisma, Zustand, Chakra, BlockNote, AWS, Terraform) is a solid, modern foundation for this application.  
* **Infrastructure:** Starting with pgvector on RDS is pragmatic. Monitor performance and consider dedicated vector DBs only if significant scaling issues arise later.  
* **Development Process:** Recommend creating OpenAPI specs for APIs and core diagrams (Architecture, Data Flow) early in Stage 2 to improve clarity for both human developers and AI assistants.

**Draft Rating:**

* **Completion:** 4.5 / 5.0 (Covers the technical design based on the current PRD and decisions).  
* **Quality/Accuracy:** 4.5 / 5.0 (Accurately reflects latest decisions like pgvector/manual migration. Needs diagrams and more detailed API/indexing specs for full implementation readiness).

This revised TDD provides a clearer technical blueprint. Please review the remaining questions.

When you're ready, we can move on to generating the **Detailed Non-Functional Requirements (NFRs)** document.