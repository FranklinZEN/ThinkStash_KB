# **Product Requirement Document (PRD)**

Product: Web-Based Knowledge Card System (v3)  
Version: 3.7 (Updated post-Stage 1 reviews)  
Date: 2025-04-21  
Status: Draft

## **1\. Introduction**

### **1.1 Overview**

This document outlines the requirements for the Web-Based Knowledge Card System, a platform designed to help knowledge workers, professionals, researchers, and educators capture, organize, discover, synthesize, and utilize information effectively. Users can create rich, multimedia "knowledge cards," organize them into hierarchical folders, retrieve information through powerful search, visualize connections, interact conversationally, and actively generate new ideas from their knowledge base using AI. Stage 1 focuses on a local/offline-capable MVP for core capture and organization, while Stage 2 introduces cloud storage, foundational AI features, and initial knowledge synthesis capabilities. Stage 2+ builds further with advanced interaction features.

### **1.2 Goals & Business Objectives**

* Increase User Productivity: Enable users to quickly capture and retrieve information.  
* Facilitate Knowledge Organization: Provide intuitive tools (folders, tags) for structuring personal knowledge bases.  
* Enhance Content Creation & Understanding: Offer a flexible block-based editing experience (Stage 1\) and leverage AI to summarize content (Stage 2).  
* Streamline Information Capture: Allow seamless creation of summarized and tagged knowledge cards directly from web links using AI (Stage 2), with robust fallbacks.  
* Enable Knowledge Synthesis & Idea Generation: Help users discover connections (visual/semantic), review themes (summaries/clouds), compare concepts (juxtaposition), and generate new insights (RAG chat, spark prompts) from their stored knowledge (Stage 2 & 2+).  
* Provide AI-driven Assistance: Leverage AI to assist with content creation (titles \- Stage 2), organization (tags from links \- Stage 2), summarization (Stage 2), visualization (Stage 2), interaction (RAG Chat \- Stage 2+), and creativity (Spark Prompts \- Stage 2+).  
* Ensure Security & Reliability: Build user trust through secure authentication and reliable data storage (local for Stage 1, cloud for Stage 2).

### **1.3 Target Audience**

* Knowledge Workers  
* Business Professionals  
* Researchers & Academics  
* Students & Educators  
* Anyone needing to organize notes, research, or ideas digitally, and wanting tools to help synthesize, visualize, and build upon that knowledge to foster creativity.

### **1.4 Scope**

**In Scope (Core Functionality):**

* **Stage 1 (Local/Offline MVP):**  
  * Secure User Authentication (Email/Password only).  
  * User Profile Management (Basic Name).  
  * Knowledge Card Creation using a Block-Based Editor (core text blocks).  
  * Tagging of Knowledge Cards (Manual).  
  * Folder Management (Hierarchy, including deletion policy).  
  * Assigning Cards to Folders.  
  * Basic Keyword Search (local data \- PostgreSQL FTS).  
  * Basic Dashboard stats (local data).  
  * Responsive Web Interface.  
  * Ability to run locally. Data stored locally (PostgreSQL).  
  * JSON Data Export.  
  * Basic User Onboarding/Help.  
  * Graceful Session Expiry Handling.  
* **Stage 2 (Cloud Backend & Foundational AI & Synthesis):**  
  * Cloud-based backend & data sync.  
  * Social Login.  
  * Media Blocks (Image, Video) w/ Cloud Storage.  
  * AI Title Suggestion.  
  * AI-Powered "Create from Link" (Summary+Tags, with fallback).  
  * AI On-Demand Summarization.  
  * Semantic Search Foundation (Embeddings \+ Vector DB).  
  * AI Collection Summaries on Folder/Tag On-demand.  
  * Knowledge Visualization: Topic Clouds, Network Graphs.  
  * Caching, Background Jobs, Full CI/CD, Monitoring.  
* **Stage 2+ (Advanced Interaction & Refinements):**  
  * Semantic Similarity Surfacing (Related Cards).  
  * Tag Intersection Explorer.  
  * Chat with Knowledge Base (RAG).  
  * AI "Spark" Prompts.  
  * Concept Juxtaposition Tool.  
  * Serendipity Mode.  
  * Advanced Search Filtering & Querying (Semantic).  
  * Advanced User Settings (Password Reset, Account Deletion).

**Out of Scope (Potential Future Enhancements):**

* Real-time Collaboration / Multi-user Editing.  
* Advanced Sharing and Permissions Models.  
* Offline Functionality (beyond Stage 1's local nature).  
* Public publishing of cards/folders.  
* AI Auto-Tagging for manually created cards (unless added to Stage 2+).  
* Mobile Native Applications.  
* Integration with third-party services (beyond auth).  
* Highly advanced, customizable reporting beyond defined visualizations.  
* Automated Theme Detection (NLP Topic Modeling).  
* Data Import functionality.

## **2\. Functional Requirements**

### **2.1 User Authentication & Security (Epic: KC-AUTH)**

* FR-AUTH-1: (Stage 1\) Local Email/Password Registration.  
* FR-AUTH-2: (Stage 1\) Local Email/Password Login.  
* FR-AUTH-3: (Stage 2\) Social Login (Google, GitHub, etc.).  
* **FR-AUTH-4:** (Stage 1\) Secure Password Hashing (bcrypt). Passwords must meet complexity requirements: **Minimum 6 characters, including at least one uppercase letter, one lowercase letter, one number, and one special character.**  
* **FR-AUTH-5:** (Stage 1\) Secure Session Management. Implementation uses **JWT (JSON Web Tokens)** managed via NextAuth.js.  
* FR-AUTH-6: (Stage 1\) Basic Profile View/Update (Name).  
* FR-AUTH-7: (Stage 2+) Password Reset via Email.  
* FR-AUTH-8: (Stage 2+) Account Management (Linked Accounts, Delete Account).  
* FR-AUTH-9: (Stage 1+) HTTPS & Basic Web Security.  
* **FR-AUTH-10:** (Stage 1\) Graceful Session Expiry Handling. The UI must inform the user clearly (e.g., via toast message) and redirect to login when an active session expires or becomes invalid during API interactions.

### **2.2 Knowledge Card Creation (Epic: KC-CARD-CREATE)**

* **FR-CARD-1:** Block-Based Editor:  
  * (Stage 1\) Users must create and edit card content using a block-based editor interface.  
  * (Stage 1\) The editor must support core text block types: Paragraph, Headings (H1, H2, H3), Unordered Lists, Ordered Lists (with basic formatting: Bold, Italic).  
  * (Stage 2\) The editor must support media blocks: Image Blocks (upload/URL), Video Embed Blocks, Code Blocks.  
  * (Stage 1\) Users must be able to easily add, delete, and reorder blocks.  
  * (Stage 1\) Content must be saved as structured JSON data (locally in Stage 1).  
* FR-CARD-2: Card Metadata: (Stage 1: Title, Manual Tags; Stage 2: AI Tags from Link).  
* FR-CARD-3: (Stage 2\) AI-Powered Create from Link:  
  * Users must be able to paste a URL.  
  * System fetches content securely (cloud).  
  * System extracts Title.  
  * System uses GenAI (LLM) to generate a concise summary (cloud).  
  * System uses GenAI (LLM) to suggest relevant tags (cloud).  
  * New card created (cloud DB) with title, AI summary (block format), AI tags, source URL.  
  * Fallback Behavior: If AI summarization or tagging fails (due to API errors, content complexity, etc.), the system must still create a card containing the extracted Title, the original source URL, and the extracted main body text (if available via Readability.js, stored in block format). The UI must indicate the partial success/failure and potentially offer an option for the user to manually trigger the AI processing again later for that card.  
  * Optional: Store extracted main body text alongside AI summary even on success.  
  * Provide async feedback and handle errors.  
* FR-CARD-4: (Stage 2\) AI Title Suggestion: Trigger AI suggestion based on block content.  
* FR-CARD-5: (Stage 2\) AI On-Demand Summarization: Trigger AI summary for any existing card.

### **2.3 Organization (Folders & Tags) (Epic: KC-ORG)**

* FR-ORG-1: (Stage 1\) Create Folders.  
* FR-ORG-2: (Stage 1\) Rename Folders.  
* **FR-ORG-3:** (Stage 1\) Delete Folders. The system must **prevent** the deletion of a folder if it contains cards or sub-folders. The UI must inform the user why the deletion cannot proceed in this case. Empty folders can be deleted after user confirmation.  
* FR-ORG-4: (Stage 1\) Folder Hierarchy.  
* FR-ORG-5: (Stage 1\) Assign Card to Folder.  
* FR-ORG-6: (Stage 1\) Move Card between Folders (including moving to root/no folder).  
* FR-ORG-7: (Stage 1\) View Folder Structure (e.g., Tree).  
* FR-ORG-8: (Stage 1\) View Cards within Folder (Filtering card list by selected folder).  
* FR-ORG-9: (Stage 1\) View Cards associated with Tag (Filtering card list by selected tag).

### **2.4 Search & Discovery (Epic: KC-SEARCH)**

* **FR-SEARCH-1:** (Stage 1\) Keyword Search: Search Title & Block Text content using PostgreSQL Full-Text Search (local). Results should optionally display highlighted snippets (headline).  
* FR-SEARCH-2: (Stage 2\) Semantic Search Foundation: Implement vector embedding generation and storage.  
* FR-SEARCH-3: (Stage 2+) Semantic Search Querying: Implement semantic search API and UI.  
* FR-SEARCH-4: (Stage 2+) Filtering: Filter search results.  
* FR-SEARCH-5: (Stage 2+) Semantic Similarity Surfacing (Related Cards): Display semantically similar cards.

### **2.5 Knowledge Insights & Interaction (Epic: KC-INSIGHTS)**

* FR-INSIGHT-1: (Stage 1\) Basic Dashboard Stats: Display basic counts (Cards, Tags, Folders) from local data. Optional: Recent cards list.  
* FR-INSIGHT-2: (Stage 2\) Knowledge Visualization \- Topic Cloud: Implement tag frequency visualization. Clicking tag filters view.  
* FR-INSIGHT-3: (Stage 2\) Knowledge Visualization \- Network Graph: Implement card relationship graph (Links, Tags, Semantic Similarity). Zoom/pan/click navigation.  
* FR-INSIGHT-4: (Stage 2\) AI Collection Summaries: Select multiple cards/folder/tag \-\> Trigger AI summary of collective content.  
* FR-INSIGHT-5: (Stage 2+) Tag Intersection Explorer: Select multiple tags \-\> View cards with all selected tags.  
* FR-INSIGHT-6: (Stage 2+) Chat with Knowledge Base (RAG): Ask questions \-\> System finds relevant cards via semantic search \-\> LLM generates answer based on card context \-\> Display response with citations.  
* FR-INSIGHT-7: (Stage 2+) AI "Spark" Prompts: Trigger AI to generate creative prompts ("What if?", etc.) based on current context (card/tag).  
* FR-INSIGHT-8: (Stage 2+) Concept Juxtaposition Tool: Select items \-\> AI highlights similarities/differences/synthesis points.  
* FR-INSIGHT-9: (Stage 2+) Serendipity Mode: Surface potentially relevant but unexpected cards.

### **2.6 AI Enhancements (Epic: KC-AI)**

* FR-AI-1: AI Title Suggestion (Stage 2): As defined in FR-CARD-4.  
* FR-AI-2: AI Summarization & Tagging for Link Creation (Stage 2): As defined in FR-CARD-3.  
* FR-AI-3: AI On-Demand Summarization (Stage 2): As defined in FR-CARD-5.  
* FR-AI-4: AI Collection Summaries (Stage 2): As defined in FR-INSIGHT-4.  
* FR-AI-5: AI Spark Prompts (Stage 2+): As defined in FR-INSIGHT-7.  
* FR-AI-6: AI Concept Juxtaposition (Stage 2+): As defined in FR-INSIGHT-8.  
* FR-AI-7: (Future) AI Auto-Tagging (Manual Cards): Potential future enhancement.

### **2.7 Data Management (Epic: KC-DATA)**

* **FR-DATA-1:** (Stage 1\) Data Export. Users must be able to export all their personal data (cards including content, tags, folders) in a structured JSON format via a UI action.

### **2.8 User Experience (Epic: KC-UX / KC-ONBOARDING)**

* **FR-UX-ONBOARD-1:** (Stage 1\) Basic Onboarding. The application must provide minimal onboarding guidance (e.g., welcome modal or contextual hints) for new users interacting with core features for the first time.

## **3\. Non-Functional Requirements**

* NFR-PERF-1: Responsiveness: UI interactions responsive, async handling for long ops (Stage 2).  
* NFR-SCALE-1: Scalability: (Stage 2\) Cloud architecture must scale.  
* NFR-SEC-1: Security: Standard web security, HTTPS, secure auth (password complexity, hashing, JWT session), key handling (Stage 2), encryption (Stage 2 cloud). Local data security TBD. Least privilege principles applied in cloud infra (Stage 2).  
* NFR-USE-1: Usability: Intuitive interface, efficient workflows. Includes basic onboarding/help (Stage 1).  
* NFR-A11Y-1: Accessibility: Adhere to basic WCAG AA guidelines.  
* NFR-MAINT-1: Maintainability: Well-structured, commented, tested code. Includes schema documentation (Stage 1). Use of IaC (Stage 2).  
* NFR-REL-1: Reliability: Proper error handling (including graceful session expiry \- Stage 1). (Stage 2\) Monitoring & cloud backups.  
* **NFR-DEPLOY-1:** (Stage 2\) Automated Deployments. CI/CD pipeline must automate build, testing (future), and deployment to cloud environments.

## **4\. Design Considerations**

* DC-UI-1: Clean, modern, intuitive UI. Use a component library (Chakra UI).  
* DC-UX-1: User flows designed for efficiency. Specific attention to block editor, "Create from Link" (async feedback \- Stage 2), Knowledge Visualization interfaces (Stage 2), RAG Chat interface (Stage 2+), triggers for other insight features, onboarding flow (Stage 1), data export trigger (Stage 1), session expiry feedback (Stage 1).  
* DC-RESP-1: Fully responsive application.  
* DC-DIAG-1: Maintain high-level architecture diagrams.

## **5\. Technical Considerations**

* TC-STACK-1: Frontend: React/Next.js/TS. Zustand. Block Editor Lib (Primary consideration: BlockNote). UI Lib (Primary consideration: Chakra UI). Visualization Lib (Primary consideration for Network Graph: react-flow; others TBD \- Stage 2).  
* TC-STACK-2: Backend: Node.js via Next.js API routes.  
* TC-STACK-3: Database: PostgreSQL (jsonb support required). Prisma ORM. Redis (Stage 2). Vector Database (Primary consideration: Pinecone \- Stage 2).  
* TC-STACK-4: Authentication: NextAuth.js (JWT session strategy).  
* TC-STACK-5: File Storage: Local FS (Stage 1 \- not for primary data, maybe PoC). Cloud Object Storage (e.g., AWS S3 \- required for Stage 2 Media Blocks).  
* TC-STACK-6: AI Integration: (Stage 2+) Architect for Multi-Cloud Provider (MCP) approach via an abstraction layer, implement OpenAI first. LLM APIs for summarization, tagging, title suggestion, RAG response generation, etc. Embedding models for semantic search/RAG. Web content extraction libs. Secure API key management. Flexible prompt engineering strategies required to potentially support different agents/prompts.  
* TC-STACK-7: Infrastructure: (Stage 1\) Local setup (Docker Compose for DB). (Stage 2\) Cloud hosting (AWS), Docker, IaC (Terraform). Background job queue.  
* TC-STACK-8: DevOps: GitHub (Version Control), GitHub Actions (basic checks Stage 1, full pipeline Stage 2). Sentry (Stage 2). Monitoring (CloudWatch \- Stage 2). Structured Logging.

## **6\. Release Criteria / Phasing (High Level)**

* **Stage 1 (Local/Offline MVP Prototype):** Focus on core local functionality. Includes Auth (Email/Pass \- local, JWT), Block Editor (text blocks), Card/Tag(manual)/Folder CRUD (local, prevent non-empty folder delete), Keyword Search (local PG FTS), Basic Dashboard stats (local), Data Export (JSON), Basic Onboarding, Graceful Session Expiry. No cloud AI, no Social Login, no cloud storage/Media Blocks. Validate core local experience.  
* **Stage 2 (Production Cloud & Foundational AI & Synthesis):** Focus on cloud deployment, data sync, cloud storage, enabling foundational cloud-dependent AI, and initial synthesis features. Includes Cloud DB setup (RDS), Social Login, Media Blocks w/ Cloud Storage (S3), AI Title Suggestion, AI-Powered Create-from-Link (with fallback), AI On-Demand Summarization, Semantic Search Foundation (Embeddings \+ Vector DB), AI Collection Summaries, Knowledge Visualization (Topic Clouds, Network Graphs), Caching (Redis), Background Jobs (BullMQ/SQS), full Testing, Monitoring (CloudWatch), CI/CD (GitHub Actions), IaC (Terraform).  
* **Stage 2+ (Advanced Interaction & Refinements):** Build upon Stage 2 infrastructure. Includes Semantic Similarity Surfacing (Related Cards), Tag Intersection Explorer, Chat with Knowledge Base (RAG), AI Spark Prompts, Concept Juxtaposition, Serendipity Mode, Advanced Search Filtering & Querying (Semantic), Advanced User Settings (Password Reset, Account Deletion).

## **7\. Open Questions**

* Confirm final choice and integration details for BlockNote (Block Editor), Chakra UI (UI Lib), Pinecone (Vector DB), react-flow (Network Graph Vis)? Research needed for other visualization libraries (Topic Cloud, etc.).  
* Detailed requirements/priority for specific Media Block types (Image, Video, Code) within Stage 2?  
* Define specific reliability targets (e.g., success rate) for Stage 2 Create from Link content extraction and AI processing? How should retries be handled in UI/BE?  
* Define detailed prompt engineering strategies and potential for using different AI agents/prompts for Stage 2+ features? (Acknowledged as deferred planning).  
* Performance NFRs for Stage 1 (local) and Stage 2 (cloud)?  
* Security compliance requirements?  
* How to handle storage/display if Stage 2 AI summarization fails or produces poor results? Store original extracted text alongside AI summary for Stage 2 Link-to-Card?  
* Strategy for packaging/distributing Stage 1 local application? (Node server vs Electron vs other?) Data migration strategy from Stage 1 to Stage 2 (JSON export confirmed as mechanism)?  
* Specific requirements & prioritization for Knowledge Visualization features (Topic Cloud vs Network Graph \- now both Stage 2)? Needs detailed UX/technical design.  
* Detailed design for RAG Chat interface, context window handling, and citation display (Stage 2+)?  
* User controls/preferences for AI features (e.g., disable certain AI assists, choose models \- Stage 2+)?  
* Algorithm details for Serendipity Mode (Stage 2+)?  
* Detailed requirements for Concept Juxtaposition analysis (Stage 2+)?