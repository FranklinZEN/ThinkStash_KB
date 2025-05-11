## **Non-Functional Requirements (NFRs) \- Knowledge Card System**

Version: 1.0 (Rev 1\)  
Date: 2025-04-21  
Status: Draft (Targets Updated)  
**1\. Introduction**

This document defines the Non-Functional Requirements (NFRs) for the Knowledge Card System. These specify criteria that judge the operation of the system, rather than specific behaviors (which are covered in the PRD). They cover aspects like performance, scalability, reliability, security, usability, maintainability, and accessibility. Meeting these NFRs is crucial for delivering a high-quality, production-ready application, particularly for Stage 2 (Cloud) and beyond. Targets specified below primarily apply to the Stage 2 cloud environment unless otherwise noted.

**2\. Performance**

| ID | Requirement | Measurement / Acceptance Criteria (Stage 2 Target) | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-PERF-1 | **API Response Time (Core CRUD)** | 95th percentile (p95) response time for core CRUD APIs (Cards, Folders, Tags \- excluding AI calls) **\< 500ms** under expected load (NFR-SCALE-1). | High | Ensures snappy UI for basic operations. Measured via APM/Load Testing. *(Initial target accepted)* |
| NFR-PERF-2 | **API Response Time (Search \- Keyword)** | p95 response time for keyword search (GET /api/search) **\< 1000ms** under expected load with representative data volume (NFR-SCALE-2). | High | Ensures search feels responsive. Target depends heavily on FTS tuning. *(Initial target accepted)* |
| NFR-PERF-3 | **API Response Time (Search \- Semantic)** | *(Stage 2+)* p95 response time for semantic search (GET /api/search/semantic) **\< 1500ms** under expected load and data volume (NFR-SCALE-3). | High | Semantic search is inherently slower; manage user expectations via UI feedback. *(Initial target accepted)* |
| NFR-PERF-4 | **API Response Time (AI Features)** | Synchronous AI APIs (e.g., Title Suggestion) p95 response time **\< 5 seconds**. Async AI jobs (Link-to-Card) completion time TBD based on complexity/cost. | Medium | Acknowledge external dependency latency. Focus on async patterns & feedback. *(Initial target accepted)* |
| NFR-PERF-5 | **Frontend Page Load Time (Core Pages)** | Largest Contentful Paint (LCP) for core pages (Dashboard, Card View) **\< 2.5 seconds** on target devices/networks. Interaction to Next Paint (INP) **\< 200ms**. | High | Standard web vitals for good UX. Requires FE optimization, CDN, code splitting. *(Initial target accepted)* |
| NFR-PERF-6 | **Block Editor Responsiveness** | Typing and basic block operations within the editor should feel instantaneous (**\< 100ms** visual feedback). | High | Core user interaction. Depends on BlockNote performance & integration. |
| NFR-PERF-7 | **Autosave Performance** | Autosave operations (PUT /api/cards/{cardId}) should not noticeably degrade frontend editor performance or backend stability under normal use. Measured via profiling. | Medium | Requires efficient endpoint and debouncing. Monitor backend load. |

**3\. Scalability**

| ID | Requirement | Measurement / Acceptance Criteria (Stage 2 Target) | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-SCALE-1 | **Concurrent Users** | System architecture (ECS/Fargate, RDS, ElastiCache) must support **100 concurrent users** while meeting performance NFRs. Architecture should allow scaling towards levels comparable to platforms like Medium.com with configuration changes & potential optimizations. | Medium | Defines initial target load based on PM input. Long-term ambition noted. Requires load testing to validate initial target. |
| NFR-SCALE-2 | **Data Volume (Relational)** | System must meet performance NFRs with up to **50,000 cards** per user and associated tags/folders. | Medium | Impacts database indexing, query optimization. Requires testing with realistic data volumes. |
| NFR-SCALE-3 | **Data Volume (Vector)** | *(Stage 2\)* Vector search (pgvector) performance must meet NFR-PERF-3 with up to **50,000 vectors** (embeddings) per user. | Medium | Impacts pgvector index choice (HNSW/IVFFlat) and potentially RDS instance size. Requires testing with vector volume. |
| NFR-SCALE-4 | **Horizontal Scaling (Application Tier)** | Application tier (ECS/Fargate service) must be configured for auto-scaling based on CPU/Memory utilization (e.g., scale out at 70% CPU, scale in at 30% CPU) to handle varying load automatically. | High | Ensures responsiveness under load without manual intervention. Requires aws\_appautoscaling\_target etc. in Terraform. |
| NFR-SCALE-5 | **Database Connections** | Application uses database connection pooling (handled by Prisma). RDS instance size and max\_connections parameter must support the expected number of connections from scaled application instances (target: \< 80% of max\_connections). | High | Prevents connection exhaustion. Monitor RDS DatabaseConnections metric. |
| NFR-SCALE-6 | **Asynchronous Task Processing** | Background job system (BullMQ/Redis) must process the expected volume of async tasks (e.g., \[TBD\] Link-to-Card jobs/hour) with average queue time \< \[TBD\] seconds. | Medium | Requires monitoring queue size/latency (e.g., via BullMQ monitoring tools or custom metrics). |

**4\. Reliability & Availability**

| ID | Requirement | Measurement / Acceptance Criteria (Stage 2 Target) | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-REL-1 | **System Availability** | Target **99.9% uptime** for core application services (measured via external monitoring, excluding scheduled maintenance, external AI provider downtime). | High | Standard availability target confirmed. Achieved via multi-AZ deployment, health checks. |
| NFR-REL-2 | **Data Durability (Cloud)** | Utilize standard AWS durability measures: RDS automated backups (daily) with **7-day retention**, point-in-time recovery enabled. S3 standard storage class. | High | Prevents data loss. Relies on correct AWS service configuration via Terraform. |
| NFR-REL-3 | **Error Handling (Backend)** | API error rate (5xx errors) should be **\< 0.1%** of requests under normal load. Expected errors (4xx) handled gracefully. Unhandled exceptions logged to Sentry & CloudWatch. | High | Indicates backend stability. Requires robust code-level error handling and monitoring. |
| NFR-REL-4 | **Error Handling (Frontend)** | Uncaught frontend exceptions should be minimal (\< \[TBD\]% of sessions). API errors handled gracefully with user feedback. Log frontend errors to Sentry. | High | Ensures good UX. Requires error boundaries, careful state management, Sentry integration. |
| NFR-REL-5 | **Error Handling (Async Jobs)** | Background jobs include **at least 3 retry attempts** with exponential backoff for transient failures. Persistent failures logged to dead-letter queue or CloudWatch Logs. Job failure rate \< \[TBD\]%. | High | Ensures async tasks complete or failures are investigated. Requires BullMQ configuration. |
| NFR-REL-6 | **Monitoring & Alerting** | Key system metrics (CPU, Memory, DB Connections, API Error Rates (4xx/5xx), Queue Length, Health Checks \- NFR-REL-1 targets) monitored (CloudWatch) with alerts configured for critical thresholds. | High | Enables proactive issue detection and response. Requires Terraform setup (KC-INFRA-DO-12). |
| NFR-REL-7 | **Deployment Reliability** | CI/CD pipeline includes automated tests (Unit **80%**, Integration **60%** coverage targets). Deployments use rolling updates with health checks. Successful deployment rate \> 99%. Manual rollback documented. | High | Minimizes deployment-related outages. Requires mature CI/CD pipeline and testing strategy. Test targets confirmed. |
| NFR-REL-8 | **AI Service Reliability Handling** | Application provides clear feedback (loading, error message) for AI service failures/timeouts. Includes retry mechanism where appropriate (e.g., Link-to-Card). Fallback logic defined (FR-CARD-3). | High | Critical for features depending on external APIs. Requires specific FE/BE implementation per feature. |

**5\. Security**

*(These are primarily practices and configurations to be implemented and verified)*

| ID | Requirement | Measurement / Acceptance Criteria | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-SEC-1 | **Authentication** | Implementation adheres to NextAuth.js security recommendations. Passwords hashed correctly (bcrypt). Session cookies configured securely (HttpOnly, SameSite=Lax, Secure). MFA enforced on AWS IAM. | High | Verified by code review, security scan. |
| NFR-SEC-2 | **Authorization** | All relevant API endpoints include and verify userId ownership checks against database records. Verified by code review, testing (including attempting cross-user access). | High | Verified by code review, specific test cases. |
| NFR-SEC-3 | **Input Validation** | All API endpoints validate inputs using Zod schemas. Validation covers type, format, length, presence. | High | Verified by code review, testing with invalid inputs. |
| NFR-SEC-4 | **Secrets Management** | No secrets in code/config files. Secrets stored in AWS Secrets Manager. Access granted via least-privilege IAM roles. | High | Verified by code review, Terraform plan review, checking runtime environment. |
| NFR-SEC-5 | **Dependency Management** | CI/CD pipeline includes dependency vulnerability scanning (npm audit \--audit-level=high or similar). Critical/High vulnerabilities addressed within **5 business days**. | High | Verified by CI/CD logs, vulnerability reports. Response timeframe confirmed. |
| NFR-SEC-6 | **Transport Security** | HTTPS enforced via ALB redirect. TLS v1.2+ used. | High | Verified by browser inspection, SSL Labs test. |
| NFR-SEC-7 | **Cloud Infrastructure Security** | Security Groups restrict traffic as defined (KC-INFRA-DO-13). IAM roles follow least privilege. S3 buckets block public access. Infrastructure scanned for misconfigurations (optional tool). | High | Verified by Terraform plan review, AWS console inspection, potential security scanning tools. |
| NFR-SEC-8 | **Rate Limiting** | *(Stage 2+)* Rate limiting implemented on key endpoints (e.g., Login, Register, AI calls) with defined thresholds (e.g., X requests/min/IP). | Medium | Requires implementation (e.g., using middleware, AWS WAF). Verified by testing. |
| NFR-SEC-9 | **Cross-Site Scripting (XSS) Prevention** | Code review confirms no unsanitized user input rendered via dangerouslySetInnerHTML. Framework defaults (React escaping) relied upon. Content Security Policy (CSP) header considered. | High | Verified by code review, potentially security scanning tools. |
| NFR-SEC-10 | **Server-Side Request Forgery (SSRF) Prevention** | *(Stage 2\)* Link-to-Card URL fetching includes validation (allow list, deny internal IPs) and potentially uses isolated environment/proxy. | High | Verified by code review, specific test cases for URL validation. |
| NFR-SEC-11 | **AI Security** | *(Stage 2+)* Input sanitization applied to prompts where feasible. Code review confirms no sensitive internal data leaked into external AI prompts. | Medium | Verified by code review, specific testing of AI features. |

**6\. Usability**

*(These are generally measured via user testing and heuristics)*

| ID | Requirement | Measurement / Acceptance Criteria | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-USE-1 | **Learnability** | Qualitative feedback from usability testing indicates new users can complete core Stage 1 tasks within 5 minutes. Onboarding (KC-UX-ONBOARD-FE-1) aids this process. | High | Ensures users can quickly become productive. |
| NFR-USE-2 | **Efficiency** | Task completion times for frequent actions (create card, search) measured during usability testing meet user expectations (qualitative feedback). Minimal clicks/steps. | High | Core value proposition. |
| NFR-USE-3 | **Consistency** | UI adheres to defined Style Guide / Chakra UI usage patterns. Terminology consistent with PRD. Verified via UX review, code review. | High | Reduces learning curve, improves predictability. |
| NFR-USE-4 | **Error Prevention & Recovery** | User errors during testing are infrequent for core tasks. Validation messages are clear. Confirmation required for destructive actions (Delete Folder/Card). Undo/Redo TBD. | High | Reduces user frustration. |
| NFR-USE-5 | **Feedback** | All actions requiring processing time (\>500ms) provide visual feedback (loading indicators). Success/error states clearly communicated (Toasts, Alerts). | High | Ensures users understand system status. |

**7\. Maintainability**

*(Assessed via code reviews, process adherence, and metrics)*

| ID | Requirement | Measurement / Acceptance Criteria | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-MAINT-1 | **Code Quality** | Code adheres to Coding Standards document. Linting/formatting pass in CI. Code review feedback addressed. Technical debt tracked and managed. | High | Ensures code is understandable, modifiable, less prone to bugs. |
| NFR-MAINT-2 | **Modularity & Coupling** | Adherence to defined module structure. Use of abstraction layers (AIService). Code reviews assess coupling/cohesion. | High | Facilitates parallel development, easier refactoring, and testing. |
| NFR-MAINT-3 | **Testability** | Unit test coverage target: **80%**. Integration test coverage target: **60%**. Tests run successfully in CI pipeline. Code structured for testability (DI, pure functions where possible). | High | Ensures changes can be made safely. Targets confirmed. Measured via coverage tools (e.g., Istanbul/nyc). |
| NFR-MAINT-4 | **Configuration Management** | All environment-specific config externalized (env vars, Secrets Manager). Verified by code review. | High | Allows easy changes between environments. |
| NFR-MAINT-5 | **Infrastructure as Code (IaC)** | *(Stage 2\)* All AWS infrastructure defined in Terraform. terraform plan shows no drift from manual changes. | High | Ensures infrastructure is repeatable, version-controlled. Verified by Terraform state, pipeline runs. |
| NFR-MAINT-6 | **Documentation** | Core documents (README, Schemas, ADRs, API Specs \- OpenAPI) are created and updated as major changes occur. | Medium | Aids onboarding and understanding. |

**8\. Accessibility**

| ID | Requirement | Measurement / Acceptance Criteria | Priority | Notes / Rationale |
| :---- | :---- | :---- | :---- | :---- |
| NFR-A11Y-1 | **WCAG Compliance** | Application aims to meet **WCAG 2.1 Level AA** guidelines. | Medium | Ensures usability for users with disabilities. Target confirmed. Requires conscious effort during design/development & specific testing resources. |
| NFR-A11Y-2 | **Keyboard Navigation** | All interactive elements (buttons, inputs, links, tree nodes, editor controls) must be navigable and operable using only the keyboard. Focus indicators must be clear. | High | Essential for users who cannot use a mouse. Verified by manual testing. |
| NFR-A11Y-3 | **Screen Reader Support** | Core content and interactive elements should be understandable and operable with common screen readers (e.g., NVDA, VoiceOver). Use semantic HTML and ARIA attributes where necessary. | Medium | Ensures usability for visually impaired users. Verified by testing with screen readers. Chakra UI provides good foundation but needs verification. |
| NFR-A11Y-4 | **Color Contrast** | Text and meaningful UI elements must meet WCAG AA contrast ratios (4.5:1 for normal text, 3:1 for large text/graphics). | High | Ensures readability for users with low vision. Verified using contrast checker tools. |

## **Tech Lead Review & Assessment (NFRs v1.0 \- Rev 1\)**

This revised NFR document incorporates the feedback on targets.

**Strengths:**

* Covers key quality attributes.  
* Defines measurable targets for Stage 2, now largely confirmed.  
* Provides a solid checklist for design and testing.  
* Includes rationale for requirements.

**Areas for Clarification / Requiring Input:**

* **TBD Targets:** Several targets remain TBD (e.g., async job volume/latency, specific FE error rate). These will need estimation or definition as we get closer to implementing those features.  
* **Stage 1 NFRs:** Formal measurement for Stage 1 remains out of scope, but the principles (responsiveness, reliability) should still guide local development.  
* **AI Performance/Reliability:** Targets remain estimates; real-world performance needs monitoring.

**Questions for PM/Stakeholders:**

1. **Performance Targets:** The initial targets were accepted ("looks good"). We will proceed with these as goals, understanding they may be refined based on testing and feedback. *(No action needed unless priorities change)*.  
2. **Async Job Volume/Latency (NFR-SCALE-6):** We will need to estimate the expected load for features like "Create from Link" closer to Stage 2 implementation to set concrete targets for queue processing time. *(Action: Defer target definition)*.  
3. **Frontend Error Rate (NFR-REL-4):** What is an acceptable percentage of user sessions experiencing uncaught frontend errors? (e.g., \< 0.5%, \< 1%). *(TL Recommendation: Aim for \< 0.5% but requires robust error boundary implementation and monitoring.)*  
4. **Async Job Failure Rate (NFR-REL-5):** What is an acceptable rate for persistent background job failures that require investigation? (e.g., \< 1%, \< 0.5%). *(TL Recommendation: Aim for \< 1% initially.)*

**TL Recommendations & Alternatives:**

* **Prioritization:** Continue focusing on Reliability and Security first.  
* **Measurability:** Plan for implementing monitoring tools (Sentry, CloudWatch APM/Metrics) early in Stage 2\.  
* **Testing:** Ensure test plans specifically cover NFR validation (performance, load, security, accessibility).  
* **Iterative NFRs:** Revisit performance and scalability targets post-Stage 2 launch based on real data.

**Draft Rating:**

* **Completion:** 4.5 / 5.0 (Covers all major NFR categories with mostly confirmed or noted TBD targets).  
* **Quality/Accuracy:** 4.5 / 5.0 (Targets are now largely confirmed or explicitly deferred. Provides a strong basis for quality assurance).

This gives us a much clearer picture of the quality requirements. Please consider the remaining questions about error/failure rates when convenient.

Shall we move on to the **Coding Standards & Design Patterns** document next?