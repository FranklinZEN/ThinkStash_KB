'use client';

import React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter, useParams } from 'next/navigation';
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
import { BlockNoteEditor, PartialBlock } from "@blocknote/core";
import "@blocknote/mantine/style.css";

// Define type for Knowledge Card data
interface KnowledgeCard {
  id: string;
  title: string;
  content: any; // BlockNote JSON structure
  userId: string;
  folderId: string | null;
  createdAt: string;
  updatedAt: string;
}

export default function CardDetailPage() {
  const { data: session, status } = useSession();
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
    // Set editable based on isEditing state
    editable: isEditing,
    // Define the initial content (will be loaded from fetched data)
    // initialContent: card ? card.content : undefined
    // onEditorContentChange: (editor) => {
    //   // Optional: Could implement auto-save or track changes here
    // }
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
      if (editor && data.content) {
        try {
          await editor.replaceBlocks(editor.topLevelBlocks, data.content as PartialBlock[]);
        } catch (err) {
          console.error('Error loading content into editor:', err);
          // Don't throw here, just log the error
        }
      }
    } catch (err: any) {
      console.error('Fetch card error:', err);
      setError(err.message || 'Could not load card');
      toast({
        title: 'Error loading card',
        description: err.message || 'Could not load card data',
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
      const updatePayload: any = {};
      if (hasTitleChanged) updatePayload.title = title.trim();
      if (hasContentChanged) updatePayload.content = currentContent;

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
    } catch (err: any) {
      console.error('Save card error:', err);
      setError(err.message || 'Could not save changes');
      toast({ title: 'Error saving card', description: err.message, status: 'error', duration: 5000 });
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

      const data = await response.json();

      if (response.ok) {
        toast({ title: 'Card deleted', status: 'success', duration: 3000 });
        router.push('/'); // Redirect to homepage after delete
        router.refresh();
      } else {
        throw new Error(data.message || 'Failed to delete card');
      }
    } catch (err: any) {
      console.error('Delete card error:', err);
      setError(err.message || 'Could not delete card');
      toast({ title: 'Error deleting card', description: err.message, status: 'error', duration: 5000 });
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
              Are you sure you want to delete the card titled "{card.title}"? This action cannot be undone.
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