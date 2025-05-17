'use client';

import React, { useState, FormEvent, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
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
import { BlockNoteEditor as BlockNoteEditorComponent } from '@/components/editor/BlockNoteEditor';
import {
  BlockNoteEditor as BlockNoteEditorType,
  PartialBlock,
} from '@blocknote/core';

interface ErrorResponse {
  message?: string;
}

export default function NewCardPage() {
  const { status } = useSession();
  const router = useRouter();
  const toast = useToast();

  const [title, setTitle] = useState('');
  const [keywords, setKeywords] = useState<string[]>([]);
  const [currentKeyword, setCurrentKeyword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  // State to hold the editor instance received from the child component
  const [editor, setEditor] = useState<BlockNoteEditorType | null>(null);
  // Define state for the editor content
  const [editorContent, setEditorContent] = useState<
    PartialBlock[] | undefined
  >(undefined);

  // Callback to receive the editor instance from the child
  const handleEditorInstanceReady = useCallback(
    (editorInstance: BlockNoteEditorType | null) => {
      setEditor(editorInstance);
    },
    [],
  );

  const handleKeywordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentKeyword(e.target.value);
  };

  const handleKeywordKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && currentKeyword.trim() !== '') {
      e.preventDefault();
      // Add '#' prefix if not already present, and ensure uniqueness
      const newKeyword = currentKeyword.trim().startsWith('#')
        ? currentKeyword.trim()
        : `#${currentKeyword.trim()}`;
      if (!keywords.includes(newKeyword)) {
        setKeywords([...keywords, newKeyword]);
      }
      setCurrentKeyword(''); // Clear input
    }
  };

  const removeKeyword = (keywordToRemove: string) => {
    setKeywords(keywords.filter((keyword) => keyword !== keywordToRemove));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    // Check the editor state received from the child
    if (!editor) {
      toast({
        title: 'Editor not ready or failed to load',
        status: 'error',
        duration: 3000,
      });
      return;
    }
    if (!title.trim() || !editorContent) {
      toast({
        title: 'Title and content are required',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    setIsSubmitting(true);

    // Get content from the editor instance we have in state
    // const content = editor.document; // Removed unused variable

    try {
      console.log('Creating card with keywords:', keywords);
      const response = await fetch('/api/cards', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: title.trim(),
          content: editorContent,
          tags: keywords,
        }),
      });

      const newCard = await response.json();
      console.log('API response for new card:', newCard); // Log API response

      if (response.ok) {
        toast({
          title: 'Card created successfully.',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        router.push('/');
        router.refresh();
      } else {
        // Use newCard.message if available, otherwise a default message
        const serverError =
          (newCard as ErrorResponse)?.message || 'Failed to create card.';
        throw new Error(serverError);
      }
    } catch (error: unknown) {
      console.error('Create card error:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Could not save the card.';
      toast({
        title: 'Error creating card.',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle loading and unauthenticated states
  if (status === 'loading') {
    return (
      <Flex justify="center" align="center" height="80vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
    router.push('/api/auth/signin?callbackUrl=/cards/new');
    return (
      <Flex justify="center" align="center" height="80vh">
        <Text>Redirecting to sign in...</Text>
      </Flex>
    );
  }

  return (
    <Container maxW="container.lg" py={8} fontFamily="'Open Sans', sans-serif">
      <Heading
        as="h1"
        size="xl"
        mb={6}
        fontFamily="'Open Sans', sans-serif"
        fontSize="36px"
      >
        Create New Knowledge Card
      </Heading>
      <Box as="form" onSubmit={handleSubmit}>
        <VStack spacing={6} align="stretch">
          <FormControl isRequired>
            <FormLabel fontFamily="'Open Sans', sans-serif" fontSize="24px">
              Title
            </FormLabel>
            <Input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter card title"
              isDisabled={isSubmitting}
              fontFamily="'Open Sans', sans-serif"
              fontSize="16px"
            />
          </FormControl>

          {/* Key Words Section - Moved here */}
          <FormControl>
            <FormLabel fontFamily="'Open Sans', sans-serif" fontSize="24px">
              Key Words{' '}
              <Text as="span" fontSize="16px" color="gray.500">
                (Optional)
              </Text>
            </FormLabel>
            <Input
              type="text"
              value={currentKeyword}
              onChange={handleKeywordChange}
              onKeyDown={handleKeywordKeyDown}
              placeholder="Type a keyword and press Enter"
              isDisabled={isSubmitting}
              fontFamily="'Open Sans', sans-serif"
              fontSize="16px"
              color="#A1824A"
              _placeholder={{ color: '#A1824A' }}
            />
            <HStack spacing={2} mt={3} flexWrap="wrap">
              {keywords.map((keyword) => (
                <Tag
                  size="lg"
                  key={keyword}
                  borderRadius="md"
                  variant="solid"
                  colorScheme="blue"
                  boxShadow="md"
                  sx={{
                    boxShadow:
                      '2px 2px 5px rgba(0,0,0,0.2), inset 1px 1px 2px rgba(255,255,255,0.3)',
                    border: '1px solid rgba(0,0,0,0.1)',
                  }}
                >
                  <TagLabel>{keyword}</TagLabel>
                  <TagCloseButton onClick={() => removeKeyword(keyword)} />
                </Tag>
              ))}
            </HStack>
          </FormControl>

          <FormControl isRequired>
            <FormLabel fontFamily="'Open Sans', sans-serif" fontSize="24px">
              Content
            </FormLabel>
            {/* Use the custom BlockNoteEditor with toolbar */}
            <BlockNoteEditorComponent
              initialContent={editorContent}
              onChange={setEditorContent}
              onEditorReady={handleEditorInstanceReady}
              readOnly={false}
            />
          </FormControl>

          {/* Buttons */}
          <Flex justify="flex-start" gap={3} mt={4}>
            {' '}
            {/* Use Flex for horizontal alignment and gap */}
            <Button
              colorScheme="green"
              type="submit"
              isLoading={isSubmitting}
              fontFamily="'Open Sans', sans-serif"
              fontSize="16px"
            >
              Create Card
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push('/')}
              isDisabled={isSubmitting}
              fontFamily="'Open Sans', sans-serif"
              fontSize="16px"
            >
              Cancel
            </Button>
          </Flex>
        </VStack>
      </Box>
    </Container>
  );
}
