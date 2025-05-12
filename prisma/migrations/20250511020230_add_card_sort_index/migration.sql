-- CreateIndex
CREATE INDEX "KnowledgeCard_userId_isStarred_updatedAt_idx" ON "KnowledgeCard"("userId", "isStarred", "updatedAt");
