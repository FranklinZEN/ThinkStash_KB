import { z } from "zod";

import { ActionState } from "@/lib/create-safe-action";

import { GenerateTitle } from "./schema";

export type InputType = z.infer<typeof GenerateTitle>;
export type ReturnType = ActionState<InputType, { taskId: string }>; 