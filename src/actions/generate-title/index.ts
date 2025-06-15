import { z } from "zod";

import { db } from "@/lib/db";
import { revalidatePath } from "next/cache";

import { createSafeAction } from "@/lib/create-safe-action";

import { GenerateTitle } from "./schema";
import { InputType, ReturnType } from "./types";

// The TaskStatus enum from the backend
enum TaskStatus {
  PENDING = "PENDING",
  PROCESSING = "PROCESSING",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
}

const handler = async (data: InputType): Promise<ReturnType> => {
  const { cardId } = data;
  let task;

  if (!cardId) {
    return {
      error: "Card ID is required",
    };
  }

  try {
    task = await db.task.create({
      data: {
        type: "GENERATE_TITLE",
        status: TaskStatus.PENDING,
        payload: {
          card_id: cardId,
        },
      },
    });

  } catch (error) {
    return {
      error: "Failed to start title generation task."
    }
  }

  revalidatePath(`/cards/${cardId}`);
  return { data: { taskId: task.id } };
};

export const generateTitle = createSafeAction(GenerateTitle, handler); 