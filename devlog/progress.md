# Thinkstash Development Progress

## Stage 2 Development Status

### Epic 0: Foundational Infrastructure & Core Features
Status: In Progress (Priority)

#### Tasks:
1. **TS-GCS-SETUP**: Setup Google Cloud Storage for Media
   - Status: Completed
   - Priority: High
   - Dependencies: None
   - Notes: GCS bucket is operational and service account permissions are configured for backend image uploads.

2. **TS-REDIS-SETUP**: Setup Managed Redis (Google Cloud Memorystore)
   - Status: Not Started
   - Priority: Medium
   - Dependencies: None
   - Notes: Required for session management and caching

3. **TS-MEDIA-BLOCK-BE**: Implement Image Block Backend Support
   - Status: Completed
   - Priority: High
   - Dependencies: TS-GCS-SETUP
   - Notes: Next.js API route `/api/upload/image` is functional, uploading images to GCS.

4. **TS-MEDIA-BLOCK-FE**: Implement Image Block in Frontend Editor
   - Status: Completed
   - Priority: High
   - Dependencies: TS-MEDIA-BLOCK-BE
   - Notes: BlockNote editor now supports image uploads to GCS via the `/api/upload/image` backend. The default `/image` slash command in BlockNote provides "Upload" and "Embed" options. Image URL handling robustly manages temporary blob URLs, converting to permanent app-served URLs upon saving, and ensuring correct display. Addressed race conditions and schema issues related to custom props for BlockNote image blocks.

5. **TS-SAVE-CARD**: Implement Save Card Functionality (Backend & Frontend)
   - Status: In Progress
   - Priority: High
   - Dependencies: TS-MEDIA-BLOCK-FE (for content generation)
   - Notes: Involves creating a Next.js API route to save card data (title, keywords, BlockNote JSON content with permanent image appServedUrls) to the database using Prisma, and updating the frontend to use this API. Core logic for saving content with correct image URLs from `NewCardPage.tsx` is now functional.

### Epic 1: Core AI Feature Backend Implementation (CrewAI)
Status: Paused

#### Tasks:
1. **TS-AI-1**: Setup CrewAI Development Environment
   - Status: Not Started
   - Priority: Low (Paused)
   - Dependencies: Epic 0 completion
   - Notes: Will resume after Epic 0 completion

2. **TS-AI-2**: Research & Decision on Initial LLM Provider(s)
   - Status: Not Started
   - Priority: Low (Paused)
   - Dependencies: Epic 0 completion
   - Notes: Will resume after Epic 0 completion

[Additional AI tasks listed but paused...]

### Epic 2: Frontend Integration for AI Features
Status: Paused

### Epic 3: Deployment & CI/CD for AI Microservices
Status: Paused

### Epic 4: Public Accessibility & SSL
Status: Paused

### Epic 5: Advanced Interaction - RAG Chat & Collaborative Card Creation
Status: Not Started (Future)

### Epic 6: Comprehensive Testing, Deployment Strategy & Operational Excellence
Status: In Progress (Partial)

#### Tasks:
1. **TS-TEST-1**: Review and Document Existing Testing Practices
   - Status: In Progress
   - Priority: Medium
   - Dependencies: None
   - Notes: Ongoing documentation of current testing state

2. **TS-TEST-2**: Define Comprehensive Testing Strategy & Standards
   - Status: Not Started
   - Priority: Medium
   - Dependencies: TS-TEST-1
   - Notes: Will be completed alongside Epic 0 development

### Epic 7: Explorative Content Ingestion Methods
Status: Not Started (Future)

## Development Notes

### Current Focus
- Priority is on completing Epic 0 tasks to establish foundational infrastructure.
- Implementing card saving functionality (TS-SAVE-CARD).
- AI feature development (Epics 1-4) is paused until Epic 0 is complete.
- Testing and documentation (Epic 6) continues in parallel with Epic 0.

### Next Steps
1. Begin TS-SAVE-CARD: Implement Save Card Functionality.
2. Continue documenting current testing practices (TS-TEST-1).
3. Define testing strategy (TS-TEST-2) alongside Epic 0 development.
4. Address TS-REDIS-SETUP when session management or caching becomes a priority.

### Blockers & Dependencies
- AI feature development blocked by Epic 0 completion
- Image handling features require GCS setup
- Frontend image block implementation depends on backend support

## Last Updated
- Date: 2024-03-22
- Version: 0.2.2

## 2025-05-17 - Secure Image Handling & Data Management (Sidecar Strategy)

Implemented a comprehensive secure image handling system using a sidecar data strategy. This ensures that images uploaded by users are private and only viewable by authorized individuals.

**Key Accomplishments:**

1.  **Architectural Decision & Core Setup:**
    *   Successfully adopted and implemented the "Sidecar Data" approach for secure, private image handling.
    *   Configured and utilized a private Google Cloud Storage (GCS) bucket (`thinkstash_media_gcs_bucket`) for image storage.
    *   Developed a backend API route (`/api/images/[...gcsPath]`) to serve images. This route includes robust authentication (session-based) and authorization logic, ensuring images are only accessible by their owners. Checked various unauthorized access scenarios successfully.

2.  **Image Metadata Management:**
    *   Created and integrated the `ImageMetadata` database table. This table stores essential details about each uploaded image (e.g., `gcsPath`, `contentType`, `originalFilename`, `size`, `appServedUrl`) and links them to `KnowledgeCard`s and `User`s.

3.  **Image Upload and Display Flow:**
    *   Refined the image upload API (`/api/upload/image`) to correctly upload files to GCS and return necessary metadata.
    *   Implemented client-side optimistic updates in `BlockNoteEditor.tsx`: images now appear instantly in the editor upon upload using temporary `Blob` object URLs. This significantly enhances the user experience.
    *   The permanent `appServedUrl` (e.g., `/api/images/images/USER_ID/FILENAME.png`) and `gcsPath` are stored as `data-` attributes within the image block's `props` in the editor.
    *   Ensured that when a `KnowledgeCard` is saved (`NewCardPage.tsx`), the editor content is processed to replace temporary object URLs with their permanent `appServedUrl` counterparts before being stored in the database.

4.  **Data Integrity and Management:**
    *   **Image Deletion:**
        *   When a `KnowledgeCard` is deleted (via `DELETE /api/cards/[cardId]`): its associated image files are removed from GCS, and their corresponding `ImageMetadata` records are deleted from the database. This process is handled within a database transaction.
        *   When an image is removed from a card's content during an update (via `PUT /api/cards/[cardId]`): the orphaned image file in GCS and its `ImageMetadata` record are also deleted, all within a database transaction.
    *   **Tag Management:**
        *   Ensured tags are normalized to lowercase upon saving (both for new cards and card updates) to maintain consistency.
        *   Implemented logic to delete orphaned tags from the database: when a `KnowledgeCard` is deleted, if any of its former tags are no longer associated with any other cards, those tags are removed.
    *   **Database Schema:** Reviewed and confirmed that database indexes for `ImageMetadata` (on `knowledgeCardId`, `userId`, `gcsPath`) and `Tag` relations are appropriate for efficient querying and data integrity.

5.  **Development and Debugging:**
    *   Addressed various issues throughout the development process, including initial GCS bucket configuration, BlockNote editor integration errors (e.g., `TypeError: Cannot read properties of undefined (reading 'requiredExtensions')`, leading to sticking with default image blocks), API route parameter handling (e.g., `params should be awaited`), and ensuring correct data flow between client and server components.
    *   **Resolved critical image display issues (Post 0.3.0 refinements):**
        *   Fixed bug where `blob:` URLs were saved instead of permanent URLs for uploaded images in `NewCardPage.tsx`, leading to `net::ERR_FILE_NOT_FOUND`. This involved several debugging iterations:
            *   Correcting BlockNote schema for custom image props (using camelCase like `appServedUrl` instead of `data-app-served-url`).
            *   Managing editor state and upload lifecycle with `activeUploads` counter and `editorRef`.
            *   Implementing a robust mapping (`blobUrlToPermanentDataMapRef`) to link temporary blob URLs to final server URLs, ensuring correct URL replacement during card save.
        *   Fixed a 500 Internal Server Error in the backend image serving route (`/api/images/[...gcsPath]`) by correctly converting Node.js GCS streams to Web API ReadableStreams using `Readable.toWeb()`.
        *   Addressed Next.js API route parameter handling warnings in image serving route.
    *   Performed code cleanup by removing verbose debugging `console.log` statements, while retaining essential logs for errors, warnings (like file not found in GCS), and security-relevant events.

**Next Steps Considerations (Post-Cleanup):**
*   Further refinement of editor behavior if any minor issues remain.
*   Consideration of more advanced features like image replacement/editing within a block or explicit sharing capabilities (currently out of scope). 