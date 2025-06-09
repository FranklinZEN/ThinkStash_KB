/*
  Warnings:

  - You are about to drop the `AITask` table. If the table is not empty, all the data it contains will be lost.

*/
-- DropTable
DROP TABLE "AITask";

-- CreateTable
CREATE TABLE "ai_task" (
    "id" TEXT NOT NULL,
    "user_id" TEXT,
    "task_type" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "progress_stage" TEXT,
    "input_data" JSONB,
    "result_data" JSONB,
    "error_message" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ai_task_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ai_task_status_idx" ON "ai_task"("status");

-- CreateIndex
CREATE INDEX "ai_task_user_id_idx" ON "ai_task"("user_id");
