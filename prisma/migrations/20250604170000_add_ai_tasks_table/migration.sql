-- CreateTable
CREATE TABLE "AITask" (
    "id" TEXT NOT NULL,
    "userId" TEXT,
    "taskType" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "inputData" JSONB,
    "resultData" JSONB,
    "errorMessage" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "AITask_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "AITask_status_idx" ON "AITask"("status");

-- CreateIndex
CREATE INDEX "AITask_userId_idx" ON "AITask"("userId");
