-- CreateTable
CREATE TABLE "ImageMetadata" (
    "id" TEXT NOT NULL,
    "knowledgeCardId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "gcsPath" TEXT NOT NULL,
    "contentType" TEXT NOT NULL,
    "originalFilename" TEXT NOT NULL,
    "size" INTEGER NOT NULL,
    "appServedUrl" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ImageMetadata_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "ImageMetadata_gcsPath_key" ON "ImageMetadata"("gcsPath");

-- CreateIndex
CREATE INDEX "ImageMetadata_knowledgeCardId_idx" ON "ImageMetadata"("knowledgeCardId");

-- CreateIndex
CREATE INDEX "ImageMetadata_userId_idx" ON "ImageMetadata"("userId");

-- CreateIndex
CREATE INDEX "ImageMetadata_gcsPath_idx" ON "ImageMetadata"("gcsPath");

-- AddForeignKey
ALTER TABLE "ImageMetadata" ADD CONSTRAINT "ImageMetadata_knowledgeCardId_fkey" FOREIGN KEY ("knowledgeCardId") REFERENCES "KnowledgeCard"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ImageMetadata" ADD CONSTRAINT "ImageMetadata_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
