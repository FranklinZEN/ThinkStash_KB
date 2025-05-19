-- CreateTable
CREATE TABLE "ImageRecord" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "gcsPath" TEXT NOT NULL,
    "contentType" TEXT NOT NULL,
    "originalFilename" TEXT NOT NULL,
    "size" INTEGER NOT NULL,
    "appServedUrl" TEXT NOT NULL,
    "knowledgeCardId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ImageRecord_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "ImageRecord_gcsPath_key" ON "ImageRecord"("gcsPath");

-- CreateIndex
CREATE UNIQUE INDEX "ImageRecord_appServedUrl_key" ON "ImageRecord"("appServedUrl");

-- CreateIndex
CREATE INDEX "ImageRecord_userId_idx" ON "ImageRecord"("userId");

-- CreateIndex
CREATE INDEX "ImageRecord_knowledgeCardId_idx" ON "ImageRecord"("knowledgeCardId");

-- AddForeignKey
ALTER TABLE "ImageRecord" ADD CONSTRAINT "ImageRecord_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ImageRecord" ADD CONSTRAINT "ImageRecord_knowledgeCardId_fkey" FOREIGN KEY ("knowledgeCardId") REFERENCES "KnowledgeCard"("id") ON DELETE CASCADE ON UPDATE CASCADE;
