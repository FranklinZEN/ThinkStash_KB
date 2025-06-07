import {
  // type BlockNoteEditor, // Removed
  type Block,
  // type PartialBlock, // Assuming this might not be needed here based on current usage
  // type InlineContent,
  // type StyleSchema,
  // type DefaultBlockSchema // No longer needed if Block is not generic here
} from "@blocknote/core";

// 1. MyAppImageBlockProps: Defines the minimal shape of props we want to persist for image blocks.
export interface MyAppImageBlockProps {
  url: string;
  caption?: string;
}

// If Block is now globally augmented to be AppBlock, then StandardBlock is simply Block.
export type StandardBlock = Block;
export type StandardDocument = StandardBlock[];

// MyAppTransformedImageBlock: Represents an image block after server-side transformation.
// It ensures it's an image type from StandardBlock and overrides its props with our minimal set.
export type MyAppTransformedImageBlock = Omit<
  StandardBlock & { type: 'image' },
  'props'
> & {
  props: MyAppImageBlockProps;
};

// Type guard to check if a block is an image block.
export function isImageBlock(
  block: StandardBlock,
): block is StandardBlock & { type: 'image' } {
  return block.type === 'image';
}
