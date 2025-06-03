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
  Tag as ChakraTag,
  TagLabel,
  TagCloseButton,
  VStack,
} from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';

import '@blocknote/mantine/style.css';
import {
  type AppEditor,
  type AppPartialBlock,
  type AppInlineContent as _AppInlineContent,
  type AppInlineContentArray,
} from '@/lib/blocknote/appSchema';
import { type ContentBlock as AIServiceContentBlock } from '@/types/api/ai-service';
import { v4 as uuidv4 } from 'uuid';

// Helper function to check if editor content is effectively empty
const isEditorEmpty = (blocks: AppPartialBlock[] | undefined | null): boolean => {
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
            return false; // Other object types (mentions, custom inline) mean not empty
          }
          // If inlineItem is not a string and not an object with a 'type' property,
          // it's an unknown structure. Treat as non-empty to be safe, or log/error.
          return false;
        });
      }
    }
  }
  return false;
};

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
  content: AppPartialBlock[] | string | null; // Updated type for BlockNote JSON structure
  tags: Tag[]; // Corrected: expects an array of Tag objects
  userId: string;
  folderId: string | null;
  createdAt: string;
  updatedAt: string;
}

interface CardUpdatePayload {
  title?: string;
  content?: AppPartialBlock[] | string | null;
  tags?: string[]; // This should be string[] as expected by the API endpoint body
}

// ADDED: Helper function to extract plain text from BlockNote InlineContent[]
const extractTextFromInlineContent = (inlineContent: AppInlineContentArray | string | undefined): string => {
  if (!inlineContent) return '';
  if (typeof inlineContent === 'string') return inlineContent;
  return inlineContent.map(item => {
    if (item.type === 'text') return item.text;
    if (item.type === 'link' && item.content) {
      return extractTextFromInlineContent(item.content);
    }
    // Add other inline types if necessary, for now, just text and link content
    return '';
  }).join('');
};

// Function to map BlockNote PartialBlock[] to AIServiceContentBlock[]
export const mapPartialBlocksToAIServiceContentBlocks = (
  partialBlocks: AppPartialBlock[], // Input is AppPartialBlock[]
  userId: string,
  documentId: string
): AIServiceContentBlock[] => {
  const aiServiceBlocks: AIServiceContentBlock[] = [];
  if (!partialBlocks || partialBlocks.length === 0) return aiServiceBlocks;

  let currentOrderIndex = 0;
  let i = 0;

  while (i < partialBlocks.length) {
    const block = partialBlocks[i]; // block is AppPartialBlock
    if (!block || !block.type) {
      i++;
      continue;
    }
    // Use existing block.id if available, else generate a new one
    const block_id = block.id || uuidv4(); 
    const tmp_id = block_id; 

    if (block.type === 'bulletListItem' || block.type === 'numberedListItem') {
      const listItemsContent: string[] = [];
      const isOrdered = block.type === 'numberedListItem';
      const listBlockType = block.type;
      // Use ID of the first item as the list's representative ID for the AI service block
      const listBlockId = block_id; 

      let listStartNumber: number | null = null;
      if (isOrdered && block.props?.start) {
        const startNum = parseInt(String(block.props.start), 10);
        if (!isNaN(startNum)) {
            listStartNumber = startNum;
        }
      }

      while (
        i < partialBlocks.length &&
        partialBlocks[i]?.type === listBlockType
      ) {
        const listItem = partialBlocks[i]; 
        if (listItem.content && Array.isArray(listItem.content)) {
            listItemsContent.push(extractTextFromInlineContent(listItem.content as AppInlineContentArray));
        }
        i++; 
      }

      if (listItemsContent.length > 0) {
        aiServiceBlocks.push({
          block_id: listBlockId,
          tmp_id: listBlockId,
          user_id: userId,
          document_id: documentId,
          type: 'list', 
          order_index: currentOrderIndex,
          items: listItemsContent,
          ordered: isOrdered,
          list_start_number: listStartNumber,
          content: null, 
        });
        currentOrderIndex++;
      }
      continue; 
    } else if (block.type === 'paragraph' || block.type === 'heading') {
      const textContent = extractTextFromInlineContent(block.content as AppInlineContentArray);
      if (textContent.trim() !== '' || block.type === 'paragraph') { // Keep empty paragraphs if that's desired, or add specific logic
        aiServiceBlocks.push({
          block_id,
          tmp_id,
          user_id: userId,
          document_id: documentId,
          type: block.type === 'heading' ? 'heading' : 'text', // Map 'paragraph' to 'text' for AI service
          order_index: currentOrderIndex,
          content: textContent,
          level: block.type === 'heading' ? block.props?.level : undefined,
          // Reset other fields not relevant for text/heading
          items: null,
          ordered: null,
          list_start_number: null,
        });
        currentOrderIndex++;
      }
      i++;
    } else {
      // Handle or skip other block types as needed
      // For now, we'll skip unknown block types to avoid errors
      // console.warn("Unsupported block type for AI service conversion:", block.type);
      i++;
    }
  }
  return aiServiceBlocks;
};

export default function CardDetailPage() {
  const { status } = useSession();
  const router = useRouter();
  const params = useParams();
  const cardId = params?.cardId as string;
  console.log('[CardDetailPage] Initial cardId from params:', cardId);
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
  const [editor, setEditor] = useState<AppEditor | null>(null);
  const [editorContent, setEditorContent] = useState<
    AppPartialBlock[] | undefined
  >(undefined); // For content tracking
  const [editorContentForInitialLoad, setEditorContentForInitialLoad] =
    useState<AppPartialBlock[] | undefined>(undefined);

  // ADD THIS: A state variable to help change the key of the editor component
  const [editorKey, setEditorKey] = useState(0);

  // ADDED: State for AI suggestions
  const [suggestedTitle, setSuggestedTitle] = useState<string | null>(null);
  const [isSuggestingTitle, setIsSuggestingTitle] = useState(false);
  const [suggestedKeywords, setSuggestedKeywords] = useState<string[] | null>(null);
  const [isSuggestingKeywords, setIsSuggestingKeywords] = useState(false);

  // ADD THIS useEffect to synchronize editorContentForInitialLoad with the card state
  useEffect(() => {
    // console.log('[CardDetail Page] useEffect for card.content, current card:', card);
    if (card && card.content) {
      let newInitialContent: AppPartialBlock[] | undefined;
      if (typeof card.content === 'string') {
        const trimmedContent = card.content.trim();
        // Try to parse as JSON array of AppPartialBlock first
        let parsedSuccessfully = false;
        if (trimmedContent.startsWith('[') && trimmedContent.endsWith(']')) {
          try {
            const parsed = JSON.parse(trimmedContent);
            if (Array.isArray(parsed)) { // Basic check
              newInitialContent = parsed as AppPartialBlock[]; // Assume structure is correct if it parses to an array
              parsedSuccessfully = true;
            }
          } catch (_e) {
            console.warn(
              '[CardDetail Page] Failed to parse string content as JSON array, treating as plain text paragraph.',
              _e
            );
          }
        }
        
        if (!parsedSuccessfully) {
          // If not a JSON array or parsing failed, treat as plain text in a paragraph
          newInitialContent = [
            {
              type: 'paragraph',
              content: [{ type: 'text', text: trimmedContent, styles: {} }] // Correctly typed content
            }
          ];
        }
      } else if (Array.isArray(card.content)) {
        newInitialContent = card.content as AppPartialBlock[];
      }
      // console.log('[CardDetail Page] Setting editorContentForInitialLoad:', newInitialContent);
      setEditorContentForInitialLoad(newInitialContent);
      if (card && card.updatedAt) {
        setEditorKey((prevKey) => prevKey + 1); // A simple increment, or use card.updatedAt
      }
    } else if (card) {
      // console.log('[CardDetail Page] Card content is null or undefined, setting editorContentForInitialLoad to undefined');
      setEditorContentForInitialLoad(undefined);
    }
    // Only run when `card` itself changes. Content is part of `card`.
  }, [card]);

  const handleEditorInstanceReady = useCallback(
    (editorInstance: AppEditor | null) => {
      setEditor(editorInstance);
    },
    [], // No dependencies needed if it just sets the editor instance
  );

  // Callback to receive content updates from the editor component
  const handleEditorContentUpdate = useCallback((blocks: AppPartialBlock[]) => {
    setEditorContent(blocks);
  }, []);

  // --- Data Fetching ---
  const fetchCard = useCallback(async () => {
    console.log('[CardDetailPage] fetchCard called with cardId:', cardId);
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
      // console.log('[CardDetail Page] fetchCard - card set:', data);

      // Prepare initialContent for the editor - THIS LOGIC IS NOW MOVED TO useEffect
      // if (data.content) { ... } else { setEditorContentForInitialLoad(undefined); }
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
    console.log('[CardDetailPage] useEffect for fetchCard triggered. cardId:', cardId, 'status:', status);
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

  // ADDED: Handler for "Suggest Title"
  const handleSuggestTitle = async () => {
    if (!editor && !card?.content) {
      toast({ title: 'No content available for title suggestion.', status: 'warning', duration: 3000 });
      return;
    }
    if (!card || !card.userId || !cardId) {
      toast({ title: 'Card data not loaded.', status: 'error', duration: 3000 });
      return;
    }

    let contentToProcess: AppPartialBlock[] | undefined = editorContent;
    if (!isEditing || !editorContent || editorContent.length === 0) {
        // Fallback to card.content if not editing or editorContent is empty
        if (card?.content) {
            if (typeof card.content === 'string') {
                // Correctly type the string content as a paragraph with text inline content
                contentToProcess = [{ type: 'paragraph', content: [{ type: 'text', text: card.content, styles: {} }] }];
            } else { // It's already AppPartialBlock[]
                contentToProcess = card.content as AppPartialBlock[];
            }
        }
    }


    if (!contentToProcess || contentToProcess.length === 0) {
        toast({ title: 'Content is empty, cannot suggest title.', status: 'info', duration: 3000 });
        return;
    }
    
    const aiServiceContentBlocks = mapPartialBlocksToAIServiceContentBlocks(contentToProcess, card.userId, cardId);

    if (aiServiceContentBlocks.length === 0) {
      toast({ title: 'No processable content found for title suggestion.', status: 'info', duration: 3000 });
      return;
    }

    setIsSuggestingTitle(true);
    setSuggestedTitle(null);
    try {
      const response = await fetch('/api/ai/generate-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_blocks: aiServiceContentBlocks }),
      });
      const data = await response.json();
      if (!response.ok || data.error_message) {
        throw new Error(data.error_message || 'Failed to suggest title');
      }
      setSuggestedTitle(data.suggested_title);
      toast({ title: 'Title suggestion received!', status: 'success', duration: 3000 });
    } catch (err) {
      console.error('Suggest title error:', err);
      const message = err instanceof Error ? err.message : 'Could not suggest title.';
      toast({ title: 'Error suggesting title', description: message, status: 'error', duration: 5000 });
    } finally {
      setIsSuggestingTitle(false);
    }
  };

  // ADDED: Handler for "Suggest Keywords"
  const handleSuggestKeywords = async () => {
    if (!editor && !card?.content) {
      toast({ title: 'No content available for keyword suggestion.', status: 'warning', duration: 3000 });
      return;
    }
     if (!card || !card.userId || !cardId) {
      toast({ title: 'Card data not loaded.', status: 'error', duration: 3000 });
      return;
    }

    let contentToProcess: AppPartialBlock[] | undefined = editorContent;
     if (!isEditing || !editorContent || editorContent.length === 0) {
        if (card?.content) {
            if (typeof card.content === 'string') {
                // Correctly type the string content as a paragraph with text inline content
                contentToProcess = [{ type: 'paragraph', content: [{ type: 'text', text: card.content, styles: {} }] }];
            } else {
                contentToProcess = card.content as AppPartialBlock[];
            }
        }
    }

    if (!contentToProcess || contentToProcess.length === 0) {
        toast({ title: 'Content is empty, cannot suggest keywords.', status: 'info', duration: 3000 });
        return;
    }

    const aiServiceContentBlocks = mapPartialBlocksToAIServiceContentBlocks(contentToProcess, card.userId, cardId);
    
    if (aiServiceContentBlocks.length === 0) {
      toast({ title: 'No processable content found for keyword suggestion.', status: 'info', duration: 3000 });
      return;
    }

    setIsSuggestingKeywords(true);
    setSuggestedKeywords(null);
    try {
      const response = await fetch('/api/ai/generate-keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_blocks: aiServiceContentBlocks }),
      });
      const data = await response.json();
      if (!response.ok || data.error_message) {
        throw new Error(data.error_message || 'Failed to suggest keywords');
      }
      setSuggestedKeywords(data.suggested_keywords);
      toast({ title: 'Keyword suggestions received!', status: 'success', duration: 3000 });
    } catch (err) {
      console.error('Suggest keywords error:', err);
      const message = err instanceof Error ? err.message : 'Could not suggest keywords.';
      toast({ title: 'Error suggesting keywords', description: message, status: 'error', duration: 5000 });
    } finally {
      setIsSuggestingKeywords(false);
    }
  };

  // --- Save Changes ---
  const handleSaveChanges = async () => {
    if (!editor || !card) return;

    // Use editorContent which is updated by onContentUpdate callback for the most current state.
    // Fallback to editor.document if editorContent is somehow not set, though it should be.
    const currentContentToValidate = editorContent || (editor as AppEditor)?.document;

    const originalContent = card.content;

    // Basic check for changes (more robust checks might compare JSON deeply)
    const hasTitleChanged = title.trim() !== card.title;
    // Normalize original content for comparison
    let originalContentForComparison: AppPartialBlock[] | undefined;
    if (originalContent) {
      if (typeof originalContent === 'string') {
        // Attempt to parse, then fallback to paragraph wrapping
        let parsedSuccessfully = false;
        if (originalContent.trim().startsWith('[') && originalContent.trim().endsWith(']')) {
          try {
            const parsed = JSON.parse(originalContent);
            if (Array.isArray(parsed)) {
              originalContentForComparison = parsed as AppPartialBlock[];
              parsedSuccessfully = true;
            }
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          } catch (_e) { /* ignore, fallback */ }
        }
        if (!parsedSuccessfully) {
          originalContentForComparison = [
            {
              // id: `block-orig-${Date.now().toString()}-${Math.random().toString(36).substring(2, 7)}`, // id is optional for PartialBlock
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
        originalContentForComparison = originalContent as AppPartialBlock[];
      }
    }
    const hasContentChanged =
      JSON.stringify(currentContentToValidate) !==
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

    // Check for empty content before proceeding with save
    if (isEditorEmpty(currentContentToValidate)) {
      toast({
        title: 'Content cannot be empty',
        description: 'Please add some content to your card.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return; // Do not proceed with saving
    }

    const updatePayload: CardUpdatePayload = {};
    if (hasTitleChanged) updatePayload.title = title.trim();

    // Use currentContentToValidate for the payload if content has changed
    if (hasContentChanged && currentContentToValidate) {
      updatePayload.content = currentContentToValidate as AppPartialBlock[];
    }

    if (hasKeywordsChanged) updatePayload.tags = keywords;

    // console.log('Updating card with payload:', updatePayload); // This was the one we discussed keeping/removing based on preference

    // Ensure setIsSaving and setError(null) are correctly placed before the try block
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

      const updatedCardData = await response.json();
      // console.log('[CardDetail Page] handleSaveChanges - API response for updated card:', updatedCardData);

      if (response.ok && updatedCardData) {
        setCard(updatedCardData as KnowledgeCard); // This will trigger the useEffect
        setTitle(updatedCardData.title);
        setKeywords(
          updatedCardData.tags
            ? updatedCardData.tags.map((tag: Tag) => tag.name)
            : [],
        );
        setIsEditing(false);
        toast({
          title: 'Card updated successfully',
          status: 'success',
          duration: 3000,
        });
        // router.refresh(); // Keep this commented out for now
      } else {
        // Log the detailed validation errors if available
        if (updatedCardData?.details) {
          console.error('Validation Details:', updatedCardData.details);
        }
        const errorMsg =
          updatedCardData?.message ||
          updatedCardData?.error ||
          (updatedCardData?.details
            ? JSON.stringify(updatedCardData.details)
            : 'Failed to update card');
        throw new Error(errorMsg);
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
  let originalContentForComparisonCanSave: AppPartialBlock[] | undefined;
  if (card.content) {
    if (typeof card.content === 'string') {
      const trimmedContent = card.content.trim();
      // Attempt to parse, then fallback to paragraph wrapping
      let parsedSuccessfully = false;
      if (trimmedContent.startsWith('[') && trimmedContent.endsWith(']')) {
        try {
          const parsed = JSON.parse(trimmedContent);
          if (Array.isArray(parsed)) {
            originalContentForComparisonCanSave = parsed as AppPartialBlock[];
            parsedSuccessfully = true;
          }
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        } catch (_e) { /* ignore, fallback */ }
      }
      if (!parsedSuccessfully) {
        originalContentForComparisonCanSave = [
          {
            // id: `block-cansave-${Date.now().toString()}-${Math.random().toString(36).substring(2, 7)}`, // id is optional
            type: 'paragraph',
            props: {
              textColor: 'default',
              backgroundColor: 'default',
              textAlignment: 'left',
            },
            content: [{ type: 'text', text: trimmedContent, styles: {} }],
            children: [],
          },
        ];
      }
    } else {
      originalContentForComparisonCanSave = card.content as AppPartialBlock[];
    }
  }
  const contentChanged = editor
    ? JSON.stringify((editor as AppEditor)?.document) !==
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
          onSubmit={(_e) => {
            _e.preventDefault();
            handleSaveChanges();
          }}
        >
          <VStack spacing={6} align="stretch">
            <FormControl isRequired>
              <FormLabel htmlFor="title" fontFamily="'Open Sans', sans-serif" fontSize="20px">Title</FormLabel>
              <Input
                id="title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter card title"
                isDisabled={!isEditing || isSaving}
                fontFamily="'Open Sans', sans-serif"
                fontSize="18px"
              />
              {/* ADDED: Suggest Title Button and Display */}
              {isEditing && (
                <Box mt={2}>
                  <Button
                    size="sm"
                    onClick={handleSuggestTitle}
                    isLoading={isSuggestingTitle}
                    loadingText="Suggesting..."
                    colorScheme="purple"
                  >
                    Suggest Title with AI
                  </Button>
                  {suggestedTitle && !isSuggestingTitle && (
                    <Flex mt={2} align="center">
                      <Text mr={2} fontSize="sm">Suggested: &quot;{suggestedTitle}&quot;</Text>
                      <Button size="xs" colorScheme="teal" onClick={() => { setTitle(suggestedTitle); setSuggestedTitle(null); }}>
                        Use this title
                      </Button>
                    </Flex>
                  )}
                </Box>
              )}
            </FormControl>

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
                  <ChakraTag
                    key={keyword}
                    size="lg"
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
                  </ChakraTag>
                ))}
              </HStack>
              {/* ADDED: Suggest Keywords Button and Display */}
              {isEditing && (
                <Box mt={2}>
                  <Button
                    size="sm"
                    onClick={handleSuggestKeywords}
                    isLoading={isSuggestingKeywords}
                    loadingText="Suggesting..."
                    colorScheme="purple"
                  >
                    Suggest Keywords with AI
                  </Button>
                  {suggestedKeywords && suggestedKeywords.length > 0 && !isSuggestingKeywords && (
                    <Box mt={2}>
                      <Text fontSize="sm" mb={1}>Suggestions:</Text>
                      <HStack spacing={2} wrap="wrap" mb={2}>
                        {suggestedKeywords.map((kw) => (
                          <ChakraTag key={kw} borderRadius="full" variant="outline" colorScheme="blue">
                            <TagLabel>{kw}</TagLabel>
                          </ChakraTag>
                        ))}
                      </HStack>
                      <Button 
                        size="xs" 
                        colorScheme="teal" 
                        onClick={() => { 
                          const newKeywords = [...new Set([...keywords, ...suggestedKeywords])];
                          setKeywords(newKeywords); 
                          setSuggestedKeywords(null); 
                        }}
                      >
                        Add these keywords
                      </Button>
                       <Button 
                          size="xs" 
                          variant="outline"
                          ml={2}
                          colorScheme="gray" 
                          onClick={() => { 
                            setKeywords(suggestedKeywords); 
                            setSuggestedKeywords(null); 
                          }}
                        >
                          Replace with these
                        </Button>
                    </Box>
                  )}
                </Box>
              )}
            </FormControl>

            <FormControl isRequired>
              <FormLabel fontFamily="'Open Sans', sans-serif" fontSize="24px">
                Content
              </FormLabel>
              <Box borderWidth="1px" borderRadius="md" p={0} minH="500px">
                <BlockNoteEditorComponent
                  key={`editor-${editorKey}`}
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
                  <ChakraTag
                    key={tag.id}
                    size="lg"
                    borderRadius="md"
                    variant="solid"
                    colorScheme="teal"
                  >
                    <TagLabel>{tag.name}</TagLabel>
                  </ChakraTag>
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
              key={`editor-readonly-${editorKey}`}
              onEditorChange={handleEditorInstanceReady}
              onContentUpdate={handleEditorContentUpdate}
              editable={!isEditing}
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
          <AlertDialogContent as="form" onSubmit={(_e) => { _e.preventDefault(); handleDelete(); }}>
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
                type="button"
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
