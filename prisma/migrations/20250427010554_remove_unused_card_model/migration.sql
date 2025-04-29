-- AlterTable
ALTER TABLE "KnowledgeCard" ADD COLUMN     "isStarred" BOOLEAN NOT NULL DEFAULT false;

-- CreateIndex
CREATE INDEX "KnowledgeCard_userId_isStarred_idx" ON "KnowledgeCard"("userId", "isStarred");
