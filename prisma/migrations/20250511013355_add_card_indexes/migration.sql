-- CreateIndex
CREATE INDEX "KnowledgeCard_userId_updatedAt_idx" ON "KnowledgeCard"("userId", "updatedAt");

-- CreateIndex
CREATE INDEX "KnowledgeCard_userId_id_idx" ON "KnowledgeCard"("userId", "id");
