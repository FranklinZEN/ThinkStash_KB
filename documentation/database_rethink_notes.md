# Database Schema Rethink Notes

# Database Optimization Proposal (KC-DB-RETHINK-PROPOSE-1)

Based on the analysis performed in KC-DB-RETHINK-ANALYZE-1, this document outlines proposed optimizations for the ThinkStash database schema, indexing, and query patterns to enhance performance and scalability for both local use and future GCP deployment, incorporating Product Owner feedback and requirements.

## 1. Schema Modification Proposals (`prisma/schema.prisma`)

**Rationale:** Introduce fields necessary for AI features (summarization, RAG, semantic search) and improve data handling.

**Proposed Changes:**

1.  **Add `aiSummaryForRag` to `KnowledgeCard`:**
    *   **Purpose:** Store AI-generated summaries for user visibility and efficient RAG retrieval.
    *   **Schema Change:**
        ```prisma
        model KnowledgeCard {
          // ... existing fields ...
          aiSummaryForRag String?  @db.Text // Store AI-generated summary
          createdAt DateTime @default(now())
          updatedAt DateTime @updatedAt
          isStarred Boolean  @default(false)

          @@index([userId])
          // ... existing indexes ...
        }
        ```
    *   **Trade-offs:** Increases storage slightly. Requires a process to generate and populate this field (see Section 5).

2.  **Add `embedding` to `KnowledgeCard`:**
    *   **Purpose:** Store vector embeddings (likely of `content` or `aiSummaryForRag`, or potentially both in separate fields later) for semantic search and RAG. Requires the `pgvector` extension in PostgreSQL.
    *   **Schema Change (Requires `pgvector` extension enabled in PostgreSQL):**
        ```prisma
        // Add this at the top if not already present
        // Ensure pgvector extension is enabled in your database: CREATE EXTENSION IF NOT EXISTS vector;

        model KnowledgeCard {
          // ... existing fields ...
          aiSummaryForRag String?  @db.Text
          embedding       Unsupported("vector(1536)")? // Assuming OpenAI Ada v2 embedding dimension (adjust if different)

          createdAt DateTime @default(now())
          // ... rest of model ...
        }
        ```
        *Note: The exact dimension (e.g., 1536) should match the embedding model used. Prisma currently uses `Unsupported` for vector types.*
    *   **Trade-offs:** Significantly increases storage size per card. Requires `pgvector` extension. Requires robust embedding generation and update process (see Section 4).

3.  **(Placeholder Notation) AI-Generated Categorization:**
    *   **Status:** Feature deferred as per PO feedback.
    *   **Future Consideration:** If revisited, a field like `categoryCode String?` could be added to `KnowledgeCard`, potentially with an index (`@@index([userId, categoryCode])`). No schema changes proposed *at this time*.

**Summary of Schema Changes:** Add `aiSummaryForRag` (Text) and `embedding` (Vector) to `KnowledgeCard`.

## 2. Indexing Strategy Proposals

**Rationale:** Optimize query performance for existing patterns, new features (hashtags, FTS, semantic search), and address potential bottlenecks.

**Proposed Changes:**

1.  **Full-Text Search (FTS) on `KnowledgeCard.content`:**
    *   **Purpose:** Enable efficient searching within the main card content JSON.
    *   **Index Proposal (Requires Raw SQL Migration):** Create a GIN index on the `content` field. This indexes all text content within the JSONB structure.
        ```sql
        -- Migration SQL for adding FTS index
        CREATE INDEX idx_gin_knowledgecard_content ON "KnowledgeCard" USING GIN (to_tsvector('english', content));
        ```
        *Note: The effectiveness depends on the JSON structure. For highly structured JSON, indexing specific text fields might be more optimal but requires more complex generated columns or expression indexes.*
    *   **Trade-offs:** Increases index size and write time for `KnowledgeCard`. Enables fast text search.

2.  **Index on `KnowledgeCard.title`:**
    *   **Purpose:** Improve performance for sorting or filtering directly by title.
    *   **Index Proposal (Can be added in `schema.prisma`):**
        ```prisma
        model KnowledgeCard {
          // ... existing fields ...
          embedding       Unsupported("vector(1536)")?

          createdAt DateTime @default(now())
          // ... rest of model ...

          @@index([userId])
          @@index([folderId])
          @@index([userId, isStarred])
          @@index([userId, updatedAt])
          @@index([userId, id])
          @@index([userId, isStarred, updatedAt])
          @@index([title]) // New index for title searches/sorting
        }
        ```
    *   **Trade-offs:** Minor increase in index size and write time. Speeds up title-based operations.

3.  **pgvector HNSW Index on `KnowledgeCard.embedding`:**
    *   **Purpose:** Enable fast Approximate Nearest Neighbor (ANN) search for semantic similarity using the `embedding` field. HNSW confirmed as preferred type.
    *   **Index Proposal (Requires Raw SQL Migration):**
        ```sql
        -- Migration SQL for adding pgvector HNSW index
        -- Ensure pgvector extension is enabled first: CREATE EXTENSION IF NOT EXISTS vector;
        CREATE INDEX idx_hnsw_knowledgecard_embedding ON "KnowledgeCard" USING hnsw (embedding vector_cosine_ops) WITH (m = 32, ef_construction = 128);
        ```
        *   **Parameters:**
            *   `m = 32`: Number of neighbors per node (controls memory usage, typical range 16-64). Start with 32.
            *   `ef_construction = 128`: Size of dynamic candidate list during index build (controls build time vs. quality, typical range 64-512). Start with 128.
        *   **Tuning:** These parameters (`m`, `ef_construction`, and `ef_search` used at query time) **must be tuned** based on data size, performance testing, and desired recall/precision trade-offs. The initial values are starting points.
        *   `vector_cosine_ops`: Assumes cosine similarity is desired. Use `vector_l2_ops` for Euclidean distance or `vector_ip_ops` for inner product if appropriate for your embedding model.
    *   **Trade-offs:** Significant index build time and storage size. Enables fast semantic search. Requires careful parameter tuning.

**Summary of Indexing Changes:** Add GIN FTS index on `content`, B-tree index on `title`, and HNSW vector index on `embedding`.

## 3. Query Refactoring & New Pattern Recommendations

**Rationale:** Implement missing search/filter logic efficiently and optimize existing queries.

**Proposed Changes:**

1.  **`GET /api/cards` - Reduce Payload:**
    *   **Problem:** Currently selects the full `content` JSON, which can be large for a list view.
    *   **Recommendation:**
        *   **Option A (Preferred once available):** Select `aiSummaryForRag` instead of `content` for list views. Requires the summary generation process to be reliable.
        *   **Option B (Interim):** Explicitly *exclude* `content` from the `select` statement in the `GET /api/cards` list query if the full content is not needed on the front-end card list. Fetch full content only when viewing/editing a single card.
            ```typescript
            // Example Option B in GET /api/cards findMany
            select: {
              id: true,
              title: true,
              // ... other needed fields ...
              isStarred: true,
              updatedAt: true,
              // content: true, // <--- OMIT THIS LINE
              folder: { select: { id: true, name: true } },
              tags: { select: { name: true } },
            },
            ```

2.  **Hashtag/Keyword Filtering Query:**
    *   **Purpose:** Allow filtering cards by one or more tags.
    *   **Recommendation:** Add a `tags` query parameter (e.g., `?tags=tag1,tag2`). Modify the `findMany` `where` clause:
        ```typescript
        // Example where clause for filtering by tags
        where: {
          userId: userId,
          AND: tagsArray.length > 0 ? tagsArray.map(tagName => ({
            tags: {
              some: {
                name: tagName
              }
            }
          })) : undefined, // Add this condition if tagsArray exists
          // ... other existing where conditions ...
        },
        ```
        *(Requires parsing the `tags` query parameter into `tagsArray`)*

3.  **General Search Query (FTS + Keywords):**
    *   **Purpose:** Search user query within card `title`, `content` (FTS), and associated `tags`.
    *   **Recommendation:** This requires a more complex query. A potential approach:
        *   Use FTS on `content` and potentially `title`.
        *   Search for matching `Tag` names.
        *   Combine results using OR logic, potentially ranking FTS matches higher.
        *   This might involve raw SQL queries using `to_tsquery` and potentially joining tables, or multiple separate Prisma queries combined application-side.
        ```sql
        -- Conceptual Raw SQL Snippet (Needs refinement)
        SELECT card.id, card.title -- other fields...
        FROM "KnowledgeCard" card
        LEFT JOIN "_CardTags" ct ON card.id = ct."A"
        LEFT JOIN "Tag" tag ON ct."B" = tag.id
        WHERE
          card."userId" = $1 AND (
            to_tsvector('english', card.content) @@ to_tsquery('english', $2) OR -- FTS on content
            card.title ILIKE $3 OR -- Simple title match
            tag.name ILIKE $3 -- Simple tag match
          )
        GROUP BY card.id, card.title -- Ensure unique cards
        ORDER BY -- Ranking logic TBD
        LIMIT $4 OFFSET $5;
        ```
        *(Where $2 is the parsed FTS query, $3 is a pattern like `%query%`)*

4.  **Keyword-Only Search Query:**
    *   **Purpose:** Search only within `Tag.name` associated with the user's cards.
    *   **Recommendation:** Find `Tag`s matching the query, then fetch associated `KnowledgeCard`s belonging to the user.
        ```typescript
        // Example Prisma query structure
        const matchingTags = await prisma.tag.findMany({
          where: {
            name: { contains: searchQuery, mode: 'insensitive' },
            // Ensure tag is connected to *any* card of the user? (Optional optimization)
          },
          select: { id: true }
        });

        const cards = await prisma.knowledgeCard.findMany({
          where: {
            userId: userId,
            tags: {
              some: {
                id: { in: matchingTags.map(t => t.id) }
              }
            }
          },
          // ... select, orderBy, pagination ...
        });
        ```

5.  **RAG Retrieval Query (Using Summary Embedding):**
    *   **Purpose:** Find cards most relevant to a query based on `aiSummaryForRag` embedding similarity.
    *   **Recommendation (Requires `embedding` field and pgvector index):** Use a raw SQL query with the vector distance operator (`<->`). Assume a separate `summaryEmbedding` field exists or the main `embedding` field stores the summary's vector.
        ```typescript
        // Prisma Raw Query Example
        const queryEmbedding = [...] // Get embedding for the user's query
        const k = 10; // Number of nearest neighbors

        const results = await prisma.$queryRaw`
          SELECT
            id,
            title,
            "aiSummaryForRag",
            embedding <-> CAST(${queryEmbedding} AS vector) AS distance
          FROM "KnowledgeCard"
          WHERE "userId" = ${userId}
          ORDER BY distance ASC
          LIMIT ${k}
        `;
        ```
        *(Requires embedding generation for summaries and `aiSummaryForRag` field population)*

## 4. Vector Embedding Update Strategy (Asynchronous via BullMQ)

**Rationale:** Regenerating embeddings via external AI models can be slow and costly. Performing this synchronously would degrade user experience. An asynchronous background job queue is essential.

**Proposed Process:**

1.  **Trigger:** When `KnowledgeCard` `content` (or `aiSummaryForRag`, if embedded separately) is created or updated successfully in a primary operation (e.g., `POST /api/cards`, `PUT /api/cards/:id`).
2.  **Enqueue Job:** After the primary database transaction (saving text content) commits successfully, add a job to a dedicated BullMQ queue (e.g., `embedding-queue`).
    *   **Job Data:** `{ cardId: '...', type: 'content' | 'summary' }` (or similar to indicate what needs embedding).
3.  **BullMQ Worker (`embedding-worker.ts`):**
    *   **Dequeue Job:** Worker picks up jobs from `embedding-queue`.
    *   **Fetch Data:** Retrieves the necessary text (`content` or `aiSummaryForRag`) for the `cardId` from the database using Prisma.
    *   **Call Embedding Service:** Uses an `AIService` module to call the relevant embedding model API (e.g., OpenAI) with the fetched text.
    *   **Update Database:** On successful API response, updates the corresponding `embedding` (or `summaryEmbedding`) field in the `KnowledgeCard` record using `prisma.knowledgeCard.update()`.
4.  **Error Handling:**
    *   **API Errors/Timeouts:** Implement retry logic within the BullMQ job (e.g., retry 3 times with exponential backoff).
    *   **Persistent Failures:** After max retries, move the job to a dead-letter queue for manual inspection/reprocessing. Log the error clearly.
    *   **Database Errors:** Handle potential Prisma errors during the final update.
5.  **Staleness Management:**
    *   During the time between content update and embedding update, the embedding is stale.
    *   **Strategies:**
        *   Accept temporary staleness (simplest).
        *   Add a status field to `KnowledgeCard` (e.g., `embeddingStatus: 'pending' | 'completed' | 'failed'`) and potentially exclude cards with `pending` or `failed` status from vector searches.
        *   Serve the old embedding until the new one is ready.
6.  **Cost Consideration:** This process incurs costs for each embedding generation call.

## 5. Data Consistency Strategy for AI Updates

**Rationale:** AI features often modify multiple related fields (content, summary, embedding, tags). Atomic updates are crucial to prevent inconsistent states.

**Proposed Strategy:**

1.  **Use `prisma.$transaction`:** Group all database writes related to a single logical AI operation within a transaction.
2.  **Order of Operations:**
    *   **Step 1 (Pre-Transaction):** Perform external AI calls that *generate* data needed for the database update (e.g., generate `aiSummaryForRag`, potentially generate `title` or `tags` if applicable to the AI feature). If these fail, handle the error before attempting database writes (e.g., inform user, retry AI call).
    *   **Step 2 (Transaction):** Start `prisma.$transaction`. Inside the transaction:
        *   Update/Create `KnowledgeCard` with new textual content (`title`, `content`, `aiSummaryForRag`).
        *   Update/Create associated `Tag`s using `connectOrCreate`.
        *   *(Do NOT perform slow external calls like embedding generation *inside* the transaction).*
    *   **Step 3 (Post-Transaction):** If the transaction succeeds, enqueue the necessary background jobs (e.g., BullMQ job to update the `embedding` based on the saved content/summary).
3.  **Handling Partial Failures:**
    *   **AI Call Failure (Step 1):** The database remains unchanged. Decide user experience (retry? show error?).
    *   **Transaction Failure (Step 2):** `prisma.$transaction` automatically rolls back all database changes within it. The state remains consistent (as before the transaction). Log the error.
    *   **Job Enqueue Failure (Step 3):** The primary data is saved, but the async job (e.g., embedding) isn't triggered. This requires monitoring or a mechanism to periodically check for cards needing embedding updates.
    *   **Async Job Failure (BullMQ Worker):** Handled by worker's retry/dead-letter queue logic (see Section 4). Does not affect the primary data saved in the transaction.

**Example `prisma.$transaction` for Creating a Card with AI Summary:**

```typescript
// Assume aiSummary was generated successfully *before* this point
try {
  const [newCard] = await prisma.$transaction(async (tx) => {
    const createdCard = await tx.knowledgeCard.create({
      data: {
        title: title.trim(),
        content: content,
        aiSummaryForRag: aiSummary, // Include the generated summary
        user: { connect: { id: userId } },
        ...(tags && tags.length > 0 && {
          tags: {
            connectOrCreate: tags.map((tagName: string) => ({
              where: { name: tagName.trim() },
              create: { name: tagName.trim() },
            })),
          },
        }),
        // Don't set embedding here
      },
      select: { id: true }, // Select ID for the next step
    });

    // Return card ID or other necessary info for post-transaction step
    return [createdCard];
  });

  // If transaction was successful, enqueue embedding job
  if (newCard?.id) {
    await embeddingQueue.add('embed-card', { cardId: newCard.id, type: 'content' }); // Or 'summary' if embedding summary
    // Maybe also queue job for summary embedding if separate
  }

  // Return success response to user
  // ...

} catch (error) {
  // Handle transaction error (database inconsistency avoided)
  console.error("Transaction failed:", error);
  // Return error response to user
  // ...
}
```

## 6. Implementation & Testing Plan

1.  **Implement Schema Changes:** Add `aiSummaryForRag` and `embedding` fields to `prisma/schema.prisma`.
2.  **Add Indexes:** Create Prisma migration for the `title` index. Create raw SQL migrations for FTS and HNSW indexes.
3.  **Enable `pgvector`:** Ensure the PostgreSQL extension is enabled in the development environment (and later, GCP).
4.  **Refactor Queries:** Update `GET /api/cards` payload. Implement new API endpoints or modify existing ones for hashtag/keyword search. Implement RAG query logic.
5.  **Setup BullMQ:** Install BullMQ, configure queues (`embedding-queue`), create worker process (`embedding-worker.ts`).
6.  **Develop AIService:** Create a module/service to handle interactions with the embedding model API.
7.  **Implement Async Trigger:** Add logic post-transaction in relevant API routes (`POST /api/cards`, `PUT /api/cards/:id`) to enqueue BullMQ jobs.
8.  **Implement Transactional Logic:** Wrap relevant database operations in `prisma.$transaction` as described.
9.  **Testing:**
    *   **Unit Tests:** Test AIService, BullMQ job handling logic.
    *   **Integration Tests:** Test API endpoints for new search/filter functionality. Test the full flow of card update -> BullMQ job -> embedding update. Test transaction rollbacks.
    *   **Performance Tests (Local/Staging):** Use tools like `pgbench` or application-level load testing with `EXPLAIN ANALYZE` on queries (especially FTS, vector search, tag filtering) with a realistic amount of data (\~50k vectors/cards per user as a target). Tune HNSW parameters based on results.

## 7. Migration Notes

*   **`pgvector` Extension:** Must be enabled in the PostgreSQL database before migrations adding vector columns or indexes can run.
*   **Raw SQL Migrations:** FTS and HNSW index creation will require raw SQL in Prisma migration files.
*   **Backfilling Data:**
    *   Existing `KnowledgeCard` records will have `NULL` for `aiSummaryForRag` and `embedding`.
    *   A script/batch process will be needed to:
        1.  Generate `aiSummaryForRag` for all existing cards (potentially costly and time-consuming).
        2.  Generate `embedding`s for all existing cards based on their `content` or newly generated `aiSummaryForRag`. This should likely use the BullMQ system developed in Section 4.
