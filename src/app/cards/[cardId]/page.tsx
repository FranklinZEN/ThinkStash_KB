'use client';

import React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter, useParams } from 'next/navigation';
import dynamic from 'next/dynamic';
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
  FormControl,
  FormLabel,
  HStack,
  Tag,
  TagLabel,
  TagCloseButton,
  VStack,
} from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';

import {
  BlockNoteEditor as BlockNoteEditorType,
  type PartialBlock,
} from '@blocknote/core';
import '@blocknote/mantine/style.css';
import type { BlockNoteDocument } from '@/types/blocknote';

// Dynamically import the editor component with SSR disabled (similar to NewCardPage)
const BlockNoteEditorComponent = dynamic(
  () => import('@/components/BlockNoteEditorComponent'),
  {
    ssr: false,
    loading: () => (
      <Flex justify="center" align="center" minH="300px">
        <Spinner />
        <Text ml={3}>Loading Editor...</Text>
      </Flex>
    ),
  },
);

// Define type for individual Tag
interface Tag {
  id: string;
  name: string;
  // createdAt?: string; // Optional, if needed later
  // updatedAt?: string; // Optional, if needed later
}

// Define type for Knowledge Card data
interface KnowledgeCard {
  id: string;
  title: string;
  content: BlockNoteDocument | string | null; // Updated type for BlockNote JSON structure
  tags: Tag[]; // Corrected: expects an array of Tag objects
  userId: string;
  folderId: string | null;
  createdAt: string;
  updatedAt: string;
}

interface CardUpdatePayload {
  title?: string;
  content?: BlockNoteDocument | string | null;
  tags?: string[]; // This should be string[] as expected by the API endpoint body
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
  const [keywords, setKeywords] = useState<string[]>([]); // State for keywords
  const [currentKeyword, setCurrentKeyword] = useState(''); // State for current keyword input
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editor, setEditor] = useState<BlockNoteEditorType | null>(null);
  const [editorContent, setEditorContent] = useState<
    PartialBlock[] | undefined
  >(undefined); // For content tracking
  const [editorContentForInitialLoad, setEditorContentForInitialLoad] =
    useState<PartialBlock[] | undefined>(undefined);

  const handleEditorInstanceReady = useCallback(
    (editorInstance: BlockNoteEditorType | null) => {
      setEditor(editorInstance);
    },
    [], // No dependencies needed if it just sets the editor instance
  );

  // Callback to receive content updates from the editor component
  const handleEditorContentUpdate = useCallback((blocks: PartialBlock[]) => {
    setEditorContent(blocks);
  }, []);

  // --- Data Fetching ---
  const fetchCard = useCallback(async () => {
    if (!cardId || status !== 'authenticated') return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/cards/${cardId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
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
      setKeywords(data.tags ? data.tags.map((tag) => tag.name) : []);

      // Prepare initialContent for the editor
      if (data.content) {
        if (typeof data.content === 'string') {
          const trimmedContent = data.content.trim();
          if (
            trimmedContent.startsWith('[') ||
            trimmedContent.startsWith('{')
          ) {
            try {
              setEditorContentForInitialLoad(
                JSON.parse(trimmedContent) as PartialBlock[],
              );
            } catch (e) {
              console.warn(
                'Failed to parse string content as JSON, using as plain text.',
                e,
              );
              setEditorContentForInitialLoad([
                { type: 'paragraph', content: trimmedContent },
              ]);
            }
          } else {
            setEditorContentForInitialLoad([
              { type: 'paragraph', content: data.content },
            ]);
          }
        } else if (Array.isArray(data.content)) {
          setEditorContentForInitialLoad(data.content as PartialBlock[]);
        }
      } else {
        setEditorContentForInitialLoad(undefined);
      }
      // REMOVED: explicit editor.replaceBlocks() call. initialContent prop handles this.
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
  }, [cardId, status, toast]);

  useEffect(() => {
    if (status === 'authenticated' && cardId) {
      fetchCard();
    } else if (status === 'unauthenticated') {
      router.push(`/api/auth/signin?callbackUrl=/cards/${cardId}`);
    }
    // fetchCard is stable due to useCallback, so only run when these change.
  }, [status, cardId, router, fetchCard]);

  // Keyword/Tag handling functions (copied from NewCardPage and adapted)
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

    // Check if keywords have changed
    const originalTags = card.tags || [];
    const hasKeywordsChanged =
      JSON.stringify(keywords.sort()) !== JSON.stringify(originalTags.sort());

    if (!hasTitleChanged && !hasContentChanged && !hasKeywordsChanged) {
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
    // Use editorContent for consistency if available, otherwise editor.document
    const contentToSave = editorContent || (editor ? editor.document : null);
    if (hasContentChanged && contentToSave)
      updatePayload.content = contentToSave as BlockNoteDocument;
    if (hasKeywordsChanged) updatePayload.tags = keywords; // Correct: send the array of keyword strings

    setIsSaving(true);
    setError(null);

    console.log('Updating card with payload:', updatePayload); // Log payload being sent

    try {
      // Use PUT to replace the entire card data (or PATCH if API supports partial)
      // Assuming PUT for now based on previous context
      const response = await fetch(`/api/cards/${cardId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatePayload),
      });

      const updatedCard = await response.json();
      console.log('API response for updated card:', updatedCard); // Log API response

      if (response.ok) {
        setCard(updatedCard as KnowledgeCard);
        setTitle(updatedCard.title);
        setKeywords(
          updatedCard.tags ? updatedCard.tags.map((tag) => tag.name) : [],
        ); // Extract tag names
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
      <Container centerContent py={10} fontFamily="'Open Sans', sans-serif">
        <Spinner size="xl" />
        <Text mt={4}>Loading card details...</Text>
      </Container>
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
  // Ensure keywords comparison for canSave is robust
  const originalTagsForCanSave = card.tags || [];
  const keywordsChangedForCanSave =
    JSON.stringify(keywords.sort()) !==
    JSON.stringify(originalTagsForCanSave.sort());
  const canSave =
    isEditing && (titleChanged || contentChanged || keywordsChangedForCanSave);

  return (
    <Container maxW="container.lg" py={8} fontFamily="'Open Sans', sans-serif">
      <Flex mb={6} align="center">
        <Heading
          as="h1"
          size="xl"
          flexGrow={1}
          fontFamily="'Open Sans', sans-serif"
          fontSize="36px"
        >
          {isEditing ? 'Edit Knowledge Card' : card?.title || 'Card Details'}
        </Heading>
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
                setKeywords(card.tags ? card.tags.map((tag) => tag.name) : []); // Revert keywords to original card tag names
                // Revert editor content might require re-fetching or complex state management
                // For now, just exit edit mode. User can save or refresh to discard.
                // Consider calling fetchCard() here too if a full reset is desired on this cancel action.
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

      {isEditing ? (
        <Box
          as="form"
          onSubmit={(e) => {
            e.preventDefault();
            handleSaveChanges();
          }}
        >
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
                isDisabled={isSaving}
                fontFamily="'Open Sans', sans-serif"
                fontSize="16px"
              />
            </FormControl>

            {/* Key Words Section - Moved here and adapted */}
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
                isDisabled={!isEditing || isSaving} // Ensure it's disabled when not editing or when saving
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
                    <TagCloseButton
                      onClick={() => removeKeyword(keyword)}
                      isDisabled={!isEditing || isSaving}
                    />
                  </Tag>
                ))}
              </HStack>
            </FormControl>

            <FormControl isRequired>
              <FormLabel fontFamily="'Open Sans', sans-serif" fontSize="24px">
                Content
              </FormLabel>
              <Box borderWidth="1px" borderRadius="md" p={0} minH="500px">
                <BlockNoteEditorComponent
                  onEditorChange={handleEditorInstanceReady}
                  onContentUpdate={handleEditorContentUpdate}
                  editable={isEditing}
                  initialContent={editorContentForInitialLoad}
                />
              </Box>
            </FormControl>

            <Flex justify="flex-start" gap={3} mt={4}>
              <Button
                colorScheme="green"
                type="submit"
                isLoading={isSaving}
                fontFamily="'Open Sans', sans-serif"
                fontSize="16px"
              >
                Save Changes
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setIsEditing(false);
                  if (card) {
                    setTitle(card.title);
                    setKeywords(
                      card.tags ? card.tags.map((tag) => tag.name) : [],
                    );
                    // Content reset is implicitly handled by BlockNoteEditorComponent
                    // when isEditing becomes false and it re-renders with card.content,
                    // or by fetchCard() if the user used the header cancel that triggers a re-fetch.
                  }
                }}
                isDisabled={isSaving}
                fontFamily="'Open Sans', sans-serif"
                fontSize="16px"
              >
                Cancel
              </Button>
            </Flex>
          </VStack>
        </Box>
      ) : (
        <Box>
          {/* Display Title - Already part of the Heading element above for non-editing mode */}
          {/* Display Tags/Keywords - If not editing, show them as static tags */}
          {card && card.tags && card.tags.length > 0 && (
            <Box my={4}>
              <Heading
                as="h3"
                size="md"
                mb={2}
                fontFamily="'Open Sans', sans-serif"
                fontSize="20px"
              >
                Key Words
              </Heading>
              <HStack spacing={2} flexWrap="wrap">
                {card.tags.map((tag) => (
                  <Tag
                    size="lg"
                    key={tag.id}
                    borderRadius="md"
                    variant="solid"
                    colorScheme="teal"
                  >
                    <TagLabel>{tag.name}</TagLabel>
                  </Tag>
                ))}
              </HStack>
            </Box>
          )}

          <Box
            borderWidth="1px"
            borderRadius="md"
            p={1}
            minH="500px"
            mt={card && card.tags && card.tags.length > 0 ? 0 : 4}
          >
            <BlockNoteEditorComponent
              onEditorChange={handleEditorInstanceReady}
              onContentUpdate={handleEditorContentUpdate}
              editable={isEditing}
              initialContent={editorContentForInitialLoad}
            />
          </Box>
        </Box>
      )}

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
