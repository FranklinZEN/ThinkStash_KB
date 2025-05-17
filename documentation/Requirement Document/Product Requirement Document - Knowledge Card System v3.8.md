# Product Requirement Document (PRD)

Product: Web-Based Knowledge Card System  
Version: 3.8 (Reflecting GCP shift, Core AI focus with CrewAI, and revised staging)  
Date: 2025-05-10  
Status: Draft

## 1\. Introduction

### 1.1 Overview

This document outlines the requirements for the Web-Based Knowledge Card System, a platform designed to help knowledge workers, professionals, researchers, and educators capture, organize, discover, synthesize, and utilize information effectively. Users can create rich, multimedia "knowledge cards," organize them into hierarchical folders, retrieve information through powerful search, visualize connections, interact conversationally, and actively generate new ideas from their knowledge base using AI.

* **Stage 1 (Completed):** Focused on a local/offline-capable MVP for core capture and organization.  
* **Stage 2 (Current Focus):** Transitions to a production-ready application on Google Cloud Platform (GCP), introduces core AI-driven content creation and enhancement features using CrewAI, implements a manual hashtagging system, overhauls the UI/UX for production, and includes a database rethink for scalability.  
* **Stage 2+ (Future):** Builds further with advanced search, interaction features like RAG chat, basic dashboard statistics, and more sophisticated AI capabilities.

### 1.2 Goals & Business Objectives

* Increase User Productivity: Enable users to quickly capture, create, and retrieve information.  
* Facilitate Knowledge Organization: Provide intuitive tools (folders, manual tags including hashtags) for structuring personal knowledge bases.  
* Enhance Content Creation & Understanding: Offer a flexible block-based editing experience and leverage AI (CrewAI) to assist in content generation, summarization, and metadata creation.  
* Streamline Information Capture: Allow seamless creation of summarized and tagged knowledge cards directly from web links using AI (CrewAI), with robust fallbacks.  
* Enable Future Knowledge Synthesis & Idea Generation: Lay the groundwork in Stage 2 for features that help users discover connections, review themes, and generate new insights (planned for Stage 2+).  
* Provide AI-driven Assistance: Leverage AI (CrewAI) to assist with content creation (titles, summaries from links, content regeneration/on-demand summarization), organization (AI tags from links, tag regeneration).  
* Ensure Security & Reliability: Build user trust through secure authentication and reliable data storage on GCP.

### 1.3 Target Audience

* Knowledge Workers  
* Business Professionals  
* Researchers & Academics  
* Students & Educators  
* Anyone needing to organize notes, research, or ideas digitally, and wanting tools to help synthesize, visualize, and build upon that knowledge to foster creativity.

### 1.4 Scope

**In Scope (Core Functionality):**

* **Stage 1 (Local MVP \- Completed):**  
  * Secure User Authentication (Local Email/Password only).  
  * User Profile Management (Basic Name).  
  * Knowledge Card Creation using a Block-Based Editor (core text blocks).  
  * Manual Tagging of Knowledge Cards.  
  * Folder Management (Hierarchy, including deletion policy).  
  * Assigning Cards to Folders.  
  * Basic Keyword Search (local data \- PostgreSQL FTS).  
  * Responsive Web Interface (for local execution).  
  * Ability to run locally. Data stored locally (PostgreSQL).  
  * JSON Data Export.  
  * Basic User Onboarding/Help.  
  * Graceful Session Expiry Handling.  
* **Stage 2 (GCP Production & Core AI Enhancements \- Current Focus):**  
  * **Cloud Infrastructure & Deployment (GCP):**  
    * Deployment to Google Cloud Platform (GCP).  
    * Managed PostgreSQL (Google Cloud SQL) with pgvector extension.  
    * Managed Redis (Google Cloud Memorystore).  
    * Object Storage (Google Cloud Storage) for media.  
    * Backend services on scalable GCP compute (e.g., Cloud Run, GKE).  
    * CI/CD pipeline for GCP.  
    * Monitoring, Logging on GCP.  
    * Infrastructure as Code (e.g., Terraform).  
  * **Core Feature Enhancements:**  
    * **Manual Hashtag System (\#tag):** Users can add and manage hashtags within cards for organization and retrieval.  
    * **Production UI/UX Overhaul:** Significant improvements to the overall user interface and experience for a production-grade application.  
    * Social Login (e.g., Google, GitHub).  
    * Media Blocks (Image, Video, Code) in editor, with cloud storage.  
  * **AI-Powered Features (with CrewAI):**  
    * **AI-Powered "Create from Link" (CrewAI):** Paste URL to generate card with AI-extracted/generated title, AI-generated concise summary (block format), and AI-suggested tags. Includes secure content fetching and robust fallback behavior.  
    * **AI-Enhanced Card Generation & On-Demand Summarization (CrewAI):**  
      * AI button to regenerate Card Title based on content.  
      * AI button to regenerate Card Tags based on title and content.  
      * AI button to regenerate/summarize Card Content (acting as on-demand summarization for any card).  
      * Regenerated content presented in a diff/preview UI with accept/cancel options.  
  * **Foundation for Future Growth:**  
    * **Database Rethink & Optimization:** Activity to analyze and refine database schema and performance for scalability on GCP.  
    * Semantic Search Foundation: Backend setup for vector embedding generation and storage in pgvector.  
    * Manual JSON data import (for Stage 1 to Stage 2 data transfer).  
* **Stage 2+ (Advanced Interaction & Features \- Future):**  
  * Semantic Search Querying UI & Advanced Filtering.  
  * Chat with Knowledge Base (RAG).  
  * **Basic Dashboard Stats:** Display basic counts (Cards, Tags, Folders). Optional: Recent cards list.  
  * Knowledge Visualization: Topic Clouds, Network Graphs.  
  * AI Collection Summaries on Folder/Tag On-demand.  
  * AI "Spark" Prompts.  
  * Semantic Similarity Surfacing (Related Cards).  
  * Tag Intersection Explorer.  
  * Concept Juxtaposition Tool.  
  * Serendipity Mode.  
  * Advanced User Settings (Password Reset, Account Deletion).

**Out of Scope (Potential Future Enhancements):**

* Real-time Collaboration / Multi-user Editing.  
* Advanced Sharing and Permissions Models.  
* True Offline Functionality (beyond Stage 1's local execution).  
* Public publishing of cards/folders.  
* Mobile Native Applications.  
* Integration with third-party services (beyond auth and link fetching).  
* Highly advanced, customizable reporting beyond defined visualizations.  
* Automated Theme Detection (NLP Topic Modeling).

## 2\. Functional Requirements

### 2.1 User Authentication & Security (Epic: KC-AUTH)

* FR-AUTH-1: (Stage 1\) Local Email/Password Registration.  
* FR-AUTH-2: (Stage 1\) Local Email/Password Login.  
* **FR-AUTH-3:** (Stage 2\) Social Login (e.g., Google, GitHub) integrated with GCP.  
* FR-AUTH-4: (Stage 1\) Secure Password Hashing (bcrypt). Passwords must meet complexity requirements: Minimum 8 characters, including at least one uppercase letter, one lowercase letter, one number, and one special character.  
* FR-AUTH-5: (Stage 1\) Secure Session Management (JWT via NextAuth.js).  
* FR-AUTH-6: (Stage 1\) Basic Profile View/Update (Name).  
* FR-AUTH-7: (Stage 2+) Password Reset via Email.  
* FR-AUTH-8: (Stage 2+) Account Management (Linked Accounts, Delete Account).  
* FR-AUTH-9: (Stage 1+) HTTPS & Basic Web Security. (Stage 2: Enhanced cloud security on GCP).  
* FR-AUTH-10: (Stage 1\) Graceful Session Expiry Handling.

### 2.2 Knowledge Card Creation & AI Enhancement (Epic: KC-CARD-CREATE, KC-AI)

* **FR-CARD-1:** Block-Based Editor:  
  * (Stage 1\) Users must create and edit card content using a block-based editor interface.  
  * (Stage 1\) The editor must support core text block types: Paragraph, Headings (H1, H2, H3), Unordered Lists, Ordered Lists (with basic formatting: Bold, Italic).  
  * **(Stage 2\)** The editor must support media blocks: Image Blocks (upload/URL), Video Embed Blocks, Code Blocks, with storage on Google Cloud Storage.  
  * (Stage 1\) Users must be able to easily add, delete, and reorder blocks.  
  * (Stage 1\) Content must be saved as structured JSON data. (Stage 2: Stored in Google Cloud SQL).  
* **FR-CARD-2:** Card Metadata \- Manual Tagging & Hashtags:  
  * (Stage 1\) Users can manually add descriptive tags to cards.  
  * **(Stage 2\) Users can manually add hashtags (e.g., \#projectX, \#idea) within a dedicated tagging interface or directly in text recognized by the system. Hashtags are stored and searchable.**  
* **FR-CARD-3:** AI-Powered "Create from Link" (CrewAI):  
  * (Stage 2\) Users must be able to paste a URL into a designated input field.  
  * (Stage 2\) System, using CrewAI agents, fetches content securely from the URL.  
  * (Stage 2\) System (CrewAI) extracts Title if available, or generates a title if missing.  
  * (Stage 2\) System (CrewAI) generates a concise summary of the content (in block format).  
  * (Stage 2\) System (CrewAI) suggests relevant tags based on the content.  
  * (Stage 2\) A new card is created in the cloud DB (Google Cloud SQL) with the title, AI summary, AI tags, and source URL.  
  * (Stage 2\) Fallback Behavior: If AI processing fails, the system creates a card with the extracted Title, source URL, and main body text (if available via Readability.js or similar, stored in block format). UI indicates partial success/failure with retry option.  
  * (Stage 2\) Optional: Store extracted main body text alongside AI summary even on success.  
  * (Stage 2\) Provide asynchronous feedback and handle errors gracefully.  
* **FR-CARD-4:** AI-Enhanced Card Generation & On-Demand Summarization (CrewAI):  
  * **(Stage 2\) For existing cards (manually created or from link), users can trigger AI-powered regeneration or on-demand summarization for specific fields:**  
    * **Title Regeneration:** An "AI" button next to the title field, when clicked, uses CrewAI agents to read the card's content and suggest one or more new titles.  
    * **Tags Regeneration:** An "AI" button associated with tags uses CrewAI agents to read the card's title and content and suggest a new set of relevant tags (including hashtags).  
    * **Content Regeneration/Summarization (On-Demand Summarization):** An "AI" button associated with the card content uses CrewAI agents to read the existing content and generate a revised summary or rephrased version, aiming to preserve key information while potentially improving conciseness or clarity. This serves as the "AI On-Demand Summarization" for any card.  
  * **(Stage 2\) Diff/Preview UI:** Regenerated content (title, tags, or main content) is presented to the user in a preview or "diff" interface, allowing them to compare the original and AI-suggested versions.  
  * **(Stage 2\) User Confirmation:** Users must be able to "Accept" the AI-generated changes (which then updates the card) or "Cancel" to keep the original content.  
* \~\~FR-CARD-5: (Stage 2+) AI On-Demand Summarization (General purpose, if not covered by FR-CARD-4).\~\~ *(Effectively covered by FR-CARD-4 in Stage 2\)*

### 2.3 Organization (Folders & Tags) (Epic: KC-ORG)

* FR-ORG-1: (Stage 1\) Create Folders.  
* FR-ORG-2: (Stage 1\) Rename Folders.  
* FR-ORG-3: (Stage 1\) Delete Folders (Prevent deletion if non-empty, confirm for empty).  
* FR-ORG-4: (Stage 1\) Folder Hierarchy.  
* FR-ORG-5: (Stage 1\) Assign Card to Folder.  
* FR-ORG-6: (Stage 1\) Move Card between Folders.  
* FR-ORG-7: (Stage 1\) View Folder Structure.  
* FR-ORG-8: (Stage 1\) View Cards within Folder.  
* **FR-ORG-9:** (Stage 1 for manual tags, Stage 2 for hashtags) View Cards associated with Tag/Hashtag (Filtering card list).

### 2.4 Search & Discovery (Epic: KC-SEARCH)

* FR-SEARCH-1: (Stage 1\) Keyword Search: Search Title & Block Text content using PostgreSQL Full-Text Search.  
* **FR-SEARCH-2:** (Stage 2\) Semantic Search Foundation: Implement vector embedding generation for card content (and potentially AI-generated summaries) and store them in pgvector on Google Cloud SQL.  
* FR-SEARCH-3: (Stage 2+) Semantic Search Querying UI: Implement user interface for semantic search queries.  
* FR-SEARCH-4: (Stage 2+) Filtering: Filter search results (keyword and semantic).  
* FR-SEARCH-5: (Stage 2+) Semantic Similarity Surfacing (Related Cards).

### 2.5 Knowledge Insights & Interaction (Epic: KC-INSIGHTS)

* **FR-INSIGHT-1:** (Stage 2+) Basic Dashboard Stats: Display basic counts (Cards, Tags, Folders). Optional: Recent cards list.  
* FR-INSIGHT-2: (Stage 2+) Knowledge Visualization \- Topic Cloud.  
* FR-INSIGHT-3: (Stage 2+) Knowledge Visualization \- Network Graph.  
* FR-INSIGHT-4: (Stage 2+) AI Collection Summaries.  
* FR-INSIGHT-5: (Stage 2+) Tag Intersection Explorer.  
* **FR-INSIGHT-6:** (Stage 2+) Chat with Knowledge Base (RAG): Ask questions \-\> System finds relevant cards via semantic search (leveraging FR-SEARCH-2 & 3\) \-\> LLM generates answer based on card context \-\> Display response with citations.  
* FR-INSIGHT-7: (Stage 2+) AI "Spark" Prompts.  
* FR-INSIGHT-8: (Stage 2+) Concept Juxtaposition Tool.  
* FR-INSIGHT-9: (Stage 2+) Serendipity Mode.

### 2.6 AI Enhancements (Consolidated under KC-CARD-CREATE & other specific FRs)

\*(This section can be kept for high-level tracking or merged into specific feature requirements like FR-CARD-3, FR-CARD-4, etc. For this revision, specific AI features are detailed above.)\*

### 2.7 Data Management (Epic: KC-DATA)

* FR-DATA-1: (Stage 1\) Data Export (JSON).  
* **FR-DATA-2:** (Stage 2\) Manual Data Import (JSON) to facilitate migration from Stage 1 to Stage 2 (GCP).

### 2.8 User Experience (Epic: KC-UX / KC-ONBOARDING)

* FR-UX-ONBOARD-1: (Stage 1\) Basic Onboarding.  
* **FR-UX-PROD-UI:** (Stage 2\) Production UI/UX Overhaul: The application will undergo a significant UI/UX review and enhancement process to ensure a polished, intuitive, and professional experience suitable for a production product. This includes consistent design language, improved workflows, and enhanced visual appeal.

## 3\. Non-Functional Requirements

* NFR-PERF-1: Responsiveness: UI interactions responsive. (Stage 2: Async handling for AI ops, optimized for GCP).  
* NFR-SCALE-1: Scalability: (Stage 2\) Cloud architecture on GCP must scale to support a growing number of users and data. (Specific targets TBD during "Database Rethink").  
* NFR-SEC-1: Security: Standard web security, HTTPS, secure auth. (Stage 2: Leverage GCP security best practices, Secret Manager, IAM).  
* NFR-USE-1: Usability: Intuitive interface, efficient workflows. (Stage 2: Enhanced by FR-UX-PROD-UI).  
* NFR-A11Y-1: Accessibility: Adhere to WCAG AA guidelines.  
* NFR-MAINT-1: Maintainability: Well-structured, commented, tested code. (Stage 2: IaC for GCP, schema documentation as part of "Database Rethink").  
* NFR-REL-1: Reliability: Proper error handling. (Stage 2: Monitoring & backups on GCP).  
* NFR-DEPLOY-1: (Stage 2\) Automated Deployments to GCP via CI/CD.  
* **NFR-DB-RETHINK-1:** (Stage 2\) Database Review: A formal review ("Database Rethink") of the database schema, indexing, and query patterns will be conducted to ensure performance and scalability on GCP, especially considering AI features and RAG.

## 4\. Design Considerations

* DC-UI-1: Clean, modern, intuitive UI (Chakra UI). (Stage 2: Subject to FR-UX-PROD-UI).  
* DC-UX-1: User flows designed for efficiency. (Stage 2: Special attention to AI interaction flows, diff/preview UI, hashtagging).  
* DC-RESP-1: Fully responsive application.  
* DC-DIAG-1: Maintain high-level architecture diagrams (reflecting GCP services and CrewAI integration).

## 5\. Technical Considerations

* TC-STACK-1: Frontend: React/Next.js/TS. Zustand. Block Editor Lib (BlockNote). UI Lib (Chakra UI).  
* TC-STACK-2: Backend: Node.js via Next.js API routes (running on GCP compute like Cloud Run/GKE).  
* **TC-STACK-3:** Database: **Google Cloud SQL for PostgreSQL** (jsonb support). Prisma ORM. **Google Cloud Memorystore for Redis** (Stage 2). Vector storage via **pgvector extension on Cloud SQL**. (Subject to "Database Rethink" NFR-DB-RETHINK-1).  
* TC-STACK-4: Authentication: NextAuth.js (JWT session strategy, with GCP integration for social logins).  
* **TC-STACK-5:** File Storage: **Google Cloud Storage** (required for Stage 2 Media Blocks).  
* **TC-STACK-6:** AI Integration:  
  * Orchestration: **CrewAI** (Python-based, likely run as separate microservices on GCP called by Next.js backend).  
  * LLM Provider: To be decided (see ADR-010), options include Google Vertex AI, OpenAI, etc. Secure API key management via **Google Secret Manager**.  
  * Web content extraction libraries for "Create from Link."  
  * Flexible prompt engineering.  
* **TC-STACK-7:** Infrastructure: (Stage 1\) Local setup. **(Stage 2\) Google Cloud Platform (GCP)**, Docker, IaC (Terraform). Background job queue (e.g., BullMQ on GCP or Google Cloud Tasks).  
* **TC-STACK-8:** DevOps: GitHub. CI/CD (e.g., Google Cloud Build or GitHub Actions deploying to GCP). Error Tracking (e.g., Sentry or Google Cloud Error Reporting). Monitoring (Google Cloud's operations suite). Structured Logging.

## 6\. Release Criteria / Phasing (High Level)

* **Stage 1 (Local MVP Prototype \- Completed):**  
  * Focus: Core local functionality for capture and organization.  
  * Key Deliverables: Local Auth (Email/Pass), Block Editor (text), Manual Tagging, Folder CRUD, Local Keyword Search (PG FTS), JSON Data Export, Basic Onboarding, Graceful Session Expiry Handling.  
* **Stage 2 (GCP Production & Core AI Enhancements \- Current Focus):**  
  * Focus: Transition to a production-ready application on GCP with core AI features, improved UX, and robust infrastructure.  
  * **Key Deliverables:**  
    * **GCP Deployment:** Full application deployed on GCP (Cloud SQL, Cloud Storage, Cloud Run/GKE, Memorystore, etc.). CI/CD established.  
    * **Production UI/UX Overhaul:** Significantly improved user interface and experience.  
    * **Manual Hashtag System:** Implemented and integrated.  
    * **AI-Powered "Create from Link" (CrewAI):** Functional.  
    * **AI-Enhanced Card Generation & On-Demand Summarization (CrewAI):** Title, Tag, Content regeneration/summarization with diff/preview UI.  
    * Social Login.  
    * Media Blocks & Cloud Storage.  
    * Semantic Search Foundation (Backend: embeddings, pgvector setup).  
    * "Database Rethink" activity completed, with initial optimizations implemented.  
    * Manual JSON Data Import.  
* **Stage 2+ (Advanced Interaction & Features \- Future):**  
  * Focus: Building advanced knowledge synthesis, search, and interaction capabilities.  
  * Key Deliverables: Full Semantic Search UI, Chat with Knowledge Base (RAG), **Basic Dashboard Stats**, Knowledge Visualizations (Topic Clouds, Network Graphs), Advanced AI Features (Collection Summaries, Spark Prompts), Advanced User Settings.

## 7\. Open Questions

* Final choice for BlockNote and Chakra UI (assuming confirmed, but good to keep listed until fully integrated in new UI).  
* Specific GCP services for compute (Cloud Run vs. GKE for Next.js and Python/CrewAI services) \- needs detailed architectural design.  
* Final decision on LLM Provider (ADR-010).  
* Detailed UX design for AI regeneration diff/preview UI and hashtag input.  
* Specific outcomes and actionable changes from the "Database Rethink" activity.  
* Performance NFRs for Stage 2 on GCP (API latencies, AI processing times).  
* Detailed requirements/priority for specific Media Block types within Stage 2\.  
* Strategy for handling potential prompt injection or misuse of AI content generation features.  
* How to manage costs effectively for LLM API calls and GCP services.  
* User controls/preferences for AI features (e.g., disable certain AI assists \- potentially Stage 2+).