# **Thinkstash: Detailed Project Plan (Stage 2\) \- Comprehensive**

This document outlines the Epics and JIRA-style tickets for implementing the AI-powered features using CrewAI, deploying them as microservices on Google Cloud Run, integrating with the frontend, and setting up public accessibility. All epics listed below are part of Stage 2, which signifies the work done after the initial foundational GCP deployment and setup.

**PRD Reference:** Version 3.8, Stage 2 (GCP Production & Core AI Enhancements), with scope adjustments as per user feedback.

## **Stage 2 \- Epic 0: Foundational Infrastructure & Core Features**

Description: This epic covers critical infrastructure setup on GCP and core feature enhancements from the PRD that are prerequisites or complementary to the AI features, especially image handling. Tasks in this epic should be prioritized to run early in Stage 2, or in parallel with initial AI development.  
PRD References: Cloud Infrastructure & Deployment (GCP), Core Feature Enhancements (Media Blocks).

### **User Stories / Tasks for Stage 2 \- Epic 0:**

1. **TS-GCS-SETUP (Task): Setup Google Cloud Storage for Media**  
   * **Description:** Provision and configure a Google Cloud Storage (GCS) bucket specifically for storing media files (initially images, later potentially videos/code snippets). Set up appropriate IAM permissions for service account access (e.g., for backend services to upload and read) and consider basic lifecycle policies for managing object versions and storage classes.  
   * **Acceptance Criteria (AC):**  
     * A GCS bucket for media is created and configured in the designated GCP project.  
     * A dedicated service account with the principle of least privilege (e.g., roles/storage.objectCreator, roles/storage.objectViewer) is created and has programmatic access to the bucket.  
     * Bucket policies and IAM permissions are verified to prevent unintended public access by default.  
     * CORS configuration is applied to the bucket if direct client uploads or access is planned.  
     * Basic object lifecycle rules (e.g., for deleting old versions or moving to colder storage) are considered and documented, if not immediately implemented.  
2. **TS-REDIS-SETUP (Task): Setup Managed Redis (Google Cloud Memorystore)**  
   * **Description:** Provision and configure a Google Cloud Memorystore for Redis instance. Integrate with the backend application (Next.js and/or Python AI services) for potential uses like caching API responses, managing user sessions, or as a simple message broker for background tasks if full Pub/Sub is overkill initially. *User to confirm if this is essential for the initial AI features of Stage 2 or can be deferred. If deferred, this task moves to a later stage.*  
   * **Acceptance Criteria (AC):**  
     * If prioritized: A Redis instance (Cloud Memorystore for Redis) is provisioned with appropriate sizing and network configuration (e.g., within the same VPC as Cloud Run services).  
     * If prioritized: Backend application(s) can securely connect to and perform basic GET/SET operations with the Redis instance.  
     * If prioritized: Connection pooling and error handling for Redis connectivity are implemented in the backend.  
3. **TS-MEDIA-BLOCK-BE (Story): Implement Image Block Backend Support (GCS Integration)**  
   * **Description:** Develop backend API endpoints and logic within the Next.js application to handle image uploads from the client (e.g., manual upload via the block editor). This service will take an image file, validate it (type, size), upload it to the GCS bucket (configured in TS-GCS-SETUP), and return a persistent GCS URL for the stored image. This internal service will also be utilized by AI agents (TS-AI-4.5) when they process web-scraped images.  
   * **Acceptance Criteria (AC):**  
     * A secure API endpoint (e.g., /api/upload/image) in the Next.js backend accepts image file uploads (e.g., multipart/form-data).  
     * Input validation is performed on uploaded files (e.g., allowed MIME types, maximum file size).  
     * Images are securely uploaded to the designated GCS bucket with unique, non-guessable object names.  
     * A stable GCS URL (or an internal identifier that can be resolved to a GCS URL) for the uploaded image is returned in the API response.  
     * Appropriate error handling and responses for upload failures (e.g., file too large, invalid type, GCS upload error) are implemented.  
4. **TS-MEDIA-BLOCK-FE (Story): Implement Image Block in Frontend Editor**  
   * **Description:** Integrate or configure the BlockNote editor (or chosen block editor) to support a dedicated "Image Block." This block should allow users to:  
     * Trigger an image upload (which calls the TS-MEDIA-BLOCK-BE endpoint).  
     * Display an image within the editor and in the rendered card view, given its GCS URL.  
     * Optionally, allow users to provide alt text for the image.  
   * **Acceptance Criteria (AC):**  
     * Users can add a new "Image Block" to a knowledge card using the block editor's interface.  
     * The Image Block provides a UI element (e.g., button, drag-and-drop area) for users to select an image file for upload.  
     * Selecting a file triggers an API call to the backend image upload service (TS-MEDIA-BLOCK-BE).  
     * Upon successful upload, the image is rendered correctly within the editor using the returned GCS URL.  
     * The GCS URL (and optionally alt text) is stored as part of the Image Block's data in the knowledge card's JSON structure.  
     * Images are displayed correctly when viewing a saved knowledge card containing Image Blocks.

## **Stage 2 \- Epic 1: Core AI Feature Backend Implementation (CrewAI)**

Description: This epic covers the design, development, and local testing of all CrewAI agents and their orchestration for the core AI features. It assumes foundational elements like GCS for image storage and Image Block support (from Epic 0\) are being developed in parallel or are available. The focus is on AI-assisted creation of new cards from URLs (including text and images) and tag generation for all cards.  
PRD References: FR-CARD-3 (Create from Link), relevant parts of FR-CARD-4 (Tag Regeneration), TC-STACK-6, FR-SEARCH-2

### **User Stories / Tasks for Stage 2 \- Epic 1:**

*(Detailed Cursor AI prompts for these tasks are in a separate document: "Cursor AI Prompts for Stage 2 \- Epic 1 (with Image Handling)")*

1. **TS-AI-1 (Task): Setup CrewAI Development Environment**  
   * Description: Install CrewAI, Langchain, and necessary Python libraries. Establish a basic Python project structure for CrewAI development.  
   * **AC:** CrewAI installed, basic agent runs, project structure defined.  
2. **TS-AI-2 (Task): Research & Decision on Initial LLM Provider(s)**  
   * Description: Evaluate and select the initial LLM provider(s) for CrewAI. *This is an interactive process for you to decide.*  
   * **AC:** LLM provider(s) selected, integration path understood.  
3. **TS-AI-3 (Task): Setup Secure API Key Management for LLMs**  
   * Description: Implement secure storage and runtime access for LLM API keys (Google Secret Manager for cloud, .env for local).  
   * **AC:** API keys in Secret Manager (for cloud) / .env (local), Python app retrieves securely.  
4. **TS-AI-4 (Story): Design & Develop "Content Fetching Agent" for "Create from Link"** (Revised for Images)  
   * **Description:** Create a CrewAI agent with a tool to fetch readable text, image URLs, and alt text from a URL.  
   * **AC:** Agent accepts URL. Tool extracts text, image URLs, alt texts. Handles errors, paywall status. Returns status, original text, list of (image\_url, alt\_text) tuples, source URL, error message.  
5. **TS-AI-4.5 (Task): Develop Tool/Logic for Processing Extracted Images** (New/Refined)  
   * **Description:** Create a CrewAI tool/function that takes image URLs (from TS-AI-4), downloads them, and uses the internal GCS upload service (from TS-MEDIA-BLOCK-BE) to store them, returning GCS URLs.  
   * AC: Accepts list of (original\_image\_url, alt\_text). Downloads images. Uploads to GCS via internal service. Returns list of structured image data \[{gcs\_url: "...", original\_url: "...", alt\_text: "...", ai\_description: null}\]. Handles errors.  
6. **TS-AI-5 (Story): Design & Develop "Title Generation/Extraction Agent" for "Create from Link"**  
   * Description: Create a CrewAI agent that, given fetched web content, extracts or generates a title using an LLM.  
   * **AC:** Agent processes fetched text, outputs title.  
7. **TS-AI-6 (Story): Design & Develop "Summarization Agent" for "Create from Link"** (Revised for Images)  
   * **Description:** Create a CrewAI agent to generate a concise summary (block format JSON) from fetched text and potentially describe/reference key images using multi-modal LLM capabilities.  
   * **AC:** Agent processes text and list of processed image data (GCS URLs, alt text from TS-AI-4.5). Outputs block-format summary including text and image blocks (referencing GCS URLs). Original source URL preserved.  
8. **TS-AI-7 (Story): Design & Develop "Tag Suggestion Agent" for "Create from Link"**  
   * Description: Create a CrewAI agent to suggest relevant tags based on fetched text, title, summary, and image information.  
   * **AC:** Agent processes content/title/summary/image info, outputs tags.  
9. **TS-AI-8 (Story): Orchestrate "Create from Link" Crew** (Revised for Images)  
   * **Description:** Define a CrewAI "Crew" to orchestrate Content Fetching, Image Processing (TS-AI-4.5), Title Gen, Summarization, and Tagging.  
   * **AC:** Crew takes URL. Executes agents. Output: status, source URL, original text, AI title, AI summary (with text & image blocks referencing GCS URLs), AI-suggested tags, list of processed image data (GCS URLs, alt text, AI descriptions if generated). Handles paywall status & partial errors.  
10. **TS-AI-10 (Story): Design & Develop "Tag Regeneration Agent" for Existing Cards**  
    * Description: Create a CrewAI agent to regenerate card tags based on its existing title and content.  
    * **AC:** Agent accepts title/content, outputs new tags.  
11. **TS-AI-12 (Task): Define API Endpoints for AI Services** (Revised for Images)  
    * **Description:** Design FastAPI endpoints for AI services.  
    * **AC:** OpenAPI spec. "Create from Link" response includes: status, source URL, original text, AI title, AI summary (with text & image blocks referencing GCS URLs), AI tags, list of processed image data. "Regenerate Tags" endpoint as before.  
12. **TS-AI-13 (Task): Integrate AI Services with Database (Cloud SQL)**  
    * Description: Define data flow where AI service returns data to Next.js backend, which then writes to the database.  
    * AC: Clear data flow documented (AI service returns data to Next.js backend for DB write).  
13. **TS-AI-14 (Task): Setup Vector Embeddings for AI Content (pgvector)** (Revised for Images)  
    * **Description:** Implement logic to generate vector embeddings for text. Note future potential for image/multi-modal embeddings.  
    * **AC:** Text embedding model selected, process implemented, embeddings generated (for Next.js backend to store).

## **Stage 2 \- Epic 2: Frontend Integration for AI Features**

Description: This epic covers all frontend work required to interact with the AI services, display AI-generated content (including images), and provide user controls for AI features. Assumes Image Block support (from Epic 0\) is available in the editor.  
PRD References: FR-CARD-3, relevant parts of FR-CARD-4, FR-UX-PROD-UI

### **User Stories / Tasks for Stage 2 \- Epic 2:**

1. **TS-FE-1 (Story): Implement UI for "Create from Link"** (Revised for Images)  
   * **Description:** Develop frontend components for the "Create from Link" feature. This includes handling user input (URL), displaying loading states, processing API responses (including potential errors like paywalls or fetch failures), and rendering the AI-generated card content (text, title, tags, and images). The UI should also manage the logic for displaying original vs. AI-summarized text based on content length.  
   * Acceptance Criteria (AC):  
     * A dedicated UI section allows users to input a URL and initiate the "Create from Link" process.  
     * Appropriate loading indicators (e.g., spinners, progress messages) are displayed during API calls.  
     * If the API response indicates a content fetch failure (e.g., paywall, inaccessible URL), a user-friendly message is displayed, along with a clear call to action (e.g., "Try Manual Creation") that navigates the user to the manual card creation interface, pre-filling the URL if possible.  
     * If the API returns successfully fetched content:  
       * AI-generated title and tags are displayed.  
       * If original\_text word count exceeds a defined threshold (e.g., 2000 words), a message informs the user about the long article, and the UI primarily displays the AI-generated summary. Access to the full original\_text is provided (e.g., via an expandable section or a "View Original" link/modal).  
       * If original\_text is below the threshold, the UI offers a clear way for the user to view/choose between the original\_text and the AI-generated summary for the main card content (e.g., using tabs, a side-by-side preview, or a selection mechanism).  
       * Images (referenced by GCS URLs in the API response) are rendered within the previewed card content using the Image Block component (TS-MEDIA-BLOCK-FE).  
       * The source URL is always prominently displayed and saved with the card.  
     * User can confirm the creation of the new card, which then saves the selected/generated content.  
2. **TS-FE-2 (Story): Implement UI Button for AI-Enhanced Tag Generation**  
   * Description: Add an "AI" button or similar interactive element to the existing card editing/viewing interface that allows users to trigger AI-powered tag suggestions for that specific card.  
   * Acceptance Criteria (AC):  
     * An "AI Suggest Tags" button/icon is clearly visible and accessible within the card interface where tags are managed or displayed.  
     * Clicking the button triggers an API call to the "Regenerate Tags" backend endpoint (TS-AI-12), sending the current card's title and content.  
     * Loading indicators are displayed while the AI processes the request.  
     * Upon receiving suggestions, they are presented to the user (potentially using the Diff/Preview UI from TS-FE-3).  
3. **TS-FE-3 (Story): Develop Diff/Preview UI for AI Tag Suggestions (and optionally "Create from Link" content choice)**  
   * Description: Create a reusable UI component that can display a comparison between original data and AI-suggested data, allowing the user to accept or reject the suggestions. Initially for tags, but potentially adaptable for "Create from Link" content choices.  
   * Acceptance Criteria (AC):  
     * The UI component clearly differentiates between "Original Tags" and "AI Suggested Tags."  
     * Users can easily review the suggested changes.  
     * "Accept" button applies the AI-suggested tags to the card (updating the local state and triggering a save).  
     * "Cancel" or "Reject" button discards the AI suggestions, leaving the original tags intact.  
     * If adapted for "Create from Link" content (for shorter articles), it allows side-by-side preview of original fetched text vs. AI summary.  
     * The component is intuitive and provides a non-destructive way to review AI suggestions.  
4. **TS-FE-4 (Task): Connect Frontend to Backend AI Service APIs**  
   * Description: Implement the client-side API call logic within the Next.js/React application to communicate with the AI service endpoints defined in TS-AI-12. This includes handling request construction, sending requests, and processing responses (both successful and error states).  
   * Acceptance Criteria (AC):  
     * Frontend service/utility functions are created to make HTTP requests to /api/v1/cards/create-from-link and /api/v1/cards/regenerate-tags.  
     * Requests are constructed with the correct payloads (URL for create-from-link; title/content for regenerate-tags).  
     * Frontend correctly processes successful API responses, extracting data (including structured image data, original text, summaries, tags, status codes).  
     * Robust error handling is implemented for API call failures (network errors, server errors, specific application errors like paywall status), displaying appropriate messages to the user.  
     * Application state (e.g., using Zustand) is updated correctly based on API responses to reflect new card data or suggested tags.

## **Stage 2 \- Epic 3: Deployment & CI/CD for AI Microservices & Infrastructure (Cloud Run)**

Description: This epic covers containerizing the Python-based CrewAI services, deploying them to Google Cloud Run, establishing CI/CD pipelines for both frontend and AI backend, and managing infrastructure as code.  
PRD References: TC-STACK-2, TC-STACK-6, TC-STACK-7, NFR-DEPLOY-1, Infrastructure as Code.

### **User Stories / Tasks for Stage 2 \- Epic 3:**

1. **TS-DEP-1 (Task): Containerize CrewAI Python Application**  
   * Description: Create a Dockerfile for the Python-based CrewAI application (FastAPI service). This Dockerfile should define the environment, install dependencies, copy application code, and specify how to run the application (e.g., using Uvicorn).  
   * Acceptance Criteria (AC):  
     * A well-structured and efficient Dockerfile is created for the AI service.  
     * The Docker image builds successfully without errors.  
     * The container runs locally, exposing the FastAPI application on the configured port.  
     * The containerized application can access environment variables (e.g., for API keys, database connections if they were direct) passed to it.  
     * Multi-stage builds are considered for smaller production images if appropriate.  
2. **TS-DEP-2 (Task): Configure Cloud Run Service(s) for AI Microservices**  
   * Description: Provision and configure Google Cloud Run services to host the containerized AI application(s). This includes setting CPU/memory allocation, concurrency, scaling parameters, environment variables (including secrets from Secret Manager), and network settings (e.g., VPC connector if needed for Redis or internal DB access).  
   * Acceptance Criteria (AC):  
     * One or more Cloud Run services are created and configured in GCP for the AI backend.  
     * The Docker container image (pushed to Google Artifact Registry or Container Registry) is successfully deployed to the Cloud Run service(s).  
     * The service is accessible via its default Cloud Run URL (\*.run.app).  
     * Environment variables (including those mapped from Google Secret Manager for API keys) are correctly configured and accessible by the running service.  
     * Appropriate IAM permissions are set for the Cloud Run service's runtime service account (e.g., to access Secret Manager, GCS, Cloud SQL if needed).  
     * Autoscaling parameters (min/max instances, concurrency) are set to reasonable defaults.  
3. **TS-DEP-3 (Task): Setup CI/CD Pipeline for AI Microservices & Frontend**  
   * Description: Implement CI/CD pipelines (e.g., using Google Cloud Build or GitHub Actions) for both the AI microservices (Python/FastAPI) and the Next.js frontend. Pipelines should automate building, testing, and deploying new versions to Cloud Run.  
   * Acceptance Criteria (AC):  
     * A CI/CD pipeline is configured for the AI backend repository:  
       * Triggered on pushes/merges to specific branches (e.g., main, develop).  
       * Runs linters and unit tests.  
       * Builds the Docker image and pushes it to Google Artifact Registry.  
       * Deploys the new image to the AI Cloud Run service.  
     * A CI/CD pipeline is configured for the Next.js frontend repository:  
       * Triggered on pushes/merges to specific branches.  
       * Runs linters and unit/E2E tests.  
       * Builds the Next.js application.  
       * Deploys the build to the frontend Cloud Run service.  
     * Deployment processes include steps for different environments (e.g., staging, production) if defined.  
4. **TS-DEP-4 (Task): Implement Basic Monitoring & Logging for AI Services**  
   * Description: Ensure AI services output structured logs to Google Cloud Logging. Set up basic monitoring dashboards or alerts in Google Cloud Monitoring for service health (availability, error rates, latency) and resource utilization.  
   * Acceptance Criteria (AC):  
     * The Python FastAPI application uses structured logging (e.g., JSON format) that is automatically ingested by Cloud Logging.  
     * Logs include relevant information like timestamps, severity, request IDs, and key operational data.  
     * Key metrics for the AI Cloud Run service(s) (e.g., request count, error rate, 5xx responses, latency, instance count, CPU/memory utilization) are visible in Cloud Monitoring.  
     * Basic alert policies are configured in Cloud Monitoring for critical issues (e.g., high error rate, service unavailability).  
   * **PRD Reference:** TC-STACK-8  
5. **TS-DEP-5 (Task): Implement Infrastructure as Code (IaC)**  
   * **Description:** Define and manage core GCP resources (Cloud Run services for frontend and AI, Cloud SQL instance, GCS buckets, Cloud Memorystore for Redis if used, IAM policies, Secret Manager secrets, etc.) using an Infrastructure as Code tool like Terraform. Store IaC configurations in version control.  
   * Acceptance Criteria (AC):  
     * Terraform (or chosen IaC tool) configurations are created for all key GCP resources.  
     * The IaC code is stored in a version-controlled repository.  
     * The infrastructure can be provisioned, updated, and destroyed using IaC scripts/commands.  
     * The CI/CD pipeline for infrastructure changes (if applicable) can apply IaC configurations.  
     * Sensitive data (like initial passwords, if any are set via IaC) is handled securely (e.g., not hardcoded, using variable files not committed).

## **Stage 2 \- Epic 4: Public Accessibility & SSL for Thinkstash (Cloud Run \- Entire App)**

Description: This epic focuses on making the entire Thinkstash application (Next.js frontend) publicly accessible via a custom domain with Google-managed SSL, and ensuring secure communication paths.  
PRD References: Stage 2 (GCP Production), NFR-SEC-1

### **User Stories / Tasks for Stage 2 \- Epic 4:**

1. **TS-SSL-1 (Task): Acquire/Configure Custom Domain for Thinkstash**  
   * Description: If not already done, register a custom domain name (e.g., thinkstash.com, app.thinkstash.com) through a domain registrar. Gain access to its DNS management settings.  
   * Acceptance Criteria (AC):  
     * A custom domain name is successfully registered.  
     * Login credentials and access to the DNS management console for the domain are secured and available.  
2. **TS-SSL-2 (Task): Map Custom Domain to Cloud Run (Next.js Frontend Service)**  
   * Description: In the Google Cloud Console, map the custom domain to the Cloud Run service hosting the Next.js frontend application. This will involve Google providing DNS records (e.g., A, AAAA, CNAME) that need to be added to your domain registrar's DNS settings.  
   * Acceptance Criteria (AC):  
     * The custom domain is successfully added and verified within the Cloud Run service settings in GCP.  
     * The required DNS records provided by Google are correctly configured in the domain registrar's DNS zone for the custom domain.  
     * DNS propagation is initiated.  
3. **TS-SSL-3 (Task): Verify Google-Managed SSL Certificate Provisioning**  
   * Description: After DNS changes have propagated (can take minutes to hours), verify that Google Cloud Run has automatically provisioned and activated an SSL/TLS certificate for the custom domain. Test access to the application via https://yourcustomdomain.com.  
   * Acceptance Criteria (AC):  
     * The Thinkstash application is accessible via https://yourcustomdomain.com without SSL errors.  
     * The browser shows a valid SSL certificate issued by Google (or Let's Encrypt via Google).  
     * HTTP to HTTPS redirection is automatically handled by Cloud Run for the custom domain.  
4. **TS-SSL-4 (Task): Secure Communication between Frontend and AI Services**  
   * Description: Ensure that communication between the Next.js frontend (running on Cloud Run) and the Python AI microservices (also on Cloud Run) is secure and efficient. This involves deciding on the invocation pattern (e.g., frontend client calls Next.js backend, which then calls AI service; or Next.js backend calls AI service directly on behalf of client).  
   * Acceptance Criteria (AC):  
     * If AI services are invoked from the Next.js backend:  
       * Calls between the Next.js Cloud Run service and the AI Cloud Run service use their internal .run.app URLs (or service discovery if in the same project and region) and are authenticated (e.g., using IAM to ensure only the Next.js service can invoke the AI service).  
     * If AI services need to be exposed publicly (less ideal but possible), they are protected by Google Cloud Armor or an API Gateway with appropriate authentication (e.g., API keys, JWT). For Stage 2, assume internal invocation.  
     * All external user-facing traffic to the frontend is HTTPS. All backend-to-backend traffic within GCP is over secure channels.

## **Stage 2 \- Epic 6: Comprehensive Testing, Deployment Strategy & Operational Excellence**

Description: This epic focuses on establishing, implementing, and continuously improving a robust testing and deployment strategy. Note: Planning and definition tasks should be initiated early in Stage 2, concurrently with development. Execution is ongoing.  
PRD References: NFR-PERF-1, NFR-SCALE-1, NFR-REL-1, NFR-DEPLOY-1, TC-STACK-8

### **User Stories / Tasks for Stage 2 \- Epic 6:**

1. **TS-TEST-1 (Task): Review and Document Existing Testing Practices**  
   * Description: Analyze any current testing procedures or informal checks being performed. Document these as a baseline to identify strengths, weaknesses, and gaps compared to desired practices.  
   * AC: A concise document outlining the current testing state, tools used (if any), and identified gaps or areas for improvement.  
2. **TS-TEST-2 (Task): Define Comprehensive Testing Strategy & Standards**  
   * Description: Create a formal testing strategy document. This document should define the different types of testing to be performed (unit, integration, E2E, UAT, performance, security), tools to be used, responsibilities, environments, and entry/exit criteria for each testing phase. Include coding standards that promote testability (e.g., dependency injection, pure functions).  
   * AC: A comprehensive testing strategy document is created, reviewed by the team, and adopted as the standard.  
3. **TS-TEST-3 (Story): Develop/Enhance Unit Test Suites**  
   * Description: Write and maintain unit tests for critical functions, components, modules, and classes in both the frontend (React/Next.js components, utility functions, state management logic) and backend (Next.js API routes, Python/CrewAI agents, tools, API endpoint handlers). Aim for a reasonable target code coverage for critical paths.  
   * AC:  
     * Unit tests are implemented for key modules using appropriate frameworks (e.g., Jest/React Testing Library for frontend, PyTest for Python).  
     * Unit tests are integrated into the CI/CD pipeline (TS-DEP-3) and run automatically on every commit/PR.  
     * Builds fail if unit tests do not pass.  
     * Code coverage reports are generated and reviewed periodically.  
4. **TS-TEST-4 (Story): Develop/Enhance Integration Test Suites**  
   * Description: Implement integration tests to verify interactions between different parts of the system. Examples:  
     * Frontend component interactions.  
     * Frontend API calls to Next.js backend API routes.  
     * Next.js backend API route logic interacting with database or other internal services.  
     * Next.js backend calls to Python AI Microservices.  
     * AI Microservices interacting with external LLM APIs (may require mocking for cost/reliability in CI).  
   * AC:  
     * Integration tests are implemented for key user workflows and service interaction points.  
     * Tests verify data consistency and correct behavior across integrated components.  
     * Integration tests are included in the CI/CD pipeline, potentially running on a dedicated test/staging environment.  
5. **TS-TEST-5 (Task): Investigate and Plan for Shadow Mode/Canary Releases for AI Features**  
   * Description: Research techniques for safely testing new AI models, prompts, or agent logic in a production-like environment with real traffic but without impacting users directly. This includes shadow mode (new version runs in parallel, results logged/compared but not served) and canary releases (new version rolled out to a small subset of users). Plan how these could be implemented using Cloud Run's traffic splitting features or other mechanisms.  
   * AC:  
     * A feasibility study document outlining options for shadow mode and canary releases for AI features in the context of the Thinkstash architecture.  
     * A high-level implementation plan for the chosen approach(es), including necessary infrastructure, logging, and monitoring.  
6. **TS-TEST-6 (Task): Define Staging Environment Setup and Testing Procedures on GCP**  
   * Description: Plan and document the setup of a dedicated staging environment on GCP that mirrors the production environment as closely as possible in terms of service configurations, data (anonymized/subset), and network setup. Define procedures for deploying to staging and conducting thorough testing (including E2E and UAT) before production releases.  
   * AC:  
     * Staging environment architecture and provisioning plan (ideally managed via IaC from TS-DEP-5) documented.  
     * Procedures for deploying new versions to the staging environment are defined and integrated into CI/CD.  
     * A checklist for testing in the staging environment is created.  
7. **TS-TEST-7 (Task): Define Production Release Process & Checklist (CRQ \- Change Request Quality Process)**  
   * Description: Document a formal, step-by-step process for releasing new versions to the production environment. This should include pre-release checks (e.g., staging tests passed, UAT sign-off), a Change Request Quality (CRQ) process (approvals, risk assessment, rollback plan), deployment steps (leveraging CI/CD), and post-release monitoring activities.  
   * AC:  
     * A detailed production release process document, incorporating CRQ elements, is created and approved.  
     * A pre-flight checklist for production releases is established.  
     * Roles and responsibilities for the release process are defined.  
8. **TS-TEST-8 (Task): Develop and Document Fallback and Reversion Mechanisms**  
   * Description: For all Cloud Run services (Frontend & AI), establish and document clear, tested procedures for quickly rolling back to a previous stable version in case of a faulty deployment or critical issues discovered post-release. Leverage Cloud Run's revision management capabilities.  
   * AC:  
     * Step-by-step rollback procedures for each Cloud Run service are documented.  
     * Rollback procedures are tested periodically to ensure they work as expected.  
     * Criteria for triggering a rollback are defined.  
9. **TS-TEST-9 (Task): Develop and Document Data Migration and Rollback Strategies**  
   * Description: For any changes involving database schema modifications or significant data transformations, define a strategy for performing these migrations safely. This includes creating migration scripts, testing them thoroughly in staging, and, critically, developing a plan for how to roll back both the schema and data if a release associated with the migration fails.  
   * AC:  
     * A documented strategy for database migrations, including tools (e.g., Prisma Migrate, custom scripts), testing, and execution.  
     * A documented rollback plan for database changes associated with each significant migration.  
     * Backup and restore procedures for the Cloud SQL database are regularly tested.  
10. **TS-TEST-10 (Task): Establish Performance Testing and Monitoring for AI Features**  
    * Description: Define and implement performance tests specifically for the AI features to measure average and percentile latencies for API endpoints, resource consumption of AI agents, and throughput under load. Set up specific monitoring dashboards and alerts in Google Cloud Monitoring for AI service performance, LLM API call latencies, and error rates.  
    * AC:  
      * A performance test suite (e.g., using k6, Locust, or JMeter) is created for key AI API endpoints.  
      * Baseline performance metrics are established.  
      * Key AI performance metrics (e.g., P95 latency for /create-from-link, LLM token usage, error rates per agent) are monitored in Cloud Monitoring with appropriate alert policies.  
11. **TS-TEST-11 (Task): User Acceptance Testing (UAT) Process Definition**  
    * Description: Define a formal process for User Acceptance Testing (UAT). This includes how to select testers (e.g., your friends for initial small-batch testing, internal team members), how to prepare UAT test cases/scenarios, how to provide access to the UAT environment (staging), how to collect and track feedback, and the criteria for UAT sign-off before a feature is released to production.  
    * AC:  
      * A UAT process document is created, outlining steps, roles, and responsibilities.  
      * Templates for UAT test cases and feedback collection are available.  
      * The UAT process is implemented for new feature releases.

## **Stage 2 \- Epic 5: Advanced Interaction \- RAG Chat & Collaborative Card Creation (Future \- Stage 2+)**

Description: This epic outlines the future development of an in-house chat system powered by an LLM, leveraging RAG and web search, and allowing collaborative card creation. This is a significant feature set planned for after the core Stage 2 AI features are stabilized and released.  
PRD References: Future Vision Note, Stage 2+ (Chat with Knowledge Base, etc.)

### **User Stories / Tasks for Stage 2 \- Epic 5:**

1. **TS-CHAT-1 (Task): Design RAG Chat System Architecture**  
   * Description: Define the comprehensive architecture for the RAG-enabled chat system. This includes detailing the flow of user interaction, how CrewAI agents will collaborate (e.g., user query handler, RAG retriever, web searcher, response synthesizer, card creation coordinator), context management strategies (short-term memory for conversation, long-term via RAG), and how it integrates with existing knowledge card data and the pgvector store. Identify necessary GCP services and their configurations.  
   * AC:  
     * Detailed architectural diagram illustrating components, data flows, and service interactions.  
     * Design document specifying agent roles, tool requirements, prompt strategies for chat, context window management, and error handling.  
     * List of GCP services (e.g., Cloud Run for chat backend, Pub/Sub for async tasks, Memorystore for chat session state) with initial sizing/configuration considerations.  
2. **TS-CHAT-2 (Story): Develop RAG Retrieval Agent/Tool**  
   * Description: Create a specialized CrewAI agent (or a sophisticated tool used by an agent) responsible for querying the pgvector database. This agent will take a user's query or conversational context, transform it into an effective embedding, perform a similarity search against the knowledge card embeddings, and retrieve relevant text snippets or card summaries.  
   * AC:  
     * Agent/tool accepts natural language queries or conversational context.  
     * Successfully generates embeddings for input queries.  
     * Performs similarity searches against the pgvector store.  
     * Retrieves and formats relevant context (e.g., top N snippets, full card content if small enough) from knowledge cards.  
     * Handles cases where no relevant information is found.  
3. **TS-CHAT-3 (Story): Develop Web Search Agent/Tool for Chat**  
   * Description: Create or integrate a CrewAI agent/tool that can perform real-time web searches using a search API (e.g., Google Custom Search API, Bing Search API, or a third-party service like Serper API via Langchain). The agent should be able to take a query, fetch search results, and extract relevant information from the top results to augment the chat response or card creation process.  
   * AC:  
     * Agent/tool accepts search queries.  
     * Successfully calls a web search API and retrieves search results (links, snippets).  
     * Can (optionally) visit 1-2 top links to extract more detailed information.  
     * Returns a structured summary of relevant web search findings.  
4. **TS-CHAT-4 (Story): Develop Chat Interaction Management Agent(s)**  
   * Description: Design and implement the core CrewAI agent(s) that manage the overall chat conversation. This includes receiving user messages, maintaining conversational state/history (potentially using Redis via TS-REDIS-SETUP), interpreting user intent (e.g., asking a question, wanting to create a card, casual chat), delegating tasks to the RAG Retrieval Agent or Web Search Agent, and synthesizing their outputs to formulate a coherent and helpful response.  
   * AC:  
     * Agent(s) can receive and process user chat messages.  
     * Basic conversational state is maintained across turns.  
     * Intent recognition correctly routes requests to appropriate specialized agents.  
     * Agent(s) can synthesize information from multiple sources (RAG, web search, LLM's own knowledge) into a single response.  
5. **TS-CHAT-5 (Story): Design & Develop Collaborative Card Creation Flow via Chat**  
   * Description: Define and implement the interactive workflow where a user can collaboratively create a new knowledge card through the chat interface. This involves the AI prompting the user for information (e.g., topic, key points, sources), using its RAG and web search tools to gather and suggest content, allowing the user to edit/refine AI suggestions, and iteratively building the card content (title, summary, body, tags).  
   * AC:  
     * User can initiate a "create new card about X" flow via chat.  
     * AI agents guide the user through the card creation process, asking clarifying questions and offering suggestions.  
     * AI uses its tools to research and draft content sections for the card.  
     * User can provide feedback, edit AI-generated text, and approve final content within the chat interface.  
     * The system can assemble the collaboratively generated information into a structured format ready for saving as a knowledge card.  
6. **TS-CHAT-6 (Story): Develop Frontend UI for Chat Interface**  
   * Description: Design and implement the user interface for the chat system within the Thinkstash application. This includes a message input area, a display area for the conversation history (user messages and AI responses, including any rich content like links or card previews), and indicators for when the AI is "typing" or processing.  
   * AC:  
     * A functional and intuitive chat UI is integrated into the Thinkstash frontend.  
     * Users can type and send messages.  
     * Conversation history is displayed clearly, distinguishing between user and AI messages.  
     * Handles streaming responses from the AI if implemented for better UX.  
     * Basic error states (e.g., "AI is unavailable") are handled gracefully.  
7. **TS-CHAT-7 (Task): Integrate Chat with Knowledge Card System**  
   * Description: Implement the functionality to take the collaboratively generated and finalized content from the chat interface (TS-CHAT-5) and save it as a new knowledge card in the user's PostgreSQL database, including any generated embeddings.  
   * AC:  
     * A "Save as Card" or similar action is available within the chat interface once card content is finalized.  
     * New knowledge cards created via chat are correctly saved to the database with all relevant fields (title, content blocks, tags, source URLs if any, embeddings).  
     * The new card appears in the user's main knowledge card list/views.  
8. **TS-CHAT-8 (Task): Plan GCP Deployment for Chat Services**  
   * Description: Detail the deployment strategy for all backend components of the chat system on GCP. This includes selecting appropriate Cloud Run configurations (or other services like GKE if complexity demands), CI/CD pipeline updates, scaling considerations (especially for potentially long-running chat sessions or agent processes), monitoring for chat-specific metrics, and cost analysis.  
   * AC:  
     * A comprehensive deployment plan for all chat-related backend services on GCP is documented.  
     * Resource requirements and scaling strategies are defined.  
     * Monitoring and logging plans specific to the chat service are outlined.  
     * Estimated operational costs are projected.

## **Stage 2 \- Epic 7: Explorative Content Ingestion Methods (Future \- Stage 2+)**

Description: This epic covers the research, exploration, and potential development of alternative content ingestion methods like bookmarklets or a browser extension/web clipper to improve handling of paywalled or dynamic web content. This is planned for after the core Stage 2 features and potentially the initial chat/RAG features are implemented.  
PRD References: Stage 2+ (Future Enhancements)

### **User Stories / Tasks for Stage 2 \- Epic 7:**

1. **TS-INGEST-1 (Task): Research Bookmarklet Capabilities and Limitations**  
   * Description: Conduct a thorough investigation into the feasibility of using a browser bookmarklet for basic content extraction (e.g., selected text, page title, current URL) and sending this data to a Thinkstash endpoint. Document technical capabilities, limitations (e.g., cross-origin restrictions, Content Security Policy (CSP) challenges, complexity of DOM parsing via bookmarklet), browser compatibility, and overall user experience.  
   * AC:  
     * A research document is produced detailing bookmarklet technology, its pros and cons for Thinkstash's use case, and examples of successful/failed implementations.  
     * Specific technical hurdles and potential workarounds are identified.  
2. **TS-INGEST-2 (Task): Research Open-Source Web Clipper/Browser Extension Technologies**  
   * Description: Explore the landscape of existing open-source web clipper frameworks, libraries, or boilerplate projects that could be adapted or used as a foundation for a Thinkstash browser extension. Evaluate their features (e.g., article cleaning, selection tools, note-taking), maintenance status, community support, browser compatibility (Chrome, Firefox, Edge), and licensing.  
   * AC:  
     * A report summarizing findings on at least 2-3 promising open-source web clipper options or foundational technologies.  
     * Comparison of features, ease of customization, and potential fit for Thinkstash.  
3. **TS-INGEST-3 (Story): Develop Proof-of-Concept (PoC) for Selected Ingestion Method**  
   * Description: Based on the research from TS-INGEST-1 and TS-INGEST-2, select the most promising alternative ingestion method (either a bookmarklet or a basic web clipper using an open-source base). Develop a functional Proof-of-Concept to demonstrate core functionality: extracting selected text and the current page URL, and sending this data to a mock backend endpoint or logging it to the console.  
   * AC:  
     * A working PoC is developed for the chosen method.  
     * The PoC can successfully extract selected text and URL from at least 2-3 different websites.  
     * The PoC demonstrates how the extracted data would be packaged and sent.  
     * Key challenges encountered during PoC development are documented.  
4. **TS-INGEST-4 (Task): Design Integration with AI Backend for Clipped/Captured Content**  
   * Description: Define how content captured via a bookmarklet or web clipper (from the PoC in TS-INGEST-3) would be processed by the existing AI agents in "Stage 2 \- Epic 1" (Title Agent, Summarization Agent, Tagging Agent). This involves designing a new API endpoint in the AI service to accept this pre-fetched/selected content directly, rather than a URL.  
   * AC:  
     * API endpoint specification (request/response schema) for submitting captured content to the AI backend.  
     * Data flow diagram showing how captured content moves from the clipper/bookmarklet to the AI agents.  
     * Modifications needed for existing AI agents/crews to handle direct content input are identified.  
5. **TS-INGEST-5 (Task): Plan Development and Maintenance for Browser Extension (If Pursued)**  
   * Description: If a full browser extension is deemed the most viable and necessary path forward based on the PoC and research, create a detailed development plan. This plan should include a feature list for V1 of the extension, UI/UX mockups or wireframes, target browsers, development milestones, testing strategies (including cross-browser testing), process for publishing to extension stores (Chrome Web Store, Firefox Add-ons, etc.), and considerations for ongoing maintenance and updates.  
   * AC:  
     * A comprehensive development and maintenance plan document for a Thinkstash browser extension.  
     * Resource and time estimates for V1 development.  
     * Key risks and mitigation strategies identified.