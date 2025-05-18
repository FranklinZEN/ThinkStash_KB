import React from 'react';
import { customSchema } from "@/lib/editor/blocks"; // Import customSchema
import { BlockNoteEditor, Block } from "@blocknote/core"; // Import core types
import { Image, Button, Input, VStack, Text } from "@chakra-ui/react"; 

type CustomImageBlockType = Block<typeof customSchema, "image">;

interface ImageBlockProps {
  block: CustomImageBlockType;
  editor: BlockNoteEditor<typeof customSchema>; // Use core type with customSchema
}

const ImageBlock = ({ block, editor }: ImageBlockProps) => {
  const { props } = block; 
  const imageSrc = props.url;
  const captionText = props.caption || "";
  const altText = props.alt || "";
  const gcsPath = props['data-gcs-path'] || ""; 
  const contentType = props.contentType || ""; 

  const handleTestUpdateProps = () => {
    if (!editor) {
      console.error("Editor instance not available in ImageBlock");
      return;
    }
    const currentProps = block.props;
    const testProps = {
      ...currentProps, 
      url: "/api/images/test/user/sample-updated-image.png", 
      caption: "Updated caption from ImageBlock",
      alt: "Updated alt text from ImageBlock",
      'data-gcs-path': "test/user/sample-updated-image.png", 
      contentType: "image/png",
      'data-app-served-url': "/api/images/test/user/sample-updated-image.png", 
    };
    editor.updateBlock(block, {
      props: testProps as Partial<CustomImageBlockType['props']>, 
    });
  };
  
  const handleCaptionChange = (newCaption: string) => {
    editor.updateBlock(block, {
      props: { ...block.props, caption: newCaption }, 
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
        Clicking &quot;Test Update All Props&quot; will attempt to set url, caption, alt, gcsPath, and contentType.
      </Text>
    </VStack>
  );
};

export default ImageBlock;
