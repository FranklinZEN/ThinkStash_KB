## Non-Functional Requirements (NFRs) \- Knowledge Card System

Version: 1.1 (Based on PRD v3.8 & TDD v1.2)  
Date: 2025-05-10  
Status: Draft (Updated for GCP, Core AI Focus)  
**1\. Introduction**

This document defines the Non-Functional Requirements (NFRs) for the Knowledge Card System. These specify criteria that judge the operation of the system, rather than specific behaviors (which are covered in PRD v3.8). They cover aspects like performance, scalability, reliability, security, usability, maintainability, and accessibility. Meeting these NFRs is crucial for delivering a high-quality, production-ready application, particularly for Stage 2 (GCP Cloud) and beyond. Targets specified below primarily apply to the Stage 2 GCP cloud environment, assuming successful completion of "Pre-Stage 2 Optimizations" outlined in TDD v1.2.

**2\. Performance**

| ID | Requirement | Measurement / Acceptance Criteria (Stage 2 Target on GCP) | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-PERF-1 | **API Response Time (Core CRUD)** | 95th percentile (p95) response time for core CRUD APIs (Cards, Folders, Tags \- excluding AI calls) **\< 500ms** under expected load (NFR-SCALE-1). | High | Ensures snappy UI for basic operations. Measured via GCP Cloud Monitoring (APM) / Load Testing. Assumes Stage 1 optimizations are effective. |
| NFR-PERF-2 | **API Response Time (Search \- Keyword)** | p95 response time for keyword search (GET /api/search) **\< 1000ms** under expected load with representative data volume (NFR-SCALE-2). | High | Ensures search feels responsive. Target depends heavily on PostgreSQL FTS tuning on Cloud SQL. |
| NFR-PERF-3 | **API Response Time (Search \- Semantic)** | *(Stage 2+)* p95 response time for semantic search (GET /api/search/semantic) **\< 1500ms** under expected load and data volume (NFR-SCALE-3). | High | Semantic search is inherently slower; manage user expectations via UI feedback. Depends on pgvector performance on Cloud SQL. |
| NFR-PERF-4 | **API Response Time (AI Features)** | Synchronous AI APIs (e.g., parts of AI Regeneration if not fully async) p95 response time **\< 5 seconds**. Async AI jobs (Create from Link, complex regenerations via CrewAI) completion time TBD based on complexity/cost. | Medium | Acknowledge external LLM dependency latency. Focus on async patterns (BullMQ) & clear UI feedback. |
| NFR-PERF-5 | **Frontend Page Load Time (Core Pages)** | Largest Contentful Paint (LCP) for core pages (Dashboard, Card View) **\< 2.5 seconds** on target devices/networks. Interaction to Next Paint (INP) **\< 200ms**. | High | Standard web vitals for good UX. Requires frontend optimization, GCP Cloud CDN, code splitting. Assumes Stage 1 optimizations are effective. |
| NFR-PERF-6 | **Block Editor Responsiveness** | Typing and basic block operations within the editor should feel instantaneous (**\< 100ms** visual feedback). | High | Core user interaction. Depends on BlockNote performance & integration. |
| NFR-PERF-7 | **Autosave Performance** | Autosave operations (PUT /api/cards/{cardId}) should not noticeably degrade frontend editor performance or backend stability under normal use. Measured via profiling. | Medium | Requires efficient endpoint and debouncing. Monitor backend load on GCP services. |

**3\. Scalability**

| ID | Requirement | Measurement / Acceptance Criteria (Stage 2 Target on GCP) | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-SCALE-1 | **Concurrent Users** | System architecture (GCP Cloud Run/GKE, Cloud SQL, Memorystore) must support **100 concurrent active users** while meeting performance NFRs. Architecture should allow scaling with GCP services. | Medium | Defines initial target load. Long-term ambition for more. Requires load testing on GCP to validate. |
| NFR-SCALE-2 | **Data Volume (Relational)** | System must meet performance NFRs with up to **50,000 cards** per user and associated tags/folders on Google Cloud SQL. | Medium | Impacts database indexing, query optimization (addressed in "Database Rethink"). Requires testing with realistic data volumes. |
| NFR-SCALE-3 | **Data Volume (Vector)** | *(Stage 2 Semantic Search Foundation)* pgvector on Cloud SQL performance must meet NFR-PERF-3 with up to **50,000 vectors** (embeddings) per user. | Medium | Impacts pgvector index choice (HNSW/IVFFlat) and potentially Cloud SQL instance size. Requires testing. |
| NFR-SCALE-4 | **Horizontal Scaling (Application Tier)** | Application tier (GCP Cloud Run services or GKE deployments for Next.js backend & Python/CrewAI services) must be configured for auto-scaling based on CPU/Memory/request count. | High | Ensures responsiveness under load without manual intervention. Requires appropriate GCP service configuration (e.g., Cloud Run min/max instances, GKE HPA). |
| NFR-SCALE-5 | **Database Connections** | Application uses database connection pooling (handled by Prisma). Cloud SQL instance size and max\_connections parameter must support connections from scaled app instances (target: \< 80% of max\_connections). | High | Prevents connection exhaustion. Monitor Cloud SQL DatabaseConnections metric. |
| NFR-SCALE-6 | **Asynchronous Task Processing** | Background job system (BullMQ/Memorystore on GCP) must process the expected volume of async AI tasks (e.g., \[TBD\] "Create from Link" jobs/hour) with average queue time \< \[TBD\] seconds. | Medium | Requires monitoring queue size/latency (e.g., via BullMQ monitoring tools or custom GCP metrics). |

**4\. Reliability & Availability**

| ID | Requirement | Measurement / Acceptance Criteria (Stage 2 Target on GCP) | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-REL-1 | **System Availability** | Target **99.9% uptime** for core application services on GCP (measured via Google Cloud Monitoring, excluding scheduled maintenance, external LLM provider downtime). | High | Standard availability target. Achieved via resilient GCP service configurations (e.g., multi-zone Cloud SQL, Cloud Run revisions), health checks. |
| NFR-REL-2 | **Data Durability (Cloud)** | Utilize standard GCP durability measures: Cloud SQL automated backups (daily) with **7-day retention**, point-in-time recovery enabled. Google Cloud Storage standard storage class durability. | High | Prevents data loss. Relies on correct GCP service configuration via Terraform. |
| NFR-REL-3 | **Error Handling (Backend)** | API error rate (5xx errors) should be **\< 0.1%** of requests under normal load. Expected errors (4xx) handled gracefully. Unhandled exceptions logged to Google Cloud Error Reporting/Logging. | High | Indicates backend stability. Requires robust code-level error handling and monitoring. |
| NFR-REL-4 | **Error Handling (Frontend)** | Uncaught frontend exceptions should be minimal (\< 0.5% of sessions). API errors handled gracefully with user feedback. Log frontend errors to Sentry or Google Cloud Error Reporting. | High | Ensures good UX. Requires error boundaries, careful state management. Target for uncaught exceptions confirmed. |
| NFR-REL-5 | **Error Handling (Async Jobs)** | Background jobs (BullMQ) include **at least 3 retry attempts** with exponential backoff for transient failures. Persistent failures logged to dead-letter mechanism or Google Cloud Logging. Job failure rate \< 1%. | High | Ensures async AI tasks complete or failures are investigated. Requires BullMQ configuration. Target for persistent failures confirmed. |
| NFR-REL-6 | **Monitoring & Alerting** | Key system metrics (CPU, Memory, DB Connections, API Error Rates, Queue Length, Health Checks) monitored (Google Cloud Monitoring) with alerts configured for critical thresholds. | High | Enables proactive issue detection and response. Requires Terraform setup for GCP monitoring resources. |
| NFR-REL-7 | **Deployment Reliability** | CI/CD pipeline (Google Cloud Build or GitHub Actions) includes automated tests (Unit **80%**, Integration **60%** coverage targets). Deployments use strategies like rolling updates with health checks. Successful deployment rate \> 99%. Manual rollback documented. | High | Minimizes deployment-related outages. Requires mature CI/CD pipeline and testing strategy. Test targets confirmed. |
| NFR-REL-8 | **AI Service Reliability Handling** | Application provides clear feedback (loading, error message) for AI service (CrewAI, LLM) failures/timeouts. Includes retry mechanism where appropriate (e.g., "Create from Link"). Fallback logic defined (PRD FR-CARD-3). | High | Critical for features depending on AI. Requires specific FE/BE implementation per feature. |

**5\. Security**

*(These are primarily practices and configurations to be implemented and verified on GCP)*

| ID | Requirement | Measurement / Acceptance Criteria | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-SEC-1 | **Authentication** | Implementation adheres to NextAuth.js security recommendations. Passwords hashed correctly (bcrypt). Session cookies configured securely (HttpOnly, SameSite=Lax, Secure). MFA enforced on GCP IAM admin accounts. | High | Verified by code review, security scan. |
| NFR-SEC-2 | **Authorization** | All relevant API endpoints include and verify userId ownership checks against database records. | High | Verified by code review, specific test cases (including attempting cross-user access). |
| NFR-SEC-3 | **Input Validation** | All API endpoints validate inputs using Zod schemas. Validation covers type, format, length, presence. | High | Verified by code review, testing with invalid inputs. |
| NFR-SEC-4 | **Secrets Management** | No secrets in code/config files. Secrets stored in **Google Secret Manager**. Access granted via least-privilege GCP IAM roles/service accounts. | High | Verified by code review, Terraform plan review, checking runtime environment. |
| NFR-SEC-5 | **Dependency Management** | CI/CD pipeline includes dependency vulnerability scanning (e.g., npm audit \--audit-level=high, Snyk, or GCP Artifact Analysis). Critical/High vulnerabilities addressed within **5 business days**. | High | Verified by CI/CD logs, vulnerability reports. Response timeframe confirmed. |
| NFR-SEC-6 | **Transport Security** | HTTPS enforced via Google Cloud Load Balancer redirect. TLS v1.2+ used. | High | Verified by browser inspection, SSL Labs test. |
| NFR-SEC-7 | **Cloud Infrastructure Security** | GCP Firewall Rules restrict traffic as defined. GCP IAM roles follow least privilege. Google Cloud Storage buckets block public access by default. Infrastructure scanned for misconfigurations (e.g., GCP Security Command Center). | High | Verified by Terraform plan review, GCP console inspection, potential security scanning tools. |
| NFR-SEC-8 | **Rate Limiting** | *(Stage 2+)* Rate limiting implemented on key endpoints (e.g., Login, Register, AI calls) with defined thresholds (e.g., X requests/min/IP) using Google Cloud Armor or API Gateway. | Medium | Requires implementation. Verified by testing. |
| NFR-SEC-9 | **Cross-Site Scripting (XSS) Prevention** | Code review confirms no unsanitized user input rendered via dangerouslySetInnerHTML. Framework defaults (React escaping) relied upon. Content Security Policy (CSP) header implemented. | High | Verified by code review, potentially security scanning tools. |
| NFR-SEC-10 | **Server-Side Request Forgery (SSRF) Prevention** | *(Stage 2\)* "Create from Link" URL fetching includes validation (allow list, deny internal GCP IPs) and potentially uses isolated environment/proxy if fetching from untrusted sources. | High | Verified by code review, specific test cases for URL validation. |
| NFR-SEC-11 | **AI Security** | *(Stage 2\)* Input sanitization applied to prompts for CrewAI/LLMs where feasible. Code review confirms no sensitive internal data unintentionally leaked into external AI prompts. Monitor for prompt injection attempts. | Medium | Verified by code review, specific testing of AI features. |

**6\. Usability**

*(These are generally measured via user testing, heuristic evaluation, and adherence to Figma designs for FR-UX-PROD-UI)*

| ID | Requirement | Measurement / Acceptance Criteria | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-USE-1 | **Learnability** | Qualitative feedback from usability testing (Stage 2\) indicates new users can complete core tasks (defined in PRD Stage 2\) efficiently. Onboarding (FR-UX-ONBOARD-1) aids this. | High | Ensures users can quickly become productive with the enhanced Stage 2 application. |
| NFR-USE-2 | **Efficiency** | Task completion times for frequent actions (create card, AI regeneration, search) measured during usability testing meet user expectations (qualitative feedback). Minimal clicks/steps. | High | Core value proposition. |
| NFR-USE-3 | **Consistency** | UI adheres to defined Figma designs and Chakra UI usage patterns. Terminology consistent with PRD. | High | Reduces learning curve, improves predictability. Enforced by FR-UX-PROD-UI. |
| NFR-USE-4 | **Error Prevention & Recovery** | User errors during testing are infrequent for core tasks. Validation messages are clear. Confirmation required for destructive actions (Delete Folder/Card). AI regeneration provides diff/preview with accept/cancel. | High | Reduces user frustration. |
| NFR-USE-5 | **Feedback** | All actions requiring processing time (\>500ms, especially AI operations) provide visual feedback (loading indicators, progress updates for async tasks). Success/error states clearly communicated (Toasts, Alerts). | High | Ensures users understand system status. |

**7\. Maintainability**

*(Assessed via code reviews, process adherence, and metrics)*

| ID | Requirement | Measurement / Acceptance Criteria | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-MAINT-1 | **Code Quality** | Code adheres to Coding Standards document. Linting/formatting pass in CI. Code review feedback addressed. Technical debt tracked and managed. | High | Ensures code is understandable, modifiable, less prone to bugs. |
| NFR-MAINT-2 | **Modularity & Coupling** | Adherence to defined module structure (Next.js, Python/CrewAI services). Use of abstraction layers (AIService). Code reviews assess coupling/cohesion. | High | Facilitates parallel development, easier refactoring, and testing. |
| NFR-MAINT-3 | **Testability** | Unit test coverage target: **80%**. Integration test coverage target: **60%**. Tests run successfully in CI/CD pipeline. Code structured for testability. | High | Ensures changes can be made safely. Targets confirmed. Measured via coverage tools. |
| NFR-MAINT-4 | **Configuration Management** | All environment-specific config externalized (env vars, Google Secret Manager). Verified by code review. | High | Allows easy changes between environments. |
| NFR-MAINT-5 | **Infrastructure as Code (IaC)** | *(Stage 2\)* All GCP infrastructure defined in Terraform. terraform plan shows no drift from manual changes. | High | Ensures infrastructure is repeatable, version-controlled. Verified by Terraform state, CI/CD pipeline runs. |
| NFR-MAINT-6 | **Documentation** | Core documents (README, Schemas from "Database Rethink", ADRs, API Specs \- OpenAPI) are created and updated as major changes occur. | Medium | Aids onboarding and understanding. |

**8\. Accessibility**

| ID | Requirement | Measurement / Acceptance Criteria | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-A11Y-1 | **WCAG Compliance** | Application aims to meet **WCAG 2.1 Level AA** guidelines. | Medium | Ensures usability for users with disabilities. Target confirmed. Requires conscious effort during Figma design & Chakra UI development & specific testing resources. |
| NFR-A11Y-2 | **Keyboard Navigation** | All interactive elements must be navigable and operable using only the keyboard. Focus indicators must be clear. | High | Essential for users who cannot use a mouse. Verified by manual testing. |
| NFR-A11Y-3 | **Screen Reader Support** | Core content and interactive elements should be understandable and operable with common screen readers (e.g., NVDA, VoiceOver). Use semantic HTML and ARIA attributes. | Medium | Ensures usability for visually impaired users. Verified by testing with screen readers. Chakra UI provides good foundation but needs verification. |
| NFR-A11Y-4 | **Color Contrast** | Text and meaningful UI elements must meet WCAG AA contrast ratios (4.5:1 for normal text, 3:1 for large text/graphics) as defined in Figma designs. | High | Ensures readability for users with low vision. Verified using contrast checker tools against Figma specs. |

## Tech Lead Review & Assessment (NFRs v1.1)

This NFR document (v1.1) has been updated to align with the project's shift to **Google Cloud Platform (GCP)** for Stage 2, the introduction of **CrewAI**, and the guidance from **PRD v3.8** and **TDD v1.2**.

**Key Updates:**

* All cloud-specific NFRs now reference GCP services and best practices.  
* Performance targets acknowledge the "Pre-Stage 2 Optimizations" and are set for the GCP environment.  
* Scalability NFRs reflect GCP services (Cloud Run/GKE, Cloud SQL, Memorystore).  
* Reliability targets for error rates (Frontend, Async Jobs) have been incorporated.  
* Security NFRs are now GCP-centric (Google Secret Manager, IAM, Firewall Rules, Security Command Center).  
* Usability NFRs emphasize adherence to Figma designs for the FR-UX-PROD-UI.  
* Maintainability NFRs include IaC for GCP.  
* Accessibility NFRs link color contrast to Figma designs.

**Areas for Clarification / Requiring Input (Ongoing):**

* **TBD Targets:** Some targets remain TBD (e.g., async job volume/latency NFR-SCALE-6). These will need estimation or definition as Stage 2 features are implemented.  
* **AI Performance/Reliability:** Targets for AI features (NFR-PERF-4) are initial estimates; real-world performance with CrewAI and chosen LLMs on GCP needs monitoring and potential refinement.  
* **Specific NFRs from "Database Rethink":** The "Database Rethink" activity (NFR-DB-RETHINK-1) might lead to more specific NFRs or refined targets for database performance and scalability.

**TL Recommendations:**

* **Prioritization:** Continue focusing on Performance (addressing Stage 1 issues first as per TDD 1.A), Reliability, and Security as foundational for Stage 2\.  
* **Measurability:** Plan for implementing monitoring tools (Google Cloud's operations suite, Sentry/Error Reporting) early in Stage 2 on GCP.  
* **Testing:** Ensure test plans specifically cover NFR validation (performance, load, security, accessibility) in the GCP environment.  
* **Iterative NFRs:** Revisit performance and scalability targets post-Stage 2 launch based on real data and user feedback.

**Draft Rating:**

* **Completion:** 4.7 / 5.0 (Covers all major NFR categories with targets largely updated for GCP or explicitly deferred/noted as TBD).  
* **Quality/Accuracy:** 4.7 / 5.0 (Targets and rationales are now aligned with the current GCP-focused project direction. Provides a strong basis for quality assurance for Stage 2).

This NFRs v1.1 document provides a clear set of quality attributes and targets for the upcoming Stage 2 development on GCP.