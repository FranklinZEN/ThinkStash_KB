'use client';

import React, { useState, FormEvent, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  Spinner,
  useToast,
  Flex,
  Text,
  Container,
  HStack,
  Tag,
  TagLabel,
  TagCloseButton,
} from '@chakra-ui/react';
import {
  BlockNoteEditor as BlockNoteEditorType,
  PartialBlock,
} from '@blocknote/core';

// Helper function to check if editor content is effectively empty
const isEditorEmpty = (blocks: PartialBlock[] | undefined): boolean => {
  if (!blocks || blocks.length === 0) return true;
  if (blocks.length === 1) {
    const block = blocks[0];
    if (block.type === 'paragraph') {
      if (
        !block.content ||
        (Array.isArray(block.content) && block.content.length === 0)
      )
        return true;
      if (typeof block.content === 'string' && block.content.trim() === '')
        return true;

      if (Array.isArray(block.content)) {
        return block.content.every((inlineItem) => {
          if (typeof inlineItem === 'string') {
            return inlineItem.trim() === '';
          }

          if (
            typeof inlineItem === 'object' &&
            inlineItem !== null &&
            'type' in inlineItem
          ) {
            const itemWithType = inlineItem as {
              type: string;
              [key: string]: unknown;
            };

            if (itemWithType.type === 'text') {
              const text =
                typeof itemWithType.text === 'string' ? itemWithType.text : '';
              const styles =
                typeof itemWithType.styles === 'object' &&
                itemWithType.styles !== null
                  ? itemWithType.styles
                  : {};
              return text.trim() === '' && Object.keys(styles).length === 0;
            }
            if (itemWithType.type === 'link') {
              const linkContent = Array.isArray(itemWithType.content)
                ? itemWithType.content
                : [];
              return linkContent.every((linkChild) => {
                if (typeof linkChild === 'string')
                  return linkChild.trim() === '';
                if (
                  typeof linkChild === 'object' &&
                  linkChild !== null &&
                  'type' in linkChild
                ) {
                  const childWithType = linkChild as {
                    type: string;
                    [key: string]: unknown;
                  };
                  if (childWithType.type === 'text') {
                    const text =
                      typeof childWithType.text === 'string'
                        ? childWithType.text
                        : '';
                    const styles =
                      typeof childWithType.styles === 'object' &&
                      childWithType.styles !== null
                        ? childWithType.styles
                        : {};
                    return (
                      text.trim() === '' && Object.keys(styles).length === 0
                    );
                  }
                }
                return false;
              });
            }
            return false;
          }
          return false;
        });
      }
    }
  }
  return false;
};

const BlockNoteEditorComponent = dynamic(
  () => import('@/components/BlockNoteEditorComponent'),
  {
    ssr: false,
    loading: () => (
      <Flex justify="center" align="center" minH="200px">
        <Spinner />
        <Text ml={3}>Loading Editor...</Text>
      </Flex>
    ),
  },
);

interface CreateCardSuccessResponse {
  id: string;
}

interface CreateCardErrorResponse {
  error?: string;
  message?: string;
  details?: { [key: string]: string[] };
}

export default function NewCardPage() {
  const { status } = useSession();
  const router = useRouter();
  const toast = useToast();

  const [title, setTitle] = useState('');
  const [_editor, setEditor] = useState<BlockNoteEditorType | null>(null);
  const [editorContent, setEditorContent] = useState<
    PartialBlock[] | undefined
  >(undefined);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [currentKeyword, setCurrentKeyword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleEditorInstanceReady = useCallback(
    (editorInstance: BlockNoteEditorType | null) => {
      setEditor(editorInstance);
    },
    [],
  );

  const handleEditorContentUpdate = useCallback((blocks: PartialBlock[]) => {
    setEditorContent(blocks);
  }, []);

  const handleKeywordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentKeyword(e.target.value);
  };

  const handleKeywordKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && currentKeyword.trim() !== '') {
      e.preventDefault();
      const newKeyword = currentKeyword.trim().startsWith('#')
        ? currentKeyword.trim()
        : `#${currentKeyword.trim()}`;
      if (!keywords.includes(newKeyword)) {
        setKeywords([...keywords, newKeyword]);
      }
      setCurrentKeyword('');
    }
  };

  const removeKeyword = (keywordToRemove: string) => {
    setKeywords(keywords.filter((keyword) => keyword !== keywordToRemove));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);

    // Get current content directly from editor instance if available
    const currentBlocks = _editor ? _editor.document : editorContent;

    if (!title.trim()) {
      toast({
        title: 'Title is required',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    // Check for empty content using currentBlocks from editor instance
    if (isEditorEmpty(currentBlocks)) {
      toast({
        title: 'Content cannot be empty',
        description: 'Please add some content to your card.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    const cardData = {
      title: title.trim(),
      content: currentBlocks || [], // Use currentBlocks from editor instance
      tags: keywords.map((kw) => (kw.startsWith('#') ? kw.substring(1) : kw)),
      folderId: null,
    };

    console.log('Creating card with data (content stringified):', {
      ...cardData,
      content: JSON.stringify(cardData.content),
    });

    try {
      const response = await fetch('/api/cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cardData),
      });

      const responseData = (await response.json()) as
        | CreateCardSuccessResponse
        | CreateCardErrorResponse;
      console.log('API response for new card:', responseData);

      if (response.ok && (responseData as CreateCardSuccessResponse).id) {
        toast({
          title: 'Card created successfully!',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        router.push(`/cards/${(responseData as CreateCardSuccessResponse).id}`);
      } else {
        const errorResponse = responseData as CreateCardErrorResponse;
        if (errorResponse.details) {
          console.error('Validation Details:', errorResponse.details);
        }
        const errorMsg =
          errorResponse.error ||
          errorResponse.message ||
          (errorResponse.details
            ? JSON.stringify(errorResponse.details)
            : 'Failed to create card');
        throw new Error(errorMsg);
      }
    } catch (error: unknown) {
      console.error('Create card error:', error);
      const message =
        error instanceof Error
          ? error.message
          : 'An unexpected error occurred.';
      toast({
        title: 'Error creating card',
        description: message,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (status === 'loading') {
    return (
      <Flex justify="center" align="center" height="80vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
    router.push('/api/auth/signin?callbackUrl=/cards/new');
    return null;
  }

  return (
    <Container maxW="container.lg" py={8}>
      <Heading as="h1" size="xl" mb={6} textAlign="center">
        Create New Knowledge Card
      </Heading>
      <Box as="form" onSubmit={handleSubmit}>
        <VStack spacing={6} align="stretch">
          <FormControl isRequired>
            <FormLabel>Title</FormLabel>
            <Input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter card title"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Key Words (Optional)</FormLabel>
            <Input
              type="text"
              value={currentKeyword}
              onChange={handleKeywordChange}
              onKeyDown={handleKeywordKeyDown}
              placeholder="Type a keyword and press Enter"
            />
            <HStack spacing={2} mt={3} flexWrap="wrap">
              {keywords.map((keyword) => (
                <Tag
                  size="lg"
                  key={keyword}
                  borderRadius="md"
                  variant="solid"
                  colorScheme="blue"
                >
                  <TagLabel>{keyword}</TagLabel>
                  <TagCloseButton onClick={() => removeKeyword(keyword)} />
                </Tag>
              ))}
            </HStack>
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Content</FormLabel>
            <Box borderWidth="1px" borderRadius="md" p={0} minH="300px">
              <BlockNoteEditorComponent
                onEditorChange={handleEditorInstanceReady}
                onContentUpdate={handleEditorContentUpdate}
                editable={true}
                initialContent={undefined}
              />
            </Box>
          </FormControl>

          <Button
            type="submit"
            colorScheme="green"
            isLoading={isSubmitting}
            size="lg"
            fontSize="md"
          >
            Create Card
          </Button>
        </VStack>
      </Box>
    </Container>
  );
}
