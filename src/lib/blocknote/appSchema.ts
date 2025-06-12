"use client";

import {
  BlockNoteSchema,
  defaultBlockSpecs,
  defaultInlineContentSpecs, // Explicitly include if you want to be clear or customize
  defaultStyleSpecs,       // Explicitly include if you want to be clear or customize
  type InlineContent as CoreInlineContent, // Import the core generic type
} from "@blocknote/core";

/**
 * Our application's BlockNote schema.
 * This instance holds all the block, inline content, and style configurations.
 */
export const appSchema = BlockNoteSchema.create({
  blockSpecs: defaultBlockSpecs, // Use defaults directly
  // Add any custom block specs here if you have them
  // e.g., alert: MyCustomAlertBlockSpec,
  inlineContentSpecs: defaultInlineContentSpecs, // Using defaults
  styleSpecs: defaultStyleSpecs,                 // Using defaults
});

/*
 * Export the schema-specific types directly from the appSchema instance.
 * BlockNote automatically creates these specialized types on the schema object.
 * This is the preferred way as per BlockNote's documentation for "Manual typing of types".
 */

/** Represents the BlockNote editor instance typed to our specific appSchema. */
export type AppEditor = typeof appSchema.BlockNoteEditor;

/** Represents a complete Block, typed to our appSchema. (e.g., from editor.topLevelBlocks) */
export type AppBlock = typeof appSchema.Block;

/**
 * Represents a PartialBlock, typed to our appSchema.
 * Useful for initial content, editor.document, and serialization.
 */
export type AppPartialBlock = typeof appSchema.PartialBlock;

/**
 * Represents a single InlineContent item (e.g., a text span, a link), typed to our appSchema.
 */
export type AppInlineContent = CoreInlineContent<
  typeof appSchema.inlineContentSchema,
  typeof appSchema.styleSchema
>;

/**
 * Represents an array of InlineContent items, commonly found in block.content.
 * BlockNote often uses ReadonlyArray for these.
 */
export type AppInlineContentArray = ReadonlyArray<AppInlineContent>; 