import { type appSchema } from "./lib/blocknote/appSchema"; // Adjusted import

declare module "@blocknote/core" {
  // Re-export the schema-specific helpers from your appSchema
  // to effectively override/shadow the default generic types from @blocknote/core.
  export type BlockNoteEditor = typeof appSchema.BlockNoteEditor;
  export type Block = typeof appSchema.Block;
  export type PartialBlock = typeof appSchema.PartialBlock;
  // export type InlineContent = AppInlineContent; // Commented out again to avoid circular issues
                                                 // Consumers should import AppInlineContent directly from appSchema.ts
  // You might need to re-export other types if you use them generically,
  // e.g., TableContent, StyleSchema, etc., if appSchema customizes them.
  // For now, these cover the main ones from the plan.
} 