Okay, excellent. Let's start drafting the **Architecture Decision Records (ADRs)**.

ADRs are lightweight documents used to capture important architectural decisions along with their context and consequences. This helps everyone understand *why* certain technical choices were made and provides valuable context as the project evolves. We typically create a new ADR for each significant decision.

Here are drafts for the key ADRs based on our discussions and the TDD.

**Document: Architecture Decision Records (ADRs)**

Date: 2025-04-21  
Status: Draft (Updated)  
**ADR-001: Choice of Web Framework**

* **Status:** Accepted  
* **Context:** We need a modern, robust framework for building the full-stack web application (frontend and backend API) with good developer experience, performance, and community support. The application requires server-side rendering (SSR) for initial load performance and SEO, client-side interactivity, and API route handling.  
* **Decision:** We will use **Next.js** with the **App Router**.  
* **Consequences:**  
  * **Pros:** Integrated full-stack development, excellent performance features, strong TypeScript support, large community, modern App Router patterns, good deployment integration.  
  * **Cons:** Potential learning curve, App Router relative newness, potential for increased build times on very large apps.  
* **Alternatives Considered:** Create React App \+ Express/NestJS, Remix, SvelteKit.

**ADR-002: Choice of Database and ORM**

* **Status:** Accepted  
* **Context:** The application requires a persistent relational database for core data and relationships. We need efficient and type-safe database interaction from Node.js, plus cloud scalability for Stage 2\.  
* **Decision:** We will use **PostgreSQL** as the relational database and **Prisma** as the ORM. Stage 2 will use a managed cloud instance (e.g., AWS RDS).  
* **Consequences:**  
  * **Pros:** Powerful RDBMS (PostgreSQL) with JSONB/extension support, excellent ORM (Prisma) DX and type safety, wide cloud availability.  
  * **Cons:** Requires local DB instance (Docker) for Stage 1, ORM abstraction layer, requires explicit migrations.  
* **Alternatives Considered:** MySQL, MongoDB, TypeORM/Sequelize.

**ADR-003: Choice of Vector Search Solution**

* **Status:** Accepted  
* **Context:** Stage 2 requires semantic search via vector embeddings. Need a scalable, cost-effective, and well-integrated solution.  
* **Decision:** We will use the **pgvector** extension within our primary **PostgreSQL** database. Embeddings generated externally (e.g., OpenAI API).  
* **Consequences:**  
  * **Pros:** Simplified infrastructure, cost-effective (vs dedicated DB), data consistency, Prisma support emerging.  
  * **Cons:** Potential performance limits at massive scale (vs dedicated DB), potential resource contention on primary DB server.  
* **Alternatives Considered:** Pinecone, Weaviate/Milvus/Qdrant, Elasticsearch.

**ADR-004: Choice of Content Storage Format for Knowledge Cards**

* **Status:** Accepted  
* **Context:** Need to store rich content from a block-based editor, supporting structure and queryability.  
* **Decision:** Store card content as **JSON (jsonb)** in PostgreSQL, defined by the chosen block editor's output.  
* **Consequences:**  
  * **Pros:** Flexibility, queryability (jsonb), standardization, compatibility with block editors.  
  * **Cons:** Parsing overhead, requires validation, potentially larger size than plain text/HTML.  
* **Alternatives Considered:** HTML String, Markdown String, XML.

**ADR-005: Strategy for Stage 1 to Stage 2 Data Migration**

* **Status:** Accepted  
* **Context:** Users might want to transfer data from the local Stage 1 prototype to the cloud-based Stage 2\.  
* **Decision:** **No automated migration tool.** Rely on **manual user export/import feature** and clear communication about Stage 1 being a prototype.  
* **Consequences:**  
  * **Pros:** Reduced development effort/complexity, focus on core features.  
  * **Cons:** User inconvenience, potential user dissatisfaction.  
* **Alternatives Considered:** Automated Migration Script, No Migration Path.

**ADR-006: Choice of UI Library**

* **Status:** Accepted  
* **Context:** Need a React component library for building the user interface efficiently and consistently within the Next.js framework. Key considerations include developer experience, component availability, customization, accessibility, and performance.  
* **Decision:** We will use **Chakra UI**.  
* **Consequences:**  
  * **Pros:**  
    * Excellent accessibility built-in.  
    * Highly composable components, promoting flexibility.  
    * Great developer experience with style props and clear documentation.  
    * Easy to customize theme and components.  
    * Good integration with React/Next.js ecosystem.  
  * **Cons:**  
    * May have fewer highly specialized, complex components out-of-the-box compared to Material UI (though composition helps build them).  
    * Team familiarity might be a factor if developers are primarily used to other libraries like Material UI or Bootstrap.  
* **Alternatives Considered:**  
  * **Material UI:** Very mature library with a vast component set, follows Material Design principles closely (can be a pro or con depending on design goals). Can sometimes be more complex to customize deeply.  
  * **Tailwind CSS (with Headless UI/Radix):** Utility-first approach offering maximum flexibility but requires building or composing components more manually. Less opinionated.  
  * **Ant Design:** Another comprehensive component library, popular especially in enterprise applications. Different design language.

**ADR-007: Choice of Background Job Queue System**

* **Status:** Accepted  
* **Context:** For Stage 2, the application requires a system to handle asynchronous background tasks reliably (e.g., processing batch file uploads, calling external AI APIs for enrichment, sending notifications). The system needs to integrate with our Node.js backend, use Redis for storage, and be deployable on AWS.  
* **Decision:** We will use **BullMQ**. It will utilize a managed **AWS ElastiCache for Redis** instance as its backend datastore in the Stage 2 cloud environment.  
* **Consequences:**  
  * **Pros:**  
    * Feature-rich: Provides job prioritization, delayed jobs, rate limiting, progress tracking, repeatable jobs, etc.  
    * Designed for Node.js: Excellent integration with the Node.js ecosystem and TypeScript.  
    * Redis-based: Leverages Redis, which we may already plan to use for caching (TDD reference). ElastiCache provides a managed Redis solution.  
    * Actively maintained successor to Bull.  
  * **Cons:**  
    * Requires managing a Redis instance (though ElastiCache simplifies this).  
    * Requires deploying and managing separate worker processes (e.g., in ECS tasks, EC2 instances) to process the jobs from the queue.  
    * Adds another moving part to the system architecture compared to purely synchronous operations.  
* **Alternatives Considered:**  
  * **AWS SQS \+ Lambda/ECS Workers:** Highly scalable, serverless (with Lambda) or container-based workers. Deep AWS integration. However, SQS itself offers fewer built-in queueing features (e.g., progress tracking, complex prioritization) compared to BullMQ; logic needs to be built into workers. Can involve more complex infrastructure setup (IAM roles, triggers, etc.).  
  * **Celery:** Very powerful and popular, but primarily Python-focused. Less idiomatic for a Node.js/TypeScript backend.  
  * **RabbitMQ (or other AMQP brokers):** Different messaging protocol (AMQP). Adds a message broker as another piece of infrastructure. Powerful but potentially overkill and different paradigm than Redis-based queues.

**Questions for PM/Stakeholders:**

* *(No outstanding questions at this time, assuming ADR review cadence is implicitly covered by the Git process below).*

**TL Recommendations & Alternatives:**

1. **UI Library:** Decision made: **Chakra UI**.  
2. **Background Job Queue:** Decision made: **BullMQ (with AWS ElastiCache for Redis)**.  
3. **ADR Process:** Confirmed. Use a simple Git-based process: store ADRs as markdown files (e.g., in /docs/adrs), review changes/additions via Pull Requests. This ensures versioning and collaborative review.

**Draft Rating:**

* **Completion:** 85% (Key decisions captured, including UI Lib and Job Queue. More ADRs may arise during detailed design/implementation).  
* **Quality/Accuracy:** High (Decisions align with TDD, PRD, and general best practices for this type of application).  
* **Collaboration Needed:** Review the newly added ADR-006 and ADR-007. Confirm agreement with the overall ADR set.