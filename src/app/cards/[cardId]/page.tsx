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
  VStack,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalCloseButton,
  ModalBody,
  ModalFooter,
} from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';

import '@blocknote/mantine/style.css';
import {
  type AppEditor,
  type AppPartialBlock,
  // type AppInlineContent as _AppInlineContent, // Removed as unused
  // type AppInlineContentArray, // Removed as unused
} from '@/lib/blocknote/appSchema';
import type { ContentBlock } from '@/types/api/ai-service';
import {
  // extractTextFromInlineContent, // Removed as unused
  mapPartialBlocksToAIServiceContentBlocks,
  mapContentBlocksToPartialBlocks,
} from '../../../lib/contentUtils';

// Helper function to check if editor content is effectively empty
const isEditorEmpty = (
  blocks: AppPartialBlock[] | undefined | null,
): boolean => {
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
  content: AppPartialBlock[] | string | null;
  tags: Tag[];
  userId: string;
  folderId: string | null;
  createdAt: string;
  updatedAt: string;
  source_url?: string;
  source_type?: string;
}

interface CardUpdatePayload {
  title?: string;
  content?: AppPartialBlock[] | string | null;
  tags?: string[]; // This should be string[] as expected by the API endpoint body
}

// Component for side-by-side comparison (extracted for clarity, similar to NewCardPage)
const SideBySideComparisonModal = ({
  isOpen,
  onClose,
  originalContent,
  rewrittenContent,
  onAccept,
  onDiscard,
  isLoadingRewrite, // New prop
  errorOnRewrite, // New prop
  currentProgressMessageForModal, // ADDED prop for modal
  modalEditorKey, // ADDED prop for editor keys
}: {
  isOpen: boolean;
  onClose: () => void;
  originalContent: AppPartialBlock[] | null | undefined;
  rewrittenContent: AppPartialBlock[] | null | undefined;
  onAccept: () => void;
  onDiscard: () => void;
  isLoadingRewrite: boolean; // To show loading spinner on right side
  errorOnRewrite: string | null; // To show error on right side
  currentProgressMessageForModal: string | null; // ADDED prop for modal
  modalEditorKey: number; // ADDED prop for editor keys
}) => {
  if (!originalContent) return null; // Should not happen if modal is open based on originalContent presence

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="6xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent maxH="90vh">
        <ModalHeader>Compare Original and Rewritten Content</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <Flex direction={{ base: 'column', md: 'row' }} gap={4}>
            <Box
              flex={1}
              p={2}
              borderWidth="1px"
              borderRadius="md"
              overflowY="auto"
              maxH="70vh"
            >
              <Heading size="sm" mb={2}>
                Original Content
              </Heading>
              <BlockNoteEditorComponent
                key={`original-comparison-${modalEditorKey}`}
                initialContent={originalContent}
                editable={false}
                onEditorChange={() => {}}
                onContentUpdate={() => {}}
              />
            </Box>
            <Box
              flex={1}
              p={2}
              borderWidth="1px"
              borderRadius="md"
              overflowY="auto"
              maxH="70vh"
            >
              <Heading size="sm" mb={2}>
                AI Rewritten Content
              </Heading>
              {isLoadingRewrite ? (
                <Flex
                  justify="center"
                  align="center"
                  minH="200px"
                  direction="column"
                >
                  <Spinner size="xl" />
                  <Text mt={3}>AI Rewriting in progress...</Text>
                  <Text mt={1} fontSize="sm" color="gray.500">
                    {currentProgressMessageForModal || 'Initializing...'}
                  </Text>
                </Flex>
              ) : errorOnRewrite ? (
                <Flex
                  justify="center"
                  align="center"
                  minH="200px"
                  direction="column"
                >
                  <Text color="red.500" textAlign="center">
                    Rewrite Error: {errorOnRewrite}
                  </Text>
                  <Text
                    fontSize="sm"
                    color="gray.500"
                    mt={2}
                    textAlign="center"
                  >
                    You can close this window and try again.
                  </Text>
                </Flex>
              ) : rewrittenContent ? (
                <BlockNoteEditorComponent
                  key={`rewritten-comparison-${modalEditorKey}`}
                  initialContent={rewrittenContent}
                  editable={false} // This editor should also be non-editable
                  onEditorChange={() => {}}
                  onContentUpdate={() => {}}
                />
              ) : (
                <Flex justify="center" align="center" minH="200px">
                  <Text color="gray.500">Waiting for rewritten content...</Text>
                </Flex>
              )}
            </Box>
          </Flex>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onDiscard}>
            Discard Rewrite
          </Button>
          <Button
            colorScheme="green"
            onClick={onAccept}
            isDisabled={
              isLoadingRewrite || !!errorOnRewrite || !rewrittenContent
            }
          >
            Accept Rewritten Content
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

// const BlockNoteEditorViewer = dynamic(() => import("@/components/BlockNoteEditorViewer"), { ssr: false }); // REMOVED as unused

const POLLING_INTERVAL_MS_CARD_DETAIL = 3000;
const MAX_POLLING_ATTEMPTS_CARD_DETAIL = 60; // Approx 3 minutes (60 * 3s)

export default function CardDetailPage() {
  const { data: session, status } = useSession();
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
  // const [suggestedKeywords, setSuggestedKeywords] = useState<string[] | null>( // REMOVED OLD
  //   null,
  // );
  // const [isSuggestingKeywords, setIsSuggestingKeywords] = useState(false); // REMOVED OLD - will be replaced by isGeneratingKeywords

  // New state for simplified keyword generation
  const [isGeneratingKeywords, setIsGeneratingKeywords] = useState(false);
  const [keywordError, setKeywordError] = useState<string | null>(null);

  // ADDED: State for AI Content Rewrite
  const [isRewritingContent, setIsRewritingContent] = useState(false);
  const [rewrittenContentBlocks, setRewrittenContentBlocks] = useState<
    AppPartialBlock[] | null
  >(null);
  const [showSideBySideView, setShowSideBySideView] = useState(false);
  const [originalContentForComparison, setOriginalContentForComparison] =
    useState<AppPartialBlock[] | null>(null);

  // ADDED for asynchronous polling for AI Rewrite
  const [taskId, setTaskId] = useState<string | null>(null);
  const [pollingIntervalId, setPollingIntervalId] =
    useState<NodeJS.Timeout | null>(null);
  const [rewriteError, setRewriteError] = useState<string | null>(null); // Specific error state
  const [currentProgressMessage, setCurrentProgressMessage] = useState<
    string | null
  >(null); // ADDED

  const [pollingAttemptsRewrite, setPollingAttemptsRewrite] = useState(0);

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
            if (Array.isArray(parsed)) {
              // Basic check
              newInitialContent = parsed as AppPartialBlock[]; // Assume structure is correct if it parses to an array
              parsedSuccessfully = true;
            }
          } catch (_e) {
            console.warn(
              '[CardDetail Page] Failed to parse string content as JSON array, treating as plain text paragraph.',
              _e,
            );
          }
        }

        if (!parsedSuccessfully) {
          // If not a JSON array or parsing failed, treat as plain text in a paragraph
          newInitialContent = [
            {
              type: 'paragraph',
              content: [{ type: 'text', text: trimmedContent, styles: {} }], // Correctly typed content
            },
          ];
        }
      } else if (Array.isArray(card.content)) {
        newInitialContent = card.content as AppPartialBlock[];
      }
      // console.log('[CardDetail Page] Setting editorContentForInitialLoad:', newInitialContent);
      setEditorContentForInitialLoad(newInitialContent);
      setEditorContent(newInitialContent); // <<< FIX: Synchronize state on load
      if (card && card.updatedAt) {
        setEditorKey((prevKey) => prevKey + 1); // A simple increment, or use card.updatedAt
      }
    } else if (card) {
      // console.log('[CardDetail Page] Card content is null or undefined, setting editorContentForInitialLoad to undefined');
      setEditorContentForInitialLoad(undefined);
      setEditorContent(undefined); // <<< FIX: Synchronize state on load
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
    console.log(
      '[CardDetailPage] useEffect for fetchCard triggered. cardId:',
      cardId,
      'status:',
      status,
    );
    if (status === 'authenticated' && cardId) {
      fetchCard();
    } else if (status === 'unauthenticated') {
      router.push(`/api/auth/signin?callbackUrl=/cards/${cardId}`);
    }
    // fetchCard is stable due to useCallback, so only run when these change.
  }, [status, cardId, router, fetchCard]);

  // Keyword/Tag handling functions (copied from NewCardPage and adapted)
  // const handleKeywordChange = (e: React.ChangeEvent<HTMLInputElement>) => { // REMOVED OLD
  //   setCurrentKeyword(e.target.value);
  // };

  // const handleKeywordKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => { // REMOVED OLD
  //   if (e.key === 'Enter' && currentKeyword.trim() !== '') {
  //     e.preventDefault();
  //     const newKeyword = currentKeyword.trim().startsWith('#')
  //       ? currentKeyword.trim()
  //       : `#${currentKeyword.trim()}`;
  //     if (!keywords.includes(newKeyword)) {
  //       setKeywords([...keywords, newKeyword]);
  //     }
  //     setCurrentKeyword('');
  //   }
  // };

  // const removeKeyword = (keywordToRemove: string) => { // REMOVED OLD
  //   setKeywords(keywords.filter((keyword) => keyword !== keywordToRemove));
  // };

  // New handler for comma-separated keyword input
  const handleKeywordsInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const newKeywords = event.target.value
      .split(',')
      .map((kw) => kw.trim())
      .filter((kw) => kw !== '');
    setKeywords(newKeywords);
  };

  // ADDED: Handler for "Suggest Title"
  const handleSuggestTitle = async () => {
    if (!editor && !card?.content) {
      toast({
        title: 'No content available for title suggestion.',
        status: 'warning',
        duration: 3000,
      });
      return;
    }
    if (!card || !card.userId || !cardId) {
      toast({
        title: 'Card data not loaded.',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    let contentToProcess: AppPartialBlock[] | undefined = editorContent;
    if (!isEditing || !editorContent || editorContent.length === 0) {
      // Fallback to card.content if not editing or editorContent is empty
      if (card?.content) {
        if (typeof card.content === 'string') {
          // Correctly type the string content as a paragraph with text inline content
          contentToProcess = [
            {
              type: 'paragraph',
              content: [{ type: 'text', text: card.content, styles: {} }],
            },
          ];
        } else {
          // It's already AppPartialBlock[]
          contentToProcess = card.content as AppPartialBlock[];
        }
      }
    }

    if (!contentToProcess || contentToProcess.length === 0) {
      toast({
        title: 'Content is empty, cannot suggest title.',
        status: 'info',
        duration: 3000,
      });
      return;
    }

    const aiServiceContentBlocks = mapPartialBlocksToAIServiceContentBlocks(
      contentToProcess,
      card.userId,
      cardId,
    );

    if (aiServiceContentBlocks.length === 0) {
      toast({
        title: 'No processable content found for title suggestion.',
        status: 'info',
        duration: 3000,
      });
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
      toast({
        title: 'Title suggestion received!',
        status: 'success',
        duration: 3000,
      });
    } catch (err) {
      console.error('Suggest title error:', err);
      const message =
        err instanceof Error ? err.message : 'Could not suggest title.';
      toast({
        title: 'Error suggesting title',
        description: message,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsSuggestingTitle(false);
    }
  };

  // New handler for AI Keyword Generation Button Click
  const handleGenerateKeywordsAIClick = async () => {
    setIsGeneratingKeywords(true);
    setKeywordError(null);

    let contentToProcess: AppPartialBlock[] | undefined;
    if (isEditing && editorContent && !isEditorEmpty(editorContent)) {
      contentToProcess = editorContent;
    } else if (card?.content) {
      if (typeof card.content === 'string') {
        try {
          const parsed = JSON.parse(card.content);
          if (Array.isArray(parsed)) {
            contentToProcess = parsed as AppPartialBlock[];
          } else {
            contentToProcess = [
              {
                type: 'paragraph',
                content: [{ type: 'text', text: card.content, styles: {} }],
              },
            ];
          }
        } catch {
          contentToProcess = [
            {
              type: 'paragraph',
              content: [{ type: 'text', text: card.content, styles: {} }],
            },
          ];
        }
      } else {
        contentToProcess = card.content as AppPartialBlock[];
      }
    }

    if (isEditorEmpty(contentToProcess)) {
      setKeywordError('Cannot generate keywords: Content is empty.');
      setIsGeneratingKeywords(false);
      return;
    }

    const currentUserId = session?.user?.id || card?.userId;
    if (!currentUserId) {
      setKeywordError(
        'User information not available. Please ensure you are logged in or card data is loaded.',
      );
      setIsGeneratingKeywords(false);
      return;
    }

    const currentCardId = cardId || card?.id;
    if (!currentCardId) {
      setKeywordError('Card ID not available.');
      setIsGeneratingKeywords(false);
      return;
    }

    try {
      const aiServiceBlocks = mapPartialBlocksToAIServiceContentBlocks(
        contentToProcess || [],
        currentUserId,
        currentCardId,
      );

      const response = await fetch('/api/ai/generate-keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_blocks: aiServiceBlocks }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.message || 'Failed to generate keywords from API',
        );
      }

      const result = await response.json();
      setKeywords(result.suggested_keywords || []);
      toast({
        title: 'Keywords Suggested',
        description: 'AI has suggested keywords.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error: unknown) {
      console.error('Error generating keywords:', error);
      setKeywordError(
        error instanceof Error
          ? error.message
          : 'An unexpected error occurred while generating keywords.',
      );
      // setKeywords([]); // Decide if keywords should be cleared on error
    } finally {
      setIsGeneratingKeywords(false);
    }
  };

  // ADDED: Handler for "AI Rewrite Content"
  const handleRewriteContent = async () => {
    if (!card || !card.userId || !cardId) {
      toast({
        title: 'Card data not loaded.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    let contentToUseAsOriginal: AppPartialBlock[] | undefined;
    if (isEditing && editorContent && editorContent.length > 0) {
      contentToUseAsOriginal = editorContent;
    } else if (card.content) {
      if (typeof card.content === 'string') {
        try {
          const parsedContent = JSON.parse(card.content);
          if (Array.isArray(parsedContent)) {
            contentToUseAsOriginal = parsedContent as AppPartialBlock[];
          } else {
            contentToUseAsOriginal = [
              {
                type: 'paragraph',
                content: [{ type: 'text', text: card.content, styles: {} }],
              },
            ];
          }
        } catch {
          contentToUseAsOriginal = [
            {
              type: 'paragraph',
              content: [{ type: 'text', text: card.content, styles: {} }],
            },
          ];
        }
      } else {
        contentToUseAsOriginal = card.content as AppPartialBlock[];
      }
    }

    if (
      !contentToUseAsOriginal ||
      contentToUseAsOriginal.length === 0 ||
      isEditorEmpty(contentToUseAsOriginal)
    ) {
      toast({
        title: 'Current content is empty, cannot rewrite.',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    // Reset states for new rewrite operation
    setIsRewritingContent(true);
    setRewrittenContentBlocks(null);
    setOriginalContentForComparison(contentToUseAsOriginal); // Set for SBS view
    setShowSideBySideView(true); // Activate side-by-side mode immediately
    setRewriteError(null); // Clear previous rewrite errors
    setTaskId(null); // Reset task ID
    setPollingAttemptsRewrite(0); // Reset polling attempts
    if (pollingIntervalId) {
      // Clear any existing polling interval
      clearInterval(pollingIntervalId);
      setPollingIntervalId(null);
    }
    setCurrentProgressMessage('Initiating rewrite process...'); // ADDED initial message

    const aiServiceContentBlocks = mapPartialBlocksToAIServiceContentBlocks(
      contentToUseAsOriginal,
      card.userId,
      cardId,
    );

    if (aiServiceContentBlocks.length === 0) {
      toast({
        title: 'No processable content found for rewrite.',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      // Reset UI states if we bail early
      setIsRewritingContent(false);
      setShowSideBySideView(false);
      setOriginalContentForComparison(null);
      return;
    }

    try {
      const payload = {
        content_blocks_to_rewrite: aiServiceContentBlocks,
        document_metadata: {
          document_id: cardId,
          user_id: card.userId,
          source_identifier: card.source_url || cardId,
          source_type: card.source_type || 'knowledge_card',
          title: card.title,
        },
        user_id: card.userId,
      };

      console.log(
        '[CardDetailPage] handleRewriteContent: Sending payload to /api/ai/rewrite-content for task submission:',
        JSON.stringify(payload, null, 2),
      );

      const response = await fetch('/api/ai/rewrite-content', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.status === 202) {
        // Task submitted successfully
        const result = await response.json();
        if (result.task_id) {
          setTaskId(result.task_id);
          toast({
            title: 'Rewrite Task Submitted',
            description: `Task ID: ${result.task_id}. Polling for results...`,
            status: 'info',
            duration: 3000,
            isClosable: true,
          });
          // Polling will be handled by the useEffect hook watching `taskId`
          // setIsRewritingContent(true) is already set and polling will turn it off
        } else {
          // This case should ideally not happen if backend sends 202 correctly with task_id
          throw new Error(
            'Task ID not found in submission response despite 202 status.',
          );
        }
      } else {
        // Handle other non-202 responses as errors
        const errorData = await response
          .json()
          .catch(() => ({ message: `HTTP error ${response.status}` }));
        throw new Error(
          errorData.message ||
            `Error submitting rewrite task: ${response.statusText}`,
        );
      }
    } catch (err) {
      console.error('Error submitting rewrite task:', err);
      const message =
        err instanceof Error ? err.message : 'Could not submit rewrite task.';
      setRewriteError(message);
      toast({
        title: 'Submission Error',
        description: message,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      // Reset UI on submission error
      setIsRewritingContent(false);
      setShowSideBySideView(false);
      setOriginalContentForComparison(null);
      // No taskId set, so polling won't start
    }
    // The finally block that set setIsRewritingContent(false) is removed.
    // Loading state is now managed by the polling useEffect upon completion/failure/timeout.
  };

  // useEffect for polling AI Rewrite task status
  useEffect(() => {
    if (!taskId || !isRewritingContent) {
      if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        setPollingIntervalId(null);
      }
      return;
    }

    const intervalId = setInterval(async () => {
      let currentAttempt;
      setPollingAttemptsRewrite((prev) => {
        currentAttempt = prev + 1;
        return currentAttempt;
      });

      // Ensure currentAttempt is defined for the log, though it should be by the setter logic
      const attemptToLog = pollingAttemptsRewrite + 1;
      console.log(
        `[CardDetailPage] Polling AI rewrite task ${taskId}, Attempt: ${attemptToLog}`,
      );

      if (attemptToLog > MAX_POLLING_ATTEMPTS_CARD_DETAIL) {
        console.warn(
          `[CardDetailPage] Polling for task ${taskId} reached max attempts (${MAX_POLLING_ATTEMPTS_CARD_DETAIL}). Timing out.`,
        );
        clearInterval(intervalId);
        setPollingIntervalId(null);
        setIsRewritingContent(false);
        const timeoutMessage = `Rewrite process timed out after ${MAX_POLLING_ATTEMPTS_CARD_DETAIL} attempts. Please try again later.`;
        setRewriteError(timeoutMessage);
        toast({
          title: 'Rewrite Timed Out',
          description: timeoutMessage,
          status: 'error',
          duration: 7000,
          isClosable: true,
        });
        setCurrentProgressMessage('Polling timed out.');
        setPollingAttemptsRewrite(0);
        return; // Stop this interval callback
      }

      try {
        const response = await fetch(`/api/ai/rewrite-status/${taskId}`);
        if (!response.ok) {
          const errorData = await response
            .json()
            .catch(() => ({ message: `HTTP error ${response.status}` }));
          throw new Error(
            errorData.message ||
              `Failed to poll task status: HTTP ${response.status}`,
          );
        }
        const data = await response.json();
        console.log(
          `[CardDetailPage] Polling response for ${taskId}, attempt ${attemptToLog}:`,
          JSON.stringify(data, null, 2),
        );

        if (data.status === 'COMPLETED') {
          console.log(`[CardDetailPage] Task ${taskId} COMPLETED.`);
          if (
            data.ai_rewritten_content_blocks &&
            Array.isArray(data.ai_rewritten_content_blocks)
          ) {
            const editorFriendlyBlocks = mapContentBlocksToPartialBlocks(
              data.ai_rewritten_content_blocks as ContentBlock[],
            ) as AppPartialBlock[];
            setRewrittenContentBlocks(editorFriendlyBlocks);
            setCurrentProgressMessage(null);
            toast({
              title: 'Rewrite Complete!',
              description: 'Content has been rewritten.',
              status: 'success',
              duration: 5000,
              isClosable: true,
            });
          } else {
            setRewriteError(
              'Task completed, but rewritten content was not in the expected format.',
            );
            setCurrentProgressMessage(null);
            toast({
              title: 'Processing Error',
              description: 'Rewritten content is not in the expected format.',
              status: 'error',
              duration: 5000,
              isClosable: true,
            });
          }
          clearInterval(intervalId);
          setPollingIntervalId(null);
          setIsRewritingContent(false);
          setPollingAttemptsRewrite(0);
        } else if (data.status === 'FAILED') {
          console.error(
            `[CardDetailPage] Task ${taskId} FAILED: ${data.errorMessage}`,
          );
          setRewriteError(
            data.errorMessage || 'Rewrite task failed for an unknown reason.',
          );
          setCurrentProgressMessage(null);
          toast({
            title: 'Rewrite Failed',
            description: data.errorMessage || 'An unknown error occurred.',
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
          clearInterval(intervalId);
          setPollingIntervalId(null);
          setIsRewritingContent(false);
          setPollingAttemptsRewrite(0);
        } else if (data.status === 'PENDING' || data.status === 'PROCESSING') {
          setCurrentProgressMessage(
            data.progressStage || `Processing... (Status: ${data.status})`,
          );
        } else {
          console.warn(
            `[CardDetailPage] Task ${taskId} has unknown status: ${data.status}`,
          );
          setRewriteError(`Unknown status: ${data.status}. Polling...`);
          setCurrentProgressMessage(null);
          toast({
            title: 'Unknown Task Status',
            description: `Unknown status: ${data.status}. Polling...`,
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
          clearInterval(intervalId);
          setPollingIntervalId(null);
          setIsRewritingContent(false);
          setPollingAttemptsRewrite(0);
        }
      } catch (error) {
        console.error(`[CardDetailPage] Error polling task ${taskId}:`, error);
        setRewriteError(
          error instanceof Error
            ? error.message
            : 'An unknown error occurred during polling.',
        );
        toast({
          title: 'Polling Error',
          description:
            error instanceof Error
              ? error.message
              : 'Could not retrieve rewrite status.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        clearInterval(intervalId);
        setPollingIntervalId(null);
        setIsRewritingContent(false);
        setPollingAttemptsRewrite(0);
      }
    }, POLLING_INTERVAL_MS_CARD_DETAIL);

    setPollingIntervalId(intervalId);

    return () => {
      if (intervalId) clearInterval(intervalId);
      setPollingIntervalId(null);
    };
  }, [
    taskId,
    isRewritingContent,
    pollingAttemptsRewrite,
    toast,
    pollingIntervalId,
  ]); // Removed POLLING_INTERVAL_MS_CARD_DETAIL from deps as it's a const

  // ADDED: Handler to accept rewritten content
  const handleAcceptRewrite = () => {
    if (rewrittenContentBlocks && editor) {
      // Ensure main editor instance is available
      // Update the main editor's content directly
      // This assumes `editor` is the instance of the *main* BlockNote editor
      // We need to ensure `editorContent` and `editorContentForInitialLoad` are updated
      // and the editor is re-keyed if necessary to reflect the new content.

      setEditorContent(rewrittenContentBlocks);
      setEditorContentForInitialLoad(rewrittenContentBlocks); // This becomes the new baseline

      // Force re-initialization of the main editor when we switch back to single view
      setEditorKey((prev) => prev + 1);
    }
    setShowSideBySideView(false);
    setIsEditing(true); // Ensure we are in edit mode to save the accepted changes
    setRewrittenContentBlocks(null);
    setOriginalContentForComparison(null);
    toast({
      title: 'Rewritten content applied.',
      description: 'You can now save the card.',
      status: 'success',
      duration: 3000,
      isClosable: true,
    });
  };

  // ADDED: Handler to discard rewritten content
  const handleDiscardRewrite = () => {
    setShowSideBySideView(false);
    // If they were editing before, they remain editing. If not, switch to edit mode.
    setIsEditing(true);
    setRewrittenContentBlocks(null);
    setOriginalContentForComparison(null);
    toast({
      title: 'Rewrite discarded.',
      status: 'info',
      duration: 2000,
      isClosable: true,
    });
  };

  // --- Save Changes ---
  const handleSaveChanges = async () => {
    if (!editor || !card) return;

    // Use editorContent which is updated by onContentUpdate callback for the most current state.
    // Fallback to editor.document if editorContent is somehow not set, though it should be.
    const currentContentToValidate =
      editorContent || (editor as AppEditor)?.document;

    const originalContent = card.content;

    // Basic check for changes (more robust checks might compare JSON deeply)
    const hasTitleChanged = title.trim() !== card.title;
    // Normalize original content for comparison
    let originalContentForComparison: AppPartialBlock[] | undefined;
    if (originalContent) {
      if (typeof originalContent === 'string') {
        // Attempt to parse, then fallback to paragraph wrapping
        let parsedSuccessfully = false;
        if (
          originalContent.trim().startsWith('[') &&
          originalContent.trim().endsWith(']')
        ) {
          try {
            const parsed = JSON.parse(originalContent);
            if (Array.isArray(parsed)) {
              originalContentForComparison = parsed as AppPartialBlock[];
              parsedSuccessfully = true;
            }
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
          } catch (_e) {
            /* ignore, fallback */
          }
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
      JSON.stringify(keywords.map((kw) => kw.replace(/^#/, '')).sort()) !==
      JSON.stringify(
        originalTags.map((tag) => tag.name.replace(/^#/, '')).sort(),
      );

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

    if (hasKeywordsChanged)
      updatePayload.tags = keywords.map((kw) =>
        kw.startsWith('#') ? kw : `#${kw}`,
      ); // Ensure leading #

    // console.log('Updating card with payload:', updatePayload); // This was the one we discussed keeping/removing based on preference

    // Ensure setIsSaving and setError(null) are correctly placed before the try block
    setIsSaving(true);
    setError(null);

    // ---- START DIAGNOSTIC LOGS ----
    console.log('[handleSaveChanges] Diagnostic Info:');
    console.log('  hasTitleChanged:', hasTitleChanged);
    console.log('  hasKeywordsChanged:', hasKeywordsChanged);
    console.log('  hasContentChanged:', hasContentChanged);
    // For content, log the actual content being compared if it's not too verbose,
    // or at least their lengths or a hash if direct logging is too much.
    // For now, let's log stringified versions carefully.
    try {
      console.log(
        '  currentContentToValidate (first 200 chars):',
        JSON.stringify(currentContentToValidate)?.substring(0, 200),
      );
      console.log(
        '  originalContentForComparison (first 200 chars):',
        JSON.stringify(originalContentForComparison)?.substring(0, 200),
      );
    } catch (e) {
      console.warn('Error stringifying content for logging:', e);
    }
    console.log(
      '  Final updatePayload being sent:',
      JSON.stringify(updatePayload),
    );
    // ---- END DIAGNOSTIC LOGS ----

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
        } catch (_e) {
          /* ignore, fallback */
        }
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
          {showSideBySideView
            ? 'AI Content Rewrite Comparison'
            : isEditing
              ? 'Edit Knowledge Card'
              : card?.title || 'Card Details'}
        </Heading>
        <Spacer />

        {!showSideBySideView && (
          <>
            {isEditing ? (
              <>
                <Button
                  colorScheme="green"
                  onClick={handleSaveChanges}
                  isLoading={isSaving}
                  isDisabled={
                    !canSave || isSaving || isDeleting || isRewritingContent
                  }
                  mr={2}
                >
                  Save Changes
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setIsEditing(false);
                    if (card) {
                      setTitle(card.title);
                      setKeywords(
                        card.tags ? card.tags.map((tag) => tag.name) : [],
                      );
                      if (card.content) {
                        if (typeof card.content === 'string') {
                          try {
                            const parsed = JSON.parse(card.content);
                            if (Array.isArray(parsed))
                              setEditorContentForInitialLoad(
                                parsed as AppPartialBlock[],
                              );
                            else
                              setEditorContentForInitialLoad([
                                {
                                  type: 'paragraph',
                                  content: [
                                    {
                                      type: 'text',
                                      text: card.content,
                                      styles: {},
                                    },
                                  ],
                                },
                              ]);
                          } catch {
                            setEditorContentForInitialLoad([
                              {
                                type: 'paragraph',
                                content: [
                                  {
                                    type: 'text',
                                    text: card.content,
                                    styles: {},
                                  },
                                ],
                              },
                            ]);
                          }
                        } else {
                          setEditorContentForInitialLoad(
                            card.content as AppPartialBlock[],
                          );
                        }
                      } else {
                        setEditorContentForInitialLoad(undefined);
                      }
                      setEditorKey((prev) => prev + 1);
                    }
                  }}
                  isDisabled={isSaving || isDeleting || isRewritingContent}
                >
                  Cancel Edit
                </Button>
              </>
            ) : (
              <Button
                colorScheme="blue"
                onClick={() => setIsEditing(true)}
                isDisabled={isSaving || isDeleting || isRewritingContent}
                mr={2}
              >
                Edit Card
              </Button>
            )}
          </>
        )}

        {!showSideBySideView && card && (
          <Button
            size="sm"
            ml={2}
            colorScheme="orange"
            onClick={handleRewriteContent}
            isLoading={isRewritingContent}
            loadingText="Preparing Rewrite..."
            isDisabled={isRewritingContent || isSaving || isDeleting}
          >
            Rewrite with AI
          </Button>
        )}

        {!showSideBySideView && (
          <IconButton
            aria-label="Delete Card"
            icon={<DeleteIcon />}
            colorScheme="red"
            onClick={onAlertOpen}
            isLoading={isDeleting}
            isDisabled={isSaving || isDeleting || isRewritingContent}
            ml={isEditing ? 0 : 2}
          />
        )}
      </Flex>

      {showSideBySideView && card && originalContentForComparison ? (
        <Box>
          <Flex mb={4} justifyContent="center" gap={3}>
            <Button
              colorScheme="teal"
              onClick={handleAcceptRewrite}
              isLoading={isSaving}
            >
              Use This Rewrite
            </Button>
            <Button variant="outline" onClick={handleDiscardRewrite}>
              Discard Rewrite & Edit Original
            </Button>
          </Flex>

          <Flex direction={{ base: 'column', md: 'row' }} gap={6}>
            <Box flex={1}>
              <Heading size="md" mb={2} textAlign="center">
                Original Content
              </Heading>
              <Box
                borderWidth="1px"
                borderRadius="md"
                p={1}
                minH={{ base: '300px', md: '500px' }}
                bg="gray.50"
              >
                <BlockNoteEditorComponent
                  key={`editor-original-sbs-${editorKey}`}
                  editable={false}
                  initialContent={originalContentForComparison}
                  onEditorChange={() => {}}
                />
              </Box>
            </Box>

            <Box flex={1}>
              <Heading size="md" mb={2} textAlign="center">
                AI Rewritten Suggestion
              </Heading>
              <Box
                borderWidth="1px"
                borderRadius="md"
                p={1}
                minH={{ base: '300px', md: '500px' }}
                display="flex"
                flexDirection="column"
                justifyContent="center"
                alignItems="center"
                bg="gray.50"
              >
                {isRewritingContent ? (
                  <Flex
                    direction="column"
                    align="center"
                    justify="center"
                    h="100%"
                  >
                    <Spinner size="xl" />
                    <Text mt={4}>Rewriting content...</Text>
                  </Flex>
                ) : rewrittenContentBlocks ? (
                  <BlockNoteEditorComponent
                    key={`editor-rewritten-sbs-${editorKey}`}
                    editable={false}
                    initialContent={rewrittenContentBlocks}
                    onEditorChange={() => {}}
                  />
                ) : (
                  <Text color="gray.500">
                    Rewritten content will appear here.
                  </Text>
                )}
              </Box>
            </Box>
          </Flex>
          <Flex mt={4} justifyContent="center" gap={3}>
            <Button
              colorScheme="teal"
              onClick={handleAcceptRewrite}
              isLoading={isSaving}
            >
              Use This Rewrite
            </Button>
            <Button variant="outline" onClick={handleDiscardRewrite}>
              Discard Rewrite & Edit Original
            </Button>
          </Flex>
        </Box>
      ) : isEditing ? (
        <Box
          as="form"
          onSubmit={(e: React.FormEvent) => {
            e.preventDefault();
            handleSaveChanges();
          }}
        >
          <VStack spacing={6} align="stretch">
            <FormControl isRequired>
              <FormLabel
                htmlFor="title"
                fontFamily="'Open Sans', sans-serif"
                fontSize="20px"
              >
                Title
              </FormLabel>
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
              {isEditing && (
                <HStack mt={2} spacing={2}>
                  <Button
                    size="sm"
                    onClick={handleSuggestTitle}
                    isLoading={isSuggestingTitle}
                    isDisabled={
                      isSuggestingTitle ||
                      !isEditing ||
                      isSaving ||
                      showSideBySideView
                    }
                  >
                    Suggest Title
                  </Button>
                  {suggestedTitle && (
                    <Button
                      size="sm"
                      colorScheme="teal"
                      variant="outline"
                      onClick={() => {
                        setTitle(suggestedTitle);
                        setSuggestedTitle(null);
                      }}
                      isDisabled={!isEditing || isSaving}
                    >
                      Apply: &quot;{suggestedTitle.substring(0, 30)}
                      {suggestedTitle.length > 30 ? '...' : ''}&quot;
                    </Button>
                  )}
                </HStack>
              )}
            </FormControl>

            <FormControl mt={4}>
              <FormLabel
                htmlFor="keywords-input"
                fontFamily="'Open Sans', sans-serif"
                fontSize="24px"
              >
                Keywords
                <Text as="span" fontSize="16px" color="gray.500" ml={2}>
                  (Optional, comma-separated)
                </Text>
              </FormLabel>
              <Text fontSize="sm" color="gray.500" mb={2}>
                Enter keywords manually (e.g., tech, ai, productivity) or let AI
                suggest them.
              </Text>
              <Input
                id="keywords-input"
                type="text"
                value={keywords.join(', ')}
                onChange={handleKeywordsInputChange}
                placeholder="e.g., artificial intelligence, machine learning, productivity"
                mb={2}
                isDisabled={isGeneratingKeywords || isSaving || !isEditing}
                fontFamily="'Open Sans', sans-serif"
                fontSize="16px"
              />
              <Button
                onClick={handleGenerateKeywordsAIClick}
                isLoading={isGeneratingKeywords}
                loadingText="Generating..."
                colorScheme="blue"
                variant="outline"
                size="sm"
                isDisabled={isSaving || !isEditing || isGeneratingKeywords}
              >
                Suggest Keywords with AI
              </Button>
              {keywordError && (
                <Text color="red.500" mt={1} fontSize="sm">
                  Error: {keywordError}
                </Text>
              )}
            </FormControl>

            <FormControl isRequired>
              <FormLabel fontFamily="'Open Sans', sans-serif" fontSize="24px">
                Content
              </FormLabel>
              <Box borderWidth="1px" borderRadius="md" p={0} minH="500px">
                {isEditing ? (
                  <BlockNoteEditorComponent
                    key={`editor-main-editing-${editorKey}`}
                    onEditorChange={handleEditorInstanceReady}
                    onContentUpdate={handleEditorContentUpdate}
                    editable={true}
                    initialContent={editorContentForInitialLoad}
                  />
                ) : (
                  <BlockNoteEditorComponent
                    key={card.id}
                    initialContent={
                      card.content
                        ? typeof card.content === 'string'
                          ? JSON.parse(card.content)
                          : card.content
                        : undefined
                    }
                    editable={false}
                    onEditorChange={() => {}}
                  />
                )}
              </Box>
            </FormControl>
          </VStack>
        </Box>
      ) : (
        <Box>
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
              key={card.id}
              initialContent={
                card.content
                  ? typeof card.content === 'string'
                    ? JSON.parse(card.content)
                    : card.content
                  : undefined
              }
              editable={false}
              onEditorChange={() => {}}
            />
          </Box>
        </Box>
      )}

      <AlertDialog
        isOpen={isAlertOpen}
        leastDestructiveRef={cancelRef}
        onClose={onAlertClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent
            as="form"
            onSubmit={(e: React.FormEvent) => {
              e.preventDefault();
              handleDelete();
            }}
          >
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

      {/* Use the extracted SideBySideComparisonModal component */}
      <SideBySideComparisonModal
        isOpen={showSideBySideView}
        onClose={() => {
          // If closing the modal manually (e.g. Escape key or close button)
          // treat it like a discard if a rewrite was in progress or completed.
          if (isRewritingContent || rewrittenContentBlocks) {
            handleDiscardRewrite(); // This already sets showSideBySideView to false
          } else {
            setShowSideBySideView(false);
          }
        }}
        originalContent={originalContentForComparison}
        rewrittenContent={rewrittenContentBlocks}
        onAccept={handleAcceptRewrite}
        onDiscard={handleDiscardRewrite}
        isLoadingRewrite={isRewritingContent}
        errorOnRewrite={rewriteError}
        currentProgressMessageForModal={currentProgressMessage}
        modalEditorKey={editorKey}
      />
    </Container>
  );
}
