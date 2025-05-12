-- This is an empty migration.
-- Add FTS index for KnowledgeCard titles
CREATE INDEX knowledge_card_title_fts_idx ON "KnowledgeCard" USING gin(to_tsvector('english', title));