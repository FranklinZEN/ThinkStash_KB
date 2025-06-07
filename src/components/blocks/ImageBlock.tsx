import { Block } from '@blocknote/core';
import { useBlockNote } from '@blocknote/react';
import { Box, Button, Image, useToast } from '@chakra-ui/react';
import { useCallback } from 'react';
import { Resizable } from 're-resizable';

interface ImageBlockProps {
  block: Block<{ width?: number | string }>;
}

export function ImageBlock({ block }: ImageBlockProps) {
  const toast = useToast();
  const { editor } = useBlockNote();

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
        editor.updateBlock(block, {
          type: 'image',
          props: {
            url: data.url,
            caption: file.name,
            width: '100%', // Default width on upload
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
  }, [block, editor, toast]);

  // If the block is an image block and has a URL, display it
  if (block.type === 'image' && block.props.url) {
    return (
      <Box position="relative" contentEditable={false}>
        <Resizable
          defaultSize={{
            width: block.props.width || '100%',
            height: 'auto',
          }}
          onResizeStop={(e, direction, ref, d) => {
            const newWidth = ref.style.width;
            editor.updateBlock(block, {
              props: { width: newWidth },
            });
          }}
          enable={{
            top: false,
            right: true,
            bottom: false,
            left: true,
            topRight: false,
            bottomRight: true,
            bottomLeft: true,
            topLeft: false,
          }}
          handleStyles={{
            right: {
              width: '10px',
              right: '-5px',
              height: '100%',
              cursor: 'col-resize',
              backgroundColor: 'rgba(0, 123, 255, 0.5)',
              borderRadius: '5px',
            },
            left: {
              width: '10px',
              left: '-5px',
              height: '100%',
              cursor: 'col-resize',
              backgroundColor: 'rgba(0, 123, 255, 0.5)',
              borderRadius: '5px',
            },
            bottomRight: {
              width: '20px',
              height: '20px',
              right: '-10px',
              bottom: '-10px',
              cursor: 'nwse-resize',
              backgroundColor: 'rgba(0, 123, 255, 0.5)',
              borderRadius: '50%',
              border: '2px solid white',
            },
            bottomLeft: {
              width: '20px',
              height: '20px',
              left: '-10px',
              bottom: '-10px',
              cursor: 'nesw-resize',
              backgroundColor: 'rgba(0, 123, 255, 0.5)',
              borderRadius: '50%',
              border: '2px solid white',
            },
          }}
        >
          <Image
            src={block.props.url}
            alt={block.props.caption || 'Uploaded image'}
            width="100%"
            height="100%"
            objectFit="contain"
          />
        </Resizable>
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
        contentEditable={false}
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
