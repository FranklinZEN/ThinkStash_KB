-- DropIndex
DROP INDEX "ImageMetadata_gcsPath_idx";

-- DropIndex
DROP INDEX "KnowledgeCard_userId_id_idx";

-- DropIndex
DROP INDEX "KnowledgeCard_userId_isStarred_idx";

-- DropIndex
DROP INDEX "KnowledgeCard_userId_isStarred_updatedAt_idx";

-- DropIndex
DROP INDEX "KnowledgeCard_userId_updatedAt_idx";

-- AlterTable
ALTER TABLE "ImageMetadata" ALTER COLUMN "knowledgeCardId" DROP NOT NULL;

-- AlterTable
ALTER TABLE "KnowledgeCard" ALTER COLUMN "content" DROP NOT NULL;
