import {
  BlockNoteSchema,
  defaultBlockSpecs,
  defaultStyleSpecs,
} from '@blocknote/core';
// import { ImageBlock } from '@/components/blocks/ImageBlock';

// No custom imageBlockSpec here; we'll rely on defaultBlockSpecs.image
// and override rendering with customBlockComponents.

// Custom font styles removed for stability.

export const customSchema = BlockNoteSchema.create({
  blockSpecs: {
    ...defaultBlockSpecs, // This includes BlockNote's own 'image' spec
  },
  styleSpecs: {
    ...defaultStyleSpecs, // Use only default styles
  },
});

// This maps the block *type* (string) to your React component.
// We are overriding the rendering for the default 'image' block type.
export const customBlockComponents = {
  // image: ImageBlock,
};

// The React import is no longer needed if we are not defining React components here.
// import React from 'react'; // Commented out or removed
