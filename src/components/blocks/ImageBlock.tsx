import React from 'react';
// Make sure this path is correct for your schema definition
import { customSchema } from "@/lib/editor/blocks"; 
import { BlockNoteEditor as BEM, Block } from "@blocknote/core";
import { Image, Button, Input, VStack, Text } from "@chakra-ui/react"; // Or your preferred UI components

// Define the type for the image block based on your custom schema
type CustomImageBlock = Block<typeof customSchema.image.type, typeof customSchema.image.props>;

interface ImageBlockProps {
  block: CustomImageBlock;
  editor: BEM<typeof customSchema>; // Pass the editor instance
}

const ImageBlock = ({ block, editor }: ImageBlockProps) => {
  const { props } = block;
  const imageSrc = props.url;
  const captionText = props.caption || "";
  const altText = props.alt || "";
  const gcsPath = props.gcsPath || "";
  const contentType = props.contentType || "";

  // For this test, we'll have a button to manually trigger updateBlock
  const handleTestUpdateProps = () => {
    if (!editor) {
      console.error("Editor instance not available in ImageBlock");
      return;
    }

    const testProps = {
      url: "/api/images/test/user/sample-updated-image.png", // Example final URL
      caption: "Updated caption from ImageBlock",
      alt: "Updated alt text from ImageBlock",
      gcsPath: "test/user/sample-updated-image.png",
      contentType: "image/png",
      // Ensure any other props defined in your schema (even with defaults) are here
      // e.g., if you had 'alignment', 'width', etc.
    };

    console.log("[ImageBlock.tsx] Attempting to update block with testProps:", testProps);
    editor.updateBlock(block, {
      props: testProps,
    });
    console.log("[ImageBlock.tsx] updateBlock called. Check editor content.");
  };
  
  // A simple input for editing caption, to see if that also works via updateBlock
  const handleCaptionChange = (newCaption: string) => {
    editor.updateBlock(block, {
      props: { ...props, caption: newCaption },
    });
  };

  return (
    <VStack 
      alignItems="stretch" 
      spacing={2} 
      style={{ padding: '8px', border: '1px solid #eee', borderRadius: '4px', background: '#f9f9f9' }}
    >
      {imageSrc ? (
        <Image 
          src={imageSrc} 
          alt={altText || captionText || 'Uploaded image'} 
          style={{ maxWidth: '100%', maxHeight: '400px', objectFit: 'contain' }}
        />
      ) : (
        <Text color="gray.500">No image URL</Text>
      )}
      
      <Input 
        value={captionText}
        onChange={(e) => handleCaptionChange(e.target.value)}
        placeholder="Enter caption"
        size="sm"
      />
      
      <Text fontSize="xs" color="gray.600">Alt: {altText || "(not set)"}</Text>
      <Text fontSize="xs" color="gray.600">GCS Path: {gcsPath || "(not set)"}</Text>
      <Text fontSize="xs" color="gray.600">Content Type: {contentType || "(not set)"}</Text>
      <Text fontSize="xs" color="gray.600">URL: {imageSrc || "(not set)"}</Text>

      <Button onClick={handleTestUpdateProps} colorScheme="teal" size="sm" mt={2}>
        Test Update All Props
      </Button>
      <Text fontSize="xs" color="gray.500" mt={1}>
        Clicking "Test Update All Props" will attempt to set url, caption, alt, gcsPath, and contentType.
      </Text>
    </VStack>
  );
};

export default ImageBlock;
