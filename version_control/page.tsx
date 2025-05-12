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

// Import BlockNote components
import { useBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/mantine";
import { BlockNoteEditor } from "@blocknote/core";
import "@blocknote/mantine/style.css";
import type { BlockNoteDocument } from '@/types/blocknote';

// Define type for Knowledge Card data
interface KnowledgeCard {
  id: string;
  title: string;
  content: BlockNoteDocument | string | null; // Updated to include string
  userId: string;
  folderId: string | null;
  createdAt: string;
  updatedAt: string;
}

// Define type for card update payload
interface CardUpdatePayload {
  title?: string;
  content?: BlockNoteDocument | null;
}

export default function CardDetailPage() {
  const { status } = useSession();
  const router = useRouter();
  const params = useParams();
  const cardId = params?.cardId as string; // Get cardId from route
  const toast = useToast();
  const { isOpen: isAlertOpen, onOpen: onAlertOpen, onClose: onAlertClose } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const [card, setCard] = useState<KnowledgeCard | null>(null);
  const [title, setTitle] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  // --- BlockNote Editor Setup ---
  const editor: BlockNoteEditor | null = useBlockNote({
    // Set editable based on isEditing state - MOVED TO BlockNoteView props
    // editable: isEditing, // This was causing the error
    // Define the initial content (will be loaded from fetched data)
    // initialContent: card ? card.content : undefined
  });

  // --- Data Fetching --- 
  const fetchCard = useCallback(async () => {
    if (!cardId) return;
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
        throw new Error(errorData.error || `Failed to fetch card: ${response.statusText}`);
      }

      const data: KnowledgeCard = await response.json();
      setCard(data);
      setTitle(data.title);
      
      // Load content into editor once fetched
      if (editor && data.content !== null) { // Ensure data.content is not null
        try {
          let contentToLoad: import("@blocknote/core").PartialBlock[] | undefined = undefined;

          if (typeof data.content === 'string') {
            console.warn("Received string content from API, attempting to parse or treat as plain text.");
            const trimmedContent = data.content.trim();
            if (trimmedContent.startsWith('[') && trimmedContent.endsWith(']')) { // Basic JSON array check
              try {
                const parsedContent = JSON.parse(trimmedContent);
                // Add further validation if parsedContent is actually PartialBlock[]
                if (Array.isArray(parsedContent)) {
                  contentToLoad = parsedContent as import("@blocknote/core").PartialBlock[];
                } else {
                  console.warn("Parsed string content was not an array, treating as single paragraph.");
                  contentToLoad = [{ type: 'paragraph', content: trimmedContent }];
                }
              } catch (e) {
                console.warn("Fetched string content looked like JSON array but failed to parse:", e);
                contentToLoad = [{ type: 'paragraph', content: trimmedContent }];
              }
            } else if (trimmedContent === "") { // Handle empty string case explicitly
                contentToLoad = []; // or undefined, or a single empty paragraph
            } else {
              // If not a JSON string, treat as plain text for a single paragraph
              contentToLoad = [{ type: 'paragraph', content: trimmedContent }];
            }
          } else if (Array.isArray(data.content)) { // If it's not a string, it should be BlockNoteDocument (Block[])
            // Assuming BlockNoteDocument is compatible with PartialBlock[]
            // This might need as import("@blocknote/core").PartialBlock[] if BlockNoteDocument is Block[]
            contentToLoad = data.content as import("@blocknote/core").PartialBlock[];
          }

          if (contentToLoad) {
            await editor.replaceBlocks(editor.topLevelBlocks, contentToLoad);
          } else if (data.content === null || (Array.isArray(data.content) && data.content.length === 0)) {
            // If content was null or an empty array, clear the editor
            await editor.replaceBlocks(editor.topLevelBlocks, []);
          }
        } catch (err) { 
          console.error('Error loading content into editor:', err);
        }
      } else if (editor && data.content === null) {
        // If content is explicitly null, clear the editor
        await editor.replaceBlocks(editor.topLevelBlocks, []);
      }
    } catch (err: unknown) { // Changed from any
      console.error('Fetch card error:', err);
      const errorMessage = err instanceof Error ? err.message : 'Could not load card data';
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
  }, [cardId, editor, toast]);

  useEffect(() => {
    if (status === 'authenticated' && cardId) {
      fetchCard();
    } else if (status === 'unauthenticated') {
      router.push(`/api/auth/signin?callbackUrl=/cards/${cardId}`);
    }
  }, [status, cardId, router, fetchCard]);

  // --- Save Changes --- 
  const handleSaveChanges = async () => {
    if (!editor || !card) return;

    const currentContent = editor.document;
    const originalContent = card.content;

    // Basic check for changes (more robust checks might compare JSON deeply)
    const hasTitleChanged = title.trim() !== card.title;
    const hasContentChanged = JSON.stringify(currentContent) !== JSON.stringify(originalContent);

    if (!hasTitleChanged && !hasContentChanged) {
      toast({ title: 'No changes detected.', status: 'info', duration: 3000 });
      return;
    }
    if (!title.trim()) {
        toast({ title: 'Title cannot be empty.', status: 'warning', duration: 3000 });
        return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const updatePayload: CardUpdatePayload = {}; // Now strongly typed
      if (hasTitleChanged) updatePayload.title = title.trim();
      if (hasContentChanged) updatePayload.content = currentContent as BlockNoteDocument; // Changed cast

      const response = await fetch(`/api/cards/${cardId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatePayload),
      });

      const updatedCard = await response.json();

      if (response.ok) {
        setCard(updatedCard); // Update local state with response
        setTitle(updatedCard.title); // Update title state
        // Update editor content ONLY IF it changed from the server response (unlikely unless concurrent edits)
        // editor.replaceBlocks(editor.topLevelBlocks, updatedCard.content);

        toast({ title: 'Card updated successfully', status: 'success', duration: 3000 });
      } else {
        throw new Error(updatedCard.message || 'Failed to update card');
      }
    } catch (err: unknown) { // Changed from any
      console.error('Save card error:', err);
      const errorMessage = err instanceof Error ? err.message : 'Could not save changes';
      setError(errorMessage);
      toast({ title: 'Error saving card', description: errorMessage, status: 'error', duration: 5000 });
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
        router.refresh();
      } else {
        // Ensure data is read for error message
        const errorData = await response.json().catch(() => ({ message: 'Failed to delete card' }));
        throw new Error(errorData.message || 'Failed to delete card');
      }
    } catch (err: unknown) { // Changed from any
      console.error('Delete card error:', err);
      const errorMessage = err instanceof Error ? err.message : 'Could not delete card';
      setError(errorMessage);
      toast({ title: 'Error deleting card', description: errorMessage, status: 'error', duration: 5000 });
      setIsDeleting(false);
    }
    // No finally needed for setIsDeleting as we redirect on success
  };

  // --- Render Logic --- 
  if (status === 'loading' || (isLoading && !error)) {
    return (
      <Flex justify="center" align="center" height="80vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
    return (
      <Flex justify="center" align="center" height="80vh">
        <Text>Redirecting to sign in...</Text>
      </Flex>
    );
  }

  if (error) {
    return (
      <Container centerContent py={10}>
        <Heading size="lg" mb={4}>Error</Heading>
        <Text color="red.500">{error}</Text>
        <Button mt={4} onClick={() => router.push('/')}>Go Home</Button>
      </Container>
    );
  }

  if (!card) {
    // Should be covered by loading/error states, but as a fallback
    return <Text>Card data not available.</Text>;
  }

  // Determine if content has changed (simple check for enabling save button)
  const contentChanged = editor ? JSON.stringify(editor.document) !== JSON.stringify(card.content) : false;
  const canSave = (title.trim() !== card.title && title.trim().length > 0) || contentChanged;

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
        <Button
            colorScheme="blue"
            onClick={isEditing ? handleSaveChanges : () => setIsEditing(true)} // Toggle edit/save
            isLoading={isSaving}
            // Disable Save when not editing OR no changes OR saving/deleting
            // Disable Edit button when saving/deleting
            isDisabled={isEditing ? (!canSave || isSaving || isDeleting) : (isSaving || isDeleting)}
            mr={2}
          >
            {isEditing ? "Save Changes" : "Edit Card"} {/* Change button text */}
          </Button>
          <IconButton
            aria-label="Delete Card"
            icon={<DeleteIcon />}
            colorScheme="red"
            onClick={onAlertOpen} // Open confirmation dialog
            isLoading={isDeleting}
            isDisabled={isSaving || isDeleting}
          />
      </Flex>

       <Box borderWidth="1px" borderRadius="md" p={1} minH="500px">
            {/* Pass editable prop based on isEditing state */} 
            {editor ? <BlockNoteView editor={editor} editable={isEditing} theme="light" /> : <Text>Loading Editor...</Text>}
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
              Are you sure you want to delete the card titled &quot;{card.title}&quot;? This action cannot be undone.
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onAlertClose} isDisabled={isDeleting}>
                Cancel
              </Button>
              <Button colorScheme="red" onClick={handleDelete} ml={3} isLoading={isDeleting}>
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Container>
  );
} 