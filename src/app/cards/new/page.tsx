'use client';

import React, { useState, FormEvent, useCallback, useEffect } from 'react';
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
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
} from '@chakra-ui/react';
import {
  BlockNoteEditor as BlockNoteEditorType,
  PartialBlock,
} from '@blocknote/core';
import '@blocknote/mantine/style.css';
import { type AppPartialBlock } from '@/lib/blocknote/appSchema';
import { useStagingCardStore } from '@/stores/stagingCardStore';
import {
  mapPartialBlocksToAIServiceContentBlocks,
  mapContentBlocksToPartialBlocks,
} from '@/lib/contentUtils';
import { v4 as uuidv4 } from 'uuid';
import type { TaskStatusResponse } from '@/types/api/ai-service';

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
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  const toast = useToast();

  // Client-side generated document ID for a new card
  const [clientSideDocumentId] = useState(() => uuidv4());

  const {
    stagedTitle,
    stagedContentBlocks,
    stagedKeywords: initialStagedKeywords,
    error: stagingError,
    clearData: clearStagingData,
    isLoading: isStagingLoading,
  } = useStagingCardStore();

  const [title, setTitle] = useState('');
  const [_editor, setEditor] = useState<BlockNoteEditorType | null>(null);
  const [editorContent, setEditorContent] = useState<
    AppPartialBlock[] | undefined
  >(undefined);
  const [editorKey, setEditorKey] = useState(Date.now());

  // Keyword states
  const [keywords, setKeywords] = useState<string[]>([]);
  const [isGeneratingKeywords, setIsGeneratingKeywords] = useState(false);
  const [keywordError, setKeywordError] = useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);

  // State for AI suggestions (Title only now for this section)
  const [suggestedTitle, setSuggestedTitle] = useState<string | null>(null);
  const [isSuggestingTitle, setIsSuggestingTitle] = useState(false);

  // New state variables for AI Rewrite functionality
  const [originalEditorContent, setOriginalEditorContent] = useState<
    AppPartialBlock[] | undefined
  >(undefined);
  const [rewrittenEditorContent, setRewrittenEditorContent] = useState<
    AppPartialBlock[] | undefined
  >(undefined);
  const [isRewritingContent, setIsRewritingContent] = useState(false);
  const [rewriteError, setRewriteError] = useState<string | null>(null);
  const [displayMode, setDisplayMode] = useState<'original' | 'rewritten'>(
    'original',
  );
  const [showComparisonView, setShowComparisonView] = useState(false);

  // Unified state for asynchronous tasks
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [currentProgressMessage, setCurrentProgressMessage] = useState<
    string | null
  >(null);

  const [
    hasShownInitialContentReadyToast,
    setHasShownInitialContentReadyToast,
  ] = useState(false);

  const POLLING_INTERVAL_MS = 2000; // 2 seconds

  useEffect(() => {
    console.log(
      '[NewCardPage Staging useEffect] Running. Initial StagedTitle:',
      stagedTitle,
    );
    console.log(
      '[NewCardPage Staging useEffect] Initial StagedContentBlocks present:',
      !!stagedContentBlocks && stagedContentBlocks.length > 0,
    );
    console.log(
      '[NewCardPage Staging useEffect] Initial initialStagedKeywords from store:',
      initialStagedKeywords,
    );
    console.log(
      '[NewCardPage Staging useEffect] hasShownInitialContentReadyToast state at start:',
      hasShownInitialContentReadyToast,
    );

    let processedNewDataInThisRun = false;
    let titleToUse: string | null = null;
    let autoExtractedTitleValue: string | null = null;

    if (
      !stagedTitle &&
      !stagedContentBlocks &&
      (!initialStagedKeywords || initialStagedKeywords.length === 0)
    ) {
      if (hasShownInitialContentReadyToast) {
        console.log(
          '[NewCardPage Staging useEffect] No staged data found, resetting hasShownInitialContentReadyToast to false.',
        );
        setHasShownInitialContentReadyToast(false);
      }
    }

    if (stagedTitle) {
      titleToUse = stagedTitle;
      autoExtractedTitleValue = stagedTitle; // Store it to check against final title
      processedNewDataInThisRun = true;
    }

    if (stagedContentBlocks && stagedContentBlocks.length > 0) {
      const editorFriendlyBlocks = mapContentBlocksToPartialBlocks(
        stagedContentBlocks,
      ) as AppPartialBlock[];
      setOriginalEditorContent(editorFriendlyBlocks);
      setEditorContent(editorFriendlyBlocks);
      setEditorKey(Date.now()); // Force re-render of editor if content changes
      processedNewDataInThisRun = true;

      if (!stagedTitle) {
        // Only auto-extract title if not already provided
        const firstTextBlock = editorFriendlyBlocks.find(
          (block) =>
            block.type === 'paragraph' &&
            block.content &&
            block.content.length > 0,
        ) as AppPartialBlock | undefined;

        if (firstTextBlock && firstTextBlock.content) {
          let extractedText = '';
          if (typeof firstTextBlock.content === 'string') {
            extractedText = firstTextBlock.content;
          } else if (Array.isArray(firstTextBlock.content)) {
            extractedText = firstTextBlock.content
              .map((inline) =>
                typeof inline === 'string'
                  ? inline
                  : inline.type === 'text'
                    ? inline.text
                    : '',
              )
              .join('');
          }
          autoExtractedTitleValue = extractedText.substring(0, 100);
          if (autoExtractedTitleValue) titleToUse = autoExtractedTitleValue;
          console.log(
            '[NewCardPage Staging useEffect] Auto-extracted title from content:',
            autoExtractedTitleValue,
          );
        } else {
          console.log(
            '[NewCardPage Staging useEffect] No suitable first text block found for auto-title extraction.',
          );
        }
      }
    } else if (
      stagedTitle ||
      (initialStagedKeywords && initialStagedKeywords.length > 0)
    ) {
      setOriginalEditorContent(undefined);
      setEditorContent(undefined);
      setEditorKey(Date.now()); // Also refresh editor if only title/keywords are staged
      // titleToUse is already set if stagedTitle exists
      if (initialStagedKeywords && initialStagedKeywords.length > 0)
        processedNewDataInThisRun = true;
    } else {
      // No content blocks, no title from staging, no keywords from staging
      // Retain current editor content or clear it if that's desired behavior when staging is empty
      // For now, doing nothing to local editor content if no new content is staged.
    }

    if (titleToUse) {
      setTitle(titleToUse);
    }

    if (initialStagedKeywords && initialStagedKeywords.length > 0) {
      setKeywords(
        initialStagedKeywords.map((kw) => (kw.startsWith('#') ? kw : `#${kw}`)),
      );
      processedNewDataInThisRun = true;
    }

    if (processedNewDataInThisRun && !hasShownInitialContentReadyToast) {
      toast({
        title: 'Ready to Edit',
        description: 'Your content has been loaded into the editor.',
        status: 'success',
        duration: 4000,
        isClosable: true,
      });
      setHasShownInitialContentReadyToast(true);
    }

    if (stagingError) {
      toast({
        title: 'Error During Previous Step',
        description: stagingError,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [
    stagedTitle,
    stagedContentBlocks,
    initialStagedKeywords,
    stagingError,
    clearStagingData, // From store, include if its identity can change or if effect calls it
    toast,
    setTitle,
    setOriginalEditorContent,
    setEditorContent,
    setEditorKey,
    setKeywords,
    hasShownInitialContentReadyToast, // state variable used in logic
    setHasShownInitialContentReadyToast, // setter for the above
  ]);

  // New useEffect for component unmount cleanup
  useEffect(() => {
    return () => {
      console.log('[NewCardPage onTrueUnmount] Clearing staged data.');
      clearStagingData();
    };
  }, [clearStagingData]);

  const handleEditorInstanceReady = useCallback(
    (editorInstance: BlockNoteEditorType | null) => {
      setEditor(editorInstance);
    },
    [],
  );

  const handleEditorContentUpdate = useCallback(
    (blocks: PartialBlock[]) => {
      if (!showComparisonView) {
        const appBlocks = blocks as AppPartialBlock[];
        setEditorContent(appBlocks);
        if (
          JSON.stringify(appBlocks) === JSON.stringify(rewrittenEditorContent)
        ) {
          setDisplayMode('rewritten');
        } else {
          setDisplayMode('original');
        }
      }
    },
    [showComparisonView, rewrittenEditorContent],
  );

  // This is the primary function for handling content rewrites.
  const handleRewriteContent = async () => {
    // 1. Check for content
    if (isEditorEmpty(editorContent)) {
      toast({
        title: 'Content is empty',
        description: 'Please add some content before rewriting.',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    if (!session?.user?.id) {
      toast({
        title: 'User not authenticated',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    // 2. Set up UI states for rewrite
    setIsRewritingContent(true);
    setRewriteError(null);
    setRewrittenEditorContent(undefined); // Clear previous rewrites
    setOriginalEditorContent(editorContent);
    setCurrentProgressMessage('Initiating rewrite...');
    setShowComparisonView(true); // Show the comparison modal immediately

    // 3. Prepare and dispatch the task
    try {
      if (!editorContent) return; // Should be caught by isEditorEmpty, but for TS safety
      const aiServiceContentBlocks = mapPartialBlocksToAIServiceContentBlocks(
        editorContent,
        session.user.id,
        clientSideDocumentId,
      );

      const payload = {
        content_blocks_to_rewrite: aiServiceContentBlocks,
        document_metadata: {
          document_id: clientSideDocumentId,
          user_id: session.user.id,
          source_identifier: 'new-card-creation',
          source_type: 'knowledge_card',
          title: title, // Send current title
        },
        user_id: session.user.id,
      };

      const response = await fetch('/api/ai/rewrite-content', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.message || 'Failed to dispatch rewrite task.',
        );
      }

      const result = await response.json();
      if (result.task_id) {
        setCurrentTaskId(result.task_id);
        toast({
          title: 'Rewrite task submitted',
          description: 'The AI is working on it. Please wait.',
          status: 'info',
          duration: 3000,
        });
      } else {
        throw new Error('Did not receive a task ID from the server.');
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'An unexpected error occurred.';
      setRewriteError(message);
      setIsRewritingContent(false);
      setCurrentProgressMessage(null);
      toast({
        title: 'Error Submitting Task',
        description: message,
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleUseOriginalFromComparison = () => {
    // The original content is already in the main editor state,
    // so we just need to exit the comparison view.
    setShowComparisonView(false);
    setRewrittenEditorContent(undefined); // Clear the rewritten content
    setOriginalEditorContent(undefined); // Clear the comparison original
    setIsRewritingContent(false); // Ensure loading state is off
    setCurrentTaskId(null); // Stop any polling
  };

  // This is for when the user clicks 'Use Rewritten Content' in the comparison modal.
  const handleUseRewrittenFromComparison = () => {
    if (rewrittenEditorContent) {
      setEditorContent(rewrittenEditorContent);
      setEditorKey(Date.now()); // Force re-render of the editor with new content
      toast({
        title: 'Content Updated',
        description: 'The rewritten content is now in the editor.',
        status: 'success',
        duration: 3000,
      });
    }
    setShowComparisonView(false);
    setRewrittenEditorContent(undefined);
    setOriginalEditorContent(undefined);
    setIsRewritingContent(false); // Ensure loading state is off
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    toast.closeAll();

    if (!session?.user?.id) {
      toast({
        title: 'Error',
        description: 'You must be signed in to create a card.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    if (!_editor) {
      toast({
        title: 'Error',
        description: 'Editor is not ready. Please wait a moment and try again.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    if (!title.trim()) {
      toast({
        title: 'Error',
        description: 'Title is required.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    // Get the full, structured content directly from the editor instance.
    // This is the correct format for the API.
    const contentToSave = _editor.document;

    if (isEditorEmpty(contentToSave)) {
      toast({
        title: 'Error',
        description: 'Content is required.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    const payload = {
      title: title.trim(),
      content: contentToSave, // Use the correct, full content from the editor
      tags: keywords,
      // folderId: null, // folderId can be added here if needed
    };

    try {
      const response = await fetch('/api/cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData: CreateCardErrorResponse = await response.json();
        const errorMessage =
          errorData.error ||
          errorData.message ||
          'An unknown error occurred.';
        console.error('Failed to create card:', errorData.details || errorData);
        toast({
          title: 'Error creating card',
          description: `Server responded with: ${errorMessage}`,
          status: 'error',
          duration: 9000,
          isClosable: true,
        });
      } else {
        const successData: CreateCardSuccessResponse = await response.json();
        toast({
          title: 'Card created successfully!',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        clearStagingData(); // Clear staging store on successful save
        router.push(`/cards/${successData.id}`);
      }
    } catch (error) {
      console.error('Network or other error:', error);
      toast({
        title: 'An unexpected error occurred',
        description: error instanceof Error ? error.message : String(error),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSuggestTitle = async () => {
    toast({
      title: 'DEBUG: handleSuggestTitle fired!',
      status: 'info',
      duration: 2000,
    });
    // Check if editor content is available and not empty
    if (isEditorEmpty(editorContent)) {
      toast({
        title: 'Content is empty',
        description: 'Please add some content before suggesting a title.',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    if (!session?.user?.id) {
      toast({
        title: 'Error',
        description: 'User not authenticated.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsSuggestingTitle(true);
    setSuggestedTitle(null);
    setCurrentProgressMessage('Sending content to AI for title suggestion...');

    try {
      if (!editorContent) {
        throw new Error('Editor content is not available.');
      }
      const aiServiceContentBlocks = mapPartialBlocksToAIServiceContentBlocks(
        editorContent,
        session.user.id,
        clientSideDocumentId, // Use the client-side generated UUID
      );

      if (aiServiceContentBlocks.length === 0) {
        toast({
          title: 'No processable content found for title suggestion.',
          status: 'info',
          duration: 3000,
        });
        setIsSuggestingTitle(false);
        return;
      }

      const response = await fetch('/api/ai/generate-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content_blocks: aiServiceContentBlocks,
        }),
      });

      const data = await response.json();

      if (!response.ok || data.error) {
        throw new Error(data.error || 'Failed to dispatch title generation task.');
      }

      if (data.taskId) {
        setCurrentTaskId(data.taskId);
        setCurrentProgressMessage('Title generation task started...');
        toast({
          title: 'Title suggestion initiated',
          description: 'The AI is generating a title. Please wait.',
          status: 'info',
          duration: 3000,
        });
      } else {
        throw new Error('Did not receive a task ID from the server.');
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'An unexpected error occurred.';
      toast({
        title: 'Error suggesting title',
        description: message,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsSuggestingTitle(false); // Stop loading on dispatch error
      setCurrentProgressMessage(null);
    }
  };

  const applySuggestedTitle = () => {
    if (suggestedTitle) {
      setTitle(suggestedTitle);
      setSuggestedTitle(null);
    }
  };

  const handleKeywordsInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const newKeywords = event.target.value
      .split(',')
      .map((kw) => kw.trim())
      .filter((kw) => kw !== '');
    setKeywords(newKeywords);
  };

  const handleGenerateKeywordsAIClick = async () => {
    if (sessionStatus !== 'authenticated' || !session?.user?.id) {
      toast({
        title: 'Authentication Required',
        description: 'You must be logged in to suggest keywords.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    const contentToProcess =
      displayMode === 'rewritten' && rewrittenEditorContent
        ? rewrittenEditorContent
        : editorContent;

    if (!contentToProcess || isEditorEmpty(contentToProcess)) {
      setKeywordError('Cannot generate keywords: Content is empty.');
      toast({
        title: 'Content Required',
        description: 'Cannot generate keywords for empty content.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsGeneratingKeywords(true);
    setKeywordError(null);

    try {
      const aiServiceBlocks = mapPartialBlocksToAIServiceContentBlocks(
        contentToProcess,
        session.user.id,
      );

      if (aiServiceBlocks.length === 0) {
        throw new Error('No processable content found for keyword generation.');
      }

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
    } finally {
      setIsGeneratingKeywords(false);
    }
  };

  // Unified polling useEffect for all async tasks
  useEffect(() => {
    if (!currentTaskId) {
      return;
    }

    const intervalId = setInterval(async () => {
      try {
        const res = await fetch(`/api/tasks/${currentTaskId}/status`);
        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(
            errorData.error || `Failed to fetch task status: ${res.status}`,
          );
        }

        const data: TaskStatusResponse = await res.json();

        if (data.progressMessage) {
          setCurrentProgressMessage(data.progressMessage);
        }
        
        console.log('[NewCardPage Polling] Received data:', JSON.stringify(data, null, 2));

        if (data.status === 'SUCCESS') {
          clearInterval(intervalId);
          setCurrentProgressMessage(null);
          setCurrentTaskId(null);

          console.log('[NewCardPage Polling] Task SUCCESS. Task type:', data.task_type);

          if (data.task_type === 'GENERATE_TITLE') {
            console.log('[NewCardPage Polling] Handling generate_title completion. Result object:', data.result);
            
            let resultData = data.result;
            if (typeof resultData === 'string') {
              try {
                resultData = JSON.parse(resultData);
              } catch (e) {
                console.error('Error parsing task result:', e);
                resultData = null;
              }
            }

            const newTitle = resultData?.generated_title;
            console.log('[NewCardPage Polling] Extracted title:', newTitle);
            if (newTitle) {
              setSuggestedTitle(newTitle);
              toast({
                title: 'Title suggestion received!',
                status: 'success',
                duration: 3000,
              });
            } else {
               console.error('[NewCardPage Polling] Title was not found in the result object.');
                toast({
                title: 'Error processing title',
                description: 'The AI task completed, but a title was not returned.',
                status: 'error',
                duration: 5000,
              });
            }
            setIsSuggestingTitle(false);
          } else if (
            data.task_type === 'rewrite_content' &&
            data.result?.content_blocks
          ) {
            const editorFriendlyBlocks = mapContentBlocksToPartialBlocks(
              data.result.content_blocks,
            );
            setRewrittenEditorContent(editorFriendlyBlocks);
            setIsRewritingContent(false);
            toast({
              title: 'Rewrite Complete!',
              description: 'You can now compare the content.',
              status: 'success',
              duration: 5000,
            });
          }
          // Handle other task types like keywords if they become async
        } else if (data.status === 'FAILED') {
          clearInterval(intervalId);
          const finalErrorMessage = data.error || 'An unknown error occurred.';
          toast({
            title: 'Task Failed',
            description: finalErrorMessage,
            status: 'error',
            duration: 5000,
          });

          // Reset relevant loading states based on task type
          if (data.task_type === 'generate_title') {
            setIsSuggestingTitle(false);
          } else if (data.task_type === 'rewrite_content') {
            setRewriteError(finalErrorMessage);
            setIsRewritingContent(false);
          }
          setCurrentProgressMessage(null);
          setCurrentTaskId(null);
        }
      } catch (error) {
        clearInterval(intervalId);
        const errorMessage =
          error instanceof Error
            ? error.message
            : 'An unknown error occurred during polling.';
        toast({
          title: 'Polling Error',
          description: errorMessage,
          status: 'error',
          duration: 5000,
        });
        // Reset all loading states on polling failure
        setIsSuggestingTitle(false);
        setIsRewritingContent(false);
        setRewriteError(errorMessage);
        setCurrentProgressMessage(null);
        setCurrentTaskId(null);
      }
    }, POLLING_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [currentTaskId, toast]);

  if (sessionStatus === 'loading' || isStagingLoading) {
    return (
      <Flex justify="center" align="center" minH="100vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (sessionStatus === 'unauthenticated') {
    // Should be handled by middleware or a higher-order component, but good to have a fallback
    router.push('/api/auth/signin');
    return null; // Render nothing while redirecting
  }

  // Display a loading spinner if data is being staged (e.g. if navigation happened before staging store finished an async op)
  // This is a fallback; ideally, navigation only occurs after staging store is not loading.
  if (isStagingLoading && !stagedTitle && !stagedContentBlocks) {
    // Only show if not yet populated
    return (
      <Flex justify="center" align="center" minH="100vh">
        <Spinner size="xl" />
        <Text ml={3}>Loading Content...</Text>
      </Flex>
    );
  }

  return (
    <Container maxW="container.lg" py={8}>
      <Heading mb={6}>Create New Knowledge Card</Heading>
      <form onSubmit={handleSubmit}>
        <VStack spacing={6} align="stretch">
          <FormControl isRequired>
            <FormLabel htmlFor="title">Title</FormLabel>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter card title"
              isDisabled={isSubmitting || isStagingLoading}
            />
            <HStack mt={2} spacing={2}>
              <Button
                size="sm"
                onClick={handleSuggestTitle}
                isLoading={isSuggestingTitle}
                disabled={
                  isSuggestingTitle ||
                  !_editor ||
                  isEditorEmpty(editorContent)
                }
              >
                Suggest Title
              </Button>
              {suggestedTitle && (
                <Button
                  size="sm"
                  colorScheme="teal"
                  variant="outline"
                  onClick={applySuggestedTitle}
                >
                  Apply: &quot;{suggestedTitle.substring(0, 30)}
                  {suggestedTitle.length > 30 ? '...' : ''}&quot;
                </Button>
              )}
            </HStack>
          </FormControl>

          <FormControl mt={4}>
            <FormLabel htmlFor="keywords-input">
              Keywords
              <Text as="span" fontSize="sm" color="gray.500" ml={2}>
                (Optional, comma-separated)
              </Text>
            </FormLabel>
            <Input
              id="keywords-input"
              type="text"
              value={keywords.join(', ')}
              onChange={handleKeywordsInputChange}
              placeholder="e.g., ai, productivity, learning"
              mb={2}
              isDisabled={isGeneratingKeywords || isSubmitting}
            />
            <Button
              onClick={handleGenerateKeywordsAIClick}
              isLoading={isGeneratingKeywords}
              loadingText="Generating..."
              colorScheme="blue"
              variant="outline"
              size="sm"
              isDisabled={isSubmitting || isGeneratingKeywords}
            >
              Suggest Keywords with AI
            </Button>
            {keywordError && (
              <Text color="red.500" mt={1} fontSize="sm">
                Error: {keywordError}
              </Text>
            )}
          </FormControl>

          <FormControl mt={4}>
            <FormLabel>Content</FormLabel>
            <HStack mt={0} mb={2} spacing={2} justify="flex-start">
              <Button
                size="sm"
                onClick={handleRewriteContent}
                isLoading={isRewritingContent && !showComparisonView}
                colorScheme="purple"
                isDisabled={showComparisonView || isRewritingContent}
              >
                AI Rewrite Content (Beta)
              </Button>
            </HStack>
            <Box
              border="1px solid"
              borderColor="gray.200"
              borderRadius="md"
              p={1}
              minH="300px"
            >
              <BlockNoteEditorComponent
                key={editorKey}
                initialContent={editorContent}
                onContentUpdate={handleEditorContentUpdate}
                onEditorChange={handleEditorInstanceReady}
                editable={true}
              />
            </Box>
            <HStack mt={2} spacing={2} justify="space-between">
              <HStack>
                <Button
                  size="sm"
                  onClick={handleRewriteContent}
                  isLoading={isRewritingContent && !showComparisonView}
                  colorScheme="purple"
                  isDisabled={showComparisonView || isRewritingContent}
                >
                  AI Rewrite Content (Beta)
                </Button>
              </HStack>
            </HStack>
            {rewriteError && (
              <Text color="red.500" mt={1} fontSize="sm">
                Rewrite Error: {rewriteError}
              </Text>
            )}
          </FormControl>
          <Button
            mt={6}
            colorScheme="blue"
            type="submit"
            isLoading={isSubmitting}
            disabled={
              isSubmitting ||
              title.trim() === '' ||
              isEditorEmpty(
                displayMode === 'rewritten' && rewrittenEditorContent
                  ? rewrittenEditorContent
                  : originalEditorContent,
              )
            }
          >
            Save Card
          </Button>
        </VStack>
      </form>

      {showComparisonView && originalEditorContent && (
        <Modal
          isOpen={showComparisonView}
          onClose={() => setShowComparisonView(false)}
          size="6xl"
          scrollBehavior="inside"
        >
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
                    Original
                  </Heading>
                  <BlockNoteEditorComponent
                    key={`original-comp-${editorKey}`}
                    initialContent={originalEditorContent}
                    editable={false}
                    onEditorChange={(_editorInstance) => {}}
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
                    AI Rewritten
                  </Heading>
                  {isRewritingContent && !rewrittenEditorContent ? (
                    <Flex
                      justify="center"
                      align="center"
                      minH="200px"
                      direction="column"
                    >
                      <Spinner size="xl" />
                      <Text mt={3}>AI Rewriting in progress...</Text>
                      <Text mt={1} fontSize="sm" color="gray.500">
                        {currentProgressMessage || 'Initializing...'}
                      </Text>
                    </Flex>
                  ) : rewrittenEditorContent ? (
                    <BlockNoteEditorComponent
                      key={`rewritten-comp-${editorKey}`}
                      initialContent={rewrittenEditorContent}
                      editable={false}
                      onEditorChange={(_editorInstance) => {}}
                      onContentUpdate={() => {}}
                    />
                  ) : rewriteError ? (
                    <Flex
                      justify="center"
                      align="center"
                      minH="200px"
                      direction="column"
                    >
                      <Text color="red.500">Rewrite Error: {rewriteError}</Text>
                      <Text fontSize="sm" color="gray.500" mt={2}>
                        You can close this window and try again.
                      </Text>
                    </Flex>
                  ) : (
                    <Flex justify="center" align="center" minH="200px">
                      <Text color="gray.500">
                        Waiting for rewritten content...
                      </Text>
                    </Flex>
                  )}
                </Box>
              </Flex>
            </ModalBody>
            <ModalFooter>
              <Button
                colorScheme="blue"
                mr={3}
                onClick={handleUseRewrittenFromComparison}
              >
                Use Rewritten Content
              </Button>
              <Button
                variant="ghost"
                mr={3}
                onClick={handleUseOriginalFromComparison}
              >
                Use Original Content
              </Button>
              <Button
                variant="outline"
                onClick={() => setShowComparisonView(false)}
              >
                Cancel
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      )}
    </Container>
  );
}