import { z } from "zod";

export const GenerateTitle = z.object({
  cardId: z.string(),
}); 