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
} from '@chakra-ui/react';
import dynamic from 'next/dynamic'; // Import dynamic
import { BlockNoteEditor } from "@blocknote/core"; // Keep type import

// Dynamically import the editor component with SSR disabled
const BlockNoteEditorComponent = dynamic(
  () => import('@/components/BlockNoteEditorComponent'),
  {
    ssr: false,
    // Optional: Add a loading component specific to the editor area
    loading: () => (
      <Flex justify="center" align="center" minH="300px">
        <Spinner />
        <Text ml={3}>Loading Editor Component...</Text>
      </Flex>
    ),
  }
);

export default function NewCardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const toast = useToast();

  const [title, setTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  // State to hold the editor instance received from the child component
  const [editor, setEditor] = useState<BlockNoteEditor | null>(null);

  // Callback to receive the editor instance from the child
  const handleEditorChange = useCallback((editorInstance: BlockNoteEditor | null) => {
    setEditor(editorInstance);
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    // Check the editor state received from the child
    if (!editor) {
      toast({ title: 'Editor not ready or failed to load', status: 'error', duration: 3000 });
      return;
    }
    if (!title.trim()) {
        toast({ title: 'Title is required', status: 'warning', duration: 3000 });
        return;
    }

    setIsSubmitting(true);

    // Get content from the editor instance we have in state
    const content = editor.document;

    try {
      const response = await fetch('/api/cards', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: title.trim(), content: content }),
      });

      const newCard = await response.json();

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
        throw new Error(newCard.message || 'Failed to create card.');
      }
    } catch (error: any) {
      console.error('Create card error:', error);
      toast({
        title: 'Error creating card.',
        description: error.message || 'Could not save the card.',
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
    <Container maxW="container.lg" py={8}>
      <Heading as="h1" size="xl" mb={6}>
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
              isDisabled={isSubmitting}
            />
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Content</FormLabel>
            {/* Render the dynamically imported component and set it to editable */}
            <BlockNoteEditorComponent onEditorChange={handleEditorChange} editable={true} />
          </FormControl>

          <Button
            type="submit"
            colorScheme="green"
            isLoading={isSubmitting}
            alignSelf="flex-start"
          >
            Create Card
          </Button>
        </VStack>
      </Box>
    </Container>
  );
} 