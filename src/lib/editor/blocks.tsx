import {
  BlockNoteSchema,
  defaultBlockSpecs,
  defaultStyleSpecs,
  defaultInlineContentSpecs,
  type BlockConfig,
  type BlockSchemaFromSpecs // Import BlockSchemaFromSpecs
  // Removed BlockSpecs, BlockNoteSchemaTyped as they might be implicitly handled or unused now
} from '@blocknote/core';

// Import your custom ImageBlock component using path alias
import ImageBlock from '@/components/blocks/ImageBlock';

// Define the props for your custom image block
export const customImageProps = {
  ...defaultBlockSpecs.image.config.propSchema, // Corrected to config.propSchema
  url: { default: "" as const },      // Ensure all defaults from base spec are covered or redefined
  caption: { default: "" as const },
  alt: { default: "" as const },
  'data-gcs-path': { default: "" as const }, // Reverted to hyphenated
  contentType: { default: "" as const }, // Stays camelCase as it's fully custom
  'data-app-served-url': { default: "" as const }, // Reverted to hyphenated
};

// 1. Build blockConfigs from defaultBlockSpecs with safety check
const blockConfigs: Record<string, BlockConfig> = {};
for (const [key, spec] of Object.entries(defaultBlockSpecs)) {
  if (spec.config) { 
    blockConfigs[key] = spec.config;
  } else {
    console.warn(`[BlockNote Schema] Default spec for '${key}' is missing a .config property.`);
    // Optionally provide a minimal fallback or skip
  }
}

// 2. Define your custom image config with safety checks
let customImageConfig: BlockConfig;
const defaultImageConfigRef = defaultBlockSpecs.image?.config;

if (defaultImageConfigRef) {
  customImageConfig = {
    type: "image", 
    propSchema: customImageProps,
    content: defaultImageConfigRef.content || "none", 
    styleSchema: defaultImageConfigRef.styleSchema, 
    ...(defaultImageConfigRef.allowsBlocks !== undefined && { allowsBlocks: defaultImageConfigRef.allowsBlocks }),
    ...(defaultImageConfigRef.childPlaceholder !== undefined && { childPlaceholder: defaultImageConfigRef.childPlaceholder }),
  };
} else {
  console.error("[BlockNote Schema] Default image block config not found! Cannot create custom image config properly.");
  customImageConfig = {
    type: "image",
    propSchema: customImageProps,
    content: "none",
  };
}

// Add/override the image config in blockConfigs
if (blockConfigs.image || defaultImageConfigRef) { // Only override if default image config existed or image key already in blockConfigs
    blockConfigs.image = customImageConfig;
} else {
    // If defaultBlockSpecs didn't even have an 'image' (highly unlikely), add it.
    // But this case should ideally be handled by the loop above if defaultBlockSpecs.image was missing a .config
    console.warn("[BlockNote Schema] Default image spec was entirely missing. Adding custom image config.");
    blockConfigs.image = customImageConfig; 
}

// Explicitly define the type of the processed block schema
export type CustomBlockSchemaInternal = BlockSchemaFromSpecs<typeof blockConfigs, typeof defaultInlineContentSpecs, typeof defaultStyleSpecs>;

// Type customSchema using this explicit internal schema type
export const customSchema = BlockNoteSchema.create({ // Let type be inferred as it was before this runtime error
  blockSpecs: blockConfigs, 
  inlineContentSpecs: defaultInlineContentSpecs,
  styleSpecs: defaultStyleSpecs,
});

// Export schema-derived types
// export type CustomBlockNoteEditor = typeof customSchema.BlockNoteEditor;
// export type CustomBlock = typeof customSchema.Block;
// export type CustomPartialBlock = typeof customSchema.PartialBlock;
// Potentially also: CustomInlineContent, CustomStyle if needed elsewhere

// Provide custom components (for rendering)
export const customBlockComponents = {
  image: ImageBlock,
};

// Old definitions - can be removed if no longer used elsewhere
// export const customImageSpec = {
//   ...defaultBlockSpecs.image, 
//   props: customImageProps,    
// };
// export const editorBlockSpecs: BlockSpecs = {
//   ...defaultBlockSpecs,
//   image: customImageSpec,
// };
