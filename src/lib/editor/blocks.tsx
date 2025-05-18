import {
  BlockNoteSchema,
  defaultBlockSpecs,
  defaultStyleSpecs,
  // createReactBlockSpec, // No longer using this directly for this test
} from '@blocknote/core';

// Import your custom ImageBlock component using path alias
import ImageBlock from '@/components/blocks/ImageBlock';

// Define the props for your custom image block
const customImageProps = {
  ...defaultBlockSpecs.image.props, // Start with default image props
  url: { default: "" as const },      // Ensure all defaults from base spec are covered or redefined
  caption: { default: "" as const },
  alt: { default: "" as const },
  gcsPath: { default: "" as const }, // For storing the GCS path
  contentType: { default: "" as const },
  appServedUrl: { default: "" as const }, // CHANGED from 'data-app-served-url'
  // Add any other props your ImageBlock or schema expects, e.g.:
  // uploadInProgress: { default: false as const },
  // 'data-gcs-path': { default: "" as const }, // This was redundant and commented out
};

// Alternative way to define the custom image spec without createReactBlockSpec
const customImageSpec = {
  ...defaultBlockSpecs.image, // Spread default image spec to get its type, content handling etc.
  props: customImageProps,     // Override with your custom props definition
  component: ImageBlock,       // Assign your custom React component for rendering
};

// Create the custom schema
export const customSchema = BlockNoteSchema.create({
  blockSpecs: {
    ...defaultBlockSpecs,
    image: customImageSpec as any, // Using 'as any' to bypass strict type checking if needed for this direct approach
                                 // BlockNote types can be complex. Ideally, this would type-check correctly.
  },
  styleSpecs: defaultStyleSpecs,
});

// You might not need customBlockComponents if component is defined in spec
// export const customBlockComponents = {
//   image: ImageBlock, // This would be an alternative way if not using component in createReactBlockSpec
// };
