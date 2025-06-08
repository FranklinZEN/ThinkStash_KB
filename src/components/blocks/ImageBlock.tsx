import { Block } from '@blocknote/core';
import { useBlockNote } from '@blocknote/react';
import { Box, Button, Image, useToast } from '@chakra-ui/react';
import { useCallback } from 'react';

interface ImageBlockProps {
  block: Block;
}

export function ImageBlock({ block }: ImageBlockProps) {
  const toast = useToast();
  const { updateBlock } = useBlockNote();

  const handleImageUpload = useCallback(async () => {
    try {
      // Create a file input element
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';

      input.onchange = async (e) => {
        const file = (e.target as HTMLInputElement).files?.[0];
        if (!file) return;

        // Create form data
        const formData = new FormData();
        formData.append('file', file);

        // Upload to our API
        const response = await fetch('/api/upload/image', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error('Failed to upload image');
        }

        const data = await response.json();

        // Update the block with the image URL
        updateBlock(block, {
          type: 'image',
          props: {
            url: data.url,
            caption: file.name,
          },
        });
      };

      input.click();
    } catch (error) {
      console.error('Error uploading image:', error);
      toast({
        title: 'Error',
        description: 'Failed to upload image',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [block, toast, updateBlock]);

  // If the block is an image block and has a URL, display it
  if (block.type === 'image' && block.props.url) {
    return (
      <Box position="relative" width="100%" maxWidth="800px" margin="0 auto">
        <Image
          src={block.props.url}
          alt={block.props.caption || 'Uploaded image'}
          width="100%"
          height="auto"
          objectFit="contain"
        />
      </Box>
    );
  }

  // Otherwise, show the upload button, also ensuring it's an image block.
  if (block.type === 'image') {
    return (
      <Box
        border="2px dashed"
        borderColor="gray.200"
        borderRadius="md"
        p={4}
        textAlign="center"
      >
        <Button onClick={handleImageUpload} colorScheme="blue">
          Upload Image
        </Button>
      </Box>
    );
  }

  // Fallback for when the block is not an image type or if further logic is needed.
  // console.warn("ImageBlock rendered with a non-image block or an unhandled case:", block);
  return null;
}
