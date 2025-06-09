/*
  Warnings:

  - You are about to drop the column `createdAt` on the `AITask` table. All the data in the column will be lost.
  - You are about to drop the column `errorMessage` on the `AITask` table. All the data in the column will be lost.
  - You are about to drop the column `inputData` on the `AITask` table. All the data in the column will be lost.
  - You are about to drop the column `progressStage` on the `AITask` table. All the data in the column will be lost.
  - You are about to drop the column `resultData` on the `AITask` table. All the data in the column will be lost.
  - You are about to drop the column `taskType` on the `AITask` table. All the data in the column will be lost.
  - You are about to drop the column `updatedAt` on the `AITask` table. All the data in the column will be lost.
  - You are about to drop the column `userId` on the `AITask` table. All the data in the column will be lost.
  - A unique constraint covering the columns `[correlation_id]` on the table `AITask` will be added. If there are existing duplicate values, this will fail.
  - Added the required column `task_type` to the `AITask` table without a default value. This is not possible if the table is not empty.
  - Added the required column `updated_at` to the `AITask` table without a default value. This is not possible if the table is not empty.

*/
-- DropIndex
DROP INDEX "AITask_userId_idx";

-- AlterTable
ALTER TABLE "AITask" DROP COLUMN "createdAt",
DROP COLUMN "errorMessage",
DROP COLUMN "inputData",
DROP COLUMN "progressStage",
DROP COLUMN "resultData",
DROP COLUMN "taskType",
DROP COLUMN "updatedAt",
DROP COLUMN "userId",
ADD COLUMN     "correlation_id" TEXT,
ADD COLUMN     "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "error_message" TEXT,
ADD COLUMN     "input_data" JSONB,
ADD COLUMN     "progress_stage" TEXT,
ADD COLUMN     "result_data" JSONB,
ADD COLUMN     "task_type" TEXT NOT NULL,
ADD COLUMN     "updated_at" TIMESTAMP(3) NOT NULL,
ADD COLUMN     "user_id" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX "AITask_correlation_id_key" ON "AITask"("correlation_id");

-- CreateIndex
CREATE INDEX "AITask_user_id_idx" ON "AITask"("user_id");
