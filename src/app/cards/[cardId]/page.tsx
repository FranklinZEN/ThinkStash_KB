'use client';

import React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter, useParams } from 'next/navigation';
import {
  Box,
  Button,
  Input,
  Heading,
  Spinner,
  useToast,
  Flex,
  Text,
  Container,
  Spacer,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
  IconButton,
} from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';

// Import BlockNote components - STATICALLY
import { useBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import { BlockNoteEditor, type PartialBlock } from '@blocknote/core';
import '@blocknote/mantine/style.css';
import type { BlockNoteDocument } from '@/types/blocknote';

// Define type for Knowledge Card data
interface KnowledgeCard {
  id: string;
  title: string;
  content: BlockNoteDocument | string | null; // Updated type for BlockNote JSON structure
  userId: string;
  folderId: string | null;
  createdAt: string;
  updatedAt: string;
}

interface CardUpdatePayload {
  title?: string;
  content?: BlockNoteDocument | string | null;
}

export default function CardDetailPage() {
  const { status } = useSession();
  const router = useRouter();
  const params = useParams();
  const cardId = params?.cardId as string;
  const toast = useToast();
  const {
    isOpen: isAlertOpen,
    onOpen: onAlertOpen,
    onClose: onAlertClose,
  } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const [card, setCard] = useState<KnowledgeCard | null>(null);
  const [title, setTitle] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  // --- BlockNote Editor Setup --- Call hook unconditionally
  const editor: BlockNoteEditor | null = useBlockNote({
    // Set editable based on isEditing state - Passed to View instead
    // editable: isEditing,
    // Define the initial content (will be loaded from fetched data)
    initialContent: undefined, // Start empty, load later
    // onEditorContentChange: (editor) => {
    //   // Optional: Could implement auto-save or track changes here
    // }
  });

  // --- Data Fetching ---
  const fetchCard = useCallback(async () => {
    if (!cardId || status !== 'authenticated') return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/cards/${cardId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        cache: 'no-store', // Prevent caching
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.error || `Failed to fetch card: ${response.statusText}`,
        );
      }

      const data: KnowledgeCard = await response.json();
      setCard(data);
      setTitle(data.title);

      // Load content into editor once fetched and editor is ready
      if (editor && data.content) {
        try {
          // Ensure content is in the correct format (BlockNoteDocument)
          let contentToLoad: BlockNoteDocument;
          if (typeof data.content === 'string') {
            // Should ideally not happen if API sends BlockNoteDocument
            const trimmedContent = data.content.trim();
            if (
              trimmedContent.startsWith('[') ||
              trimmedContent.startsWith('{')
            ) {
              contentToLoad = JSON.parse(trimmedContent);
            } else {
              console.warn(
                'Fetched content is string but not JSON, treating as single paragraph.',
              );
              contentToLoad = [
                {
                  id: `block-${Date.now().toString()}-${Math.random().toString(36).substring(2, 7)}`,
                  type: 'paragraph',
                  props: {
                    textColor: 'default',
                    backgroundColor: 'default',
                    textAlignment: 'left',
                  },
                  content: [
                    { type: 'text', text: data.content as string, styles: {} },
                  ],
                  children: [],
                },
              ];
            }
          } else {
            contentToLoad = data.content as BlockNoteDocument; // Assuming it's already BlockNoteDocument or null
          }
          // Use replaceBlocks API
          if (contentToLoad) {
            // only load if not null
            await editor.replaceBlocks(
              editor.topLevelBlocks,
              contentToLoad as PartialBlock[],
            );
          }
        } catch (err: unknown) {
          console.error('Error loading content into editor:', err);
          // Don't throw here, just log the error
        }
      }
    } catch (err: unknown) {
      console.error('Fetch card error:', err);
      const errorMessage =
        err instanceof Error ? err.message : 'Could not load card data';
      setError(errorMessage);
      toast({
        title: 'Error loading card',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
    // Fetch depends on cardId and auth status. Editor is dependency for loading content AFTER fetch.
  }, [cardId, status, editor, toast]);

  useEffect(() => {
    if (status === 'authenticated' && cardId) {
      fetchCard();
    } else if (status === 'unauthenticated') {
      router.push(`/api/auth/signin?callbackUrl=/cards/${cardId}`);
    }
    // fetchCard is stable due to useCallback, so only run when these change.
  }, [status, cardId, router, fetchCard]);

  // --- Save Changes ---
  const handleSaveChanges = async () => {
    if (!editor || !card) return;

    const currentContent = editor.document;
    const originalContent = card.content;

    // Basic check for changes (more robust checks might compare JSON deeply)
    const hasTitleChanged = title.trim() !== card.title;
    // Normalize original content for comparison
    let originalContentForComparison: BlockNoteDocument | undefined;
    if (originalContent) {
      if (typeof originalContent === 'string') {
        // Should ideally not happen
        const trimmedContent = originalContent.trim();
        if (trimmedContent.startsWith('[') || trimmedContent.startsWith('{')) {
          originalContentForComparison = JSON.parse(trimmedContent);
        } else {
          originalContentForComparison = [
            {
              id: `block-orig-${Date.now().toString()}-${Math.random().toString(36).substring(2, 7)}`,
              type: 'paragraph',
              props: {
                textColor: 'default',
                backgroundColor: 'default',
                textAlignment: 'left',
              },
              content: [{ type: 'text', text: originalContent, styles: {} }],
              children: [],
            },
          ];
        }
      } else {
        originalContentForComparison = originalContent as BlockNoteDocument;
      }
    }
    const hasContentChanged =
      JSON.stringify(currentContent) !==
      JSON.stringify(originalContentForComparison || []);

    if (!hasTitleChanged && !hasContentChanged) {
      toast({ title: 'No changes detected.', status: 'info', duration: 3000 });
      setIsEditing(false); // Exit edit mode if no changes
      return;
    }
    if (!title.trim()) {
      toast({
        title: 'Title cannot be empty.',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    const updatePayload: CardUpdatePayload = {};
    if (hasTitleChanged) updatePayload.title = title.trim();
    if (hasContentChanged)
      updatePayload.content = currentContent as BlockNoteDocument;

    setIsSaving(true);
    setError(null);

    try {
      // Use PUT to replace the entire card data (or PATCH if API supports partial)
      // Assuming PUT for now based on previous context
      const response = await fetch(`/api/cards/${cardId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatePayload),
      });

      const updatedCard = await response.json();

      if (response.ok) {
        setCard(updatedCard as KnowledgeCard);
        setTitle(updatedCard.title);
        setIsEditing(false);
        toast({
          title: 'Card updated successfully',
          status: 'success',
          duration: 3000,
        });
      } else {
        throw new Error(updatedCard.message || 'Failed to update card');
      }
    } catch (err: unknown) {
      console.error('Save card error:', err);
      const errorMessage =
        err instanceof Error ? err.message : 'Could not save changes';
      setError(errorMessage);
      toast({
        title: 'Error saving card',
        description: errorMessage,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsSaving(false);
    }
  };

  // --- Delete Card ---
  const handleDelete = async () => {
    onAlertClose(); // Close confirmation dialog
    setIsDeleting(true);
    setError(null);
    try {
      const response = await fetch(`/api/cards/${cardId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        toast({ title: 'Card deleted', status: 'success', duration: 3000 });
        router.push('/'); // Redirect to homepage after delete
      } else {
        const data = await response
          .json()
          .catch(() => ({ message: 'Failed to delete card' }));
        throw new Error(data.message || 'Failed to delete card');
      }
    } catch (err: unknown) {
      console.error('Delete card error:', err);
      const errorMessage =
        err instanceof Error ? err.message : 'Could not delete card';
      setError(errorMessage);
      toast({
        title: 'Error deleting card',
        description: errorMessage,
        status: 'error',
        duration: 5000,
      });
      setIsDeleting(false);
    }
  };

  // --- Render Logic ---
  if (status === 'loading' || (isLoading && !error && !card)) {
    // Show loading if auth loading OR data loading (and no error/card yet)
    return (
      <Flex justify="center" align="center" height="80vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
    // This case might be handled by the useEffect redirect, but keep as safety net
    return (
      <Flex justify="center" align="center" height="80vh">
        <Text>Redirecting to sign in...</Text>
      </Flex>
    );
  }

  if (error && !card) {
    // Show error only if we failed to load the card completely
    return (
      <Container centerContent py={10}>
        <Heading size="lg" mb={4}>
          Error
        </Heading>
        <Text color="red.500">{error}</Text>
        <Button mt={4} onClick={() => router.push('/')}>
          Go Home
        </Button>
      </Container>
    );
  }

  if (!card) {
    // Fallback if loading finished but card is still null (shouldn't happen ideally)
    return <Text>Card not found or failed to load.</Text>;
  }

  // Determine if content has changed (simple check for enabling save button)
  // Normalize original content for comparison
  let originalContentForComparisonCanSave: BlockNoteDocument | undefined;
  if (card.content) {
    if (typeof card.content === 'string') {
      const trimmedContent = card.content.trim();
      if (trimmedContent.startsWith('[') || trimmedContent.startsWith('{')) {
        originalContentForComparisonCanSave = JSON.parse(trimmedContent);
      } else {
        originalContentForComparisonCanSave = [
          {
            id: `block-cansave-${Date.now().toString()}-${Math.random().toString(36).substring(2, 7)}`,
            type: 'paragraph',
            props: {
              textColor: 'default',
              backgroundColor: 'default',
              textAlignment: 'left',
            },
            content: [{ type: 'text', text: card.content, styles: {} }],
            children: [],
          },
        ];
      }
    } else {
      originalContentForComparisonCanSave = card.content as BlockNoteDocument;
    }
  }
  const contentChanged = editor
    ? JSON.stringify(editor.document) !==
      JSON.stringify(originalContentForComparisonCanSave || [])
    : false;
  const titleChanged = title.trim() !== (card.title || '');
  const canSave = isEditing && (titleChanged || contentChanged);

  return (
    <Container maxW="container.lg" py={8}>
      <Flex mb={6} alignItems="center">
        <Input
          variant="flushed" // Use a less prominent input for title
          size="lg"
          fontSize="2xl"
          fontWeight="bold"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          isDisabled={!isEditing || isSaving || isDeleting} // Disable if not editing
          placeholder="Card Title"
          mr={4}
        />
        <Spacer />
        {isEditing ? (
          <>
            <Button
              colorScheme="green"
              onClick={handleSaveChanges}
              isLoading={isSaving}
              isDisabled={!canSave || isSaving || isDeleting}
              mr={2}
            >
              Save
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setIsEditing(false);
                setTitle(card.title); // Revert title on cancel
                // Revert editor content might require re-fetching or complex state management
                // For now, just exit edit mode. User can save or refresh to discard.
              }}
              isDisabled={isSaving || isDeleting}
            >
              Cancel
            </Button>
          </>
        ) : (
          <Button
            colorScheme="blue"
            onClick={() => setIsEditing(true)} // Toggle edit/save
            isDisabled={isSaving || isDeleting} // Disable Edit button when saving/deleting
            mr={2}
          >
            Edit Card
          </Button>
        )}
        <IconButton
          aria-label="Delete Card"
          icon={<DeleteIcon />} // Keep delete separate
          colorScheme="red"
          onClick={onAlertOpen} // Open confirmation dialog
          isLoading={isDeleting}
          isDisabled={isSaving || isDeleting}
        />
      </Flex>

      <Box borderWidth="1px" borderRadius="md" p={1} minH="500px">
        {/* Pass editable prop based on isEditing state */}
        {editor ? (
          <BlockNoteView editor={editor} editable={isEditing} theme="light" />
        ) : (
          <Flex justify="center" align="center" height="200px">
            <Spinner size="md" />
            <Text ml={3}>Loading Editor...</Text>
          </Flex>
        )}
      </Box>

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        isOpen={isAlertOpen}
        leastDestructiveRef={cancelRef}
        onClose={onAlertClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete Knowledge Card
            </AlertDialogHeader>

            <AlertDialogBody>
              {`Are you sure you want to delete the card titled "${card.title}"? This action cannot be undone.`}
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button
                ref={cancelRef}
                onClick={onAlertClose}
                isDisabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={handleDelete}
                ml={3}
                isLoading={isDeleting}
              >
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Container>
  );
}
