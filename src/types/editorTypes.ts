import { Block, DefaultBlockSchema } from '@blocknote/core';

// 1. MyAppImageBlockProps: Defines the minimal shape of props we want to persist for image blocks.
export interface MyAppImageBlockProps {
  url: string;
  caption?: string;
}

// 2. Use BlockNote's DefaultBlockSchema for general document/block typing internally.
export type StandardBlock = Block<DefaultBlockSchema>;
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
