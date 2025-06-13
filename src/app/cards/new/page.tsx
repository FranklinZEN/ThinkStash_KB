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
import { type AppPartialBlock } from '@/lib/blocknote/appSchema';
import { useStagingCardStore } from '@/stores/stagingCardStore';
import {
  mapPartialBlocksToAIServiceContentBlocks,
  mapContentBlocksToPartialBlocks,
} from '@/lib/contentUtils';

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

  const {
    stagedTitle,
    stagedContentBlocks,
    stagedKeywords: initialStagedKeywords,
    stagedTaskId,
    error: stagingError,
    clearData: clearStagingData,
    setData: setStagingData,
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
  const isStagingLoading = useStagingCardStore((state) => state.isLoading);

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

  // --- Task-based Polling State ---
  const [pollingAttempts, setPollingAttempts] = useState(0);
  const [currentProgressMessage, setCurrentProgressMessage] =
    useState<string | null>(null);

  const [pollingTaskId, setPollingTaskId] = useState<string | null>(null);
  const [pollingTaskType, setPollingTaskType] = useState<
    'rewrite' | 'title' | 'keywords' | 'reconstruct' | null
  >(null);

  // This useEffect handles the polling logic for a task ID passed via the staging store.
  useEffect(() => {
    if (stagedTaskId) {
      setPollingTaskId(stagedTaskId);
      setPollingTaskType('reconstruct');
      // Important: Clear the taskId from the store so this effect doesn't re-run
      // with the same ID on component re-renders.
      setStagingData(null, null, null, null);
    }
  }, [stagedTaskId, setStagingData]);

  const POLLING_INTERVAL_MS = 3000; // 3 seconds
  const MAX_POLLING_ATTEMPTS = 60; // 60 attempts * 3 seconds = 3 minutes timeout

  // Main polling useEffect
  useEffect(() => {
    if (!pollingTaskId || !pollingTaskType) {
      return; // No active task to poll
    }

    const intervalId = setInterval(async () => {
      setPollingAttempts((prev) => prev + 1);

      if (pollingAttempts >= MAX_POLLING_ATTEMPTS) {
        clearInterval(intervalId);
        const errorMsg = `Polling timed out for ${pollingTaskType} task.`;
        toast({
          title: 'Task Timeout',
          description: errorMsg,
          status: 'error',
        });
        // Reset all polling states
        setPollingTaskId(null);
        setPollingTaskType(null);
        setPollingAttempts(0);
        setCurrentProgressMessage(null);
        // Also clear any loading states related to the specific task type
        if (pollingTaskType === 'rewrite') {
          setIsRewritingContent(false);
          setRewriteError(errorMsg);
        }
        return;
      }

      try {
        const res = await fetch(`/api/tasks/${pollingTaskId}/status`);
        if (!res.ok) {
          // Special handling for 404
          if (res.status === 404) {
            // This can happen in a race condition where polling starts before the task is committed.
            // We can just wait for the next attempt.
            console.warn(
              `Polling warning: Task ${pollingTaskId} not found (attempt ${pollingAttempts}). Retrying.`,
            );
            return;
          }
          throw new Error(`Server returned ${res.status}`);
        }
        const taskData = await res.json();

        setCurrentProgressMessage(taskData.progressMessage);

        if (taskData.status === 'COMPLETED') {
          clearInterval(intervalId);
          toast({
            title: 'Task Complete',
            description: `${pollingTaskType} finished successfully.`,
            status: 'success',
          });

          // Handle result based on task type
          if (pollingTaskType === 'reconstruct' && taskData.result) {
            setStagingData(
              taskData.result.title,
              taskData.result.contentBlocks,
              taskData.result.keywords,
              null, // Clear the taskId
            );
          } else if (pollingTaskType === 'rewrite' && taskData.result) {
            handleRewriteSuccess(taskData.result.contentBlocks);
          }

          // Reset polling state
          setPollingTaskId(null);
          setPollingTaskType(null);
          setPollingAttempts(0);
        } else if (taskData.status === 'FAILED') {
          clearInterval(intervalId);
          const userMessage =
            taskData.error?.userMessage ||
            `Task failed with an unknown error.`;
          toast({
            title: 'Task Failed',
            description: userMessage,
            status: 'error',
          });
          // Reset polling state and set specific error states
          if (pollingTaskType === 'rewrite') {
            setIsRewritingContent(false);
            setRewriteError(userMessage);
          }
          setPollingTaskId(null);
          setPollingTaskType(null);
          setPollingAttempts(0);
        }
        // If 'PENDING' or 'PROCESSING', do nothing and let the interval continue
      } catch (error) {
        console.error('Polling error:', error);
        // We don't clear interval here, we let it retry up to the max attempts
      }
    }, POLLING_INTERVAL_MS);

    // Cleanup function
    return () => {
      clearInterval(intervalId);
    };
  }, [
    pollingTaskId,
    pollingTaskType,
    setStagingData,
    toast,
    pollingAttempts,
  ]);

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

    let processedNewDataInThisRun = false;
    let titleToUse: string | null = null;
    let autoExtractedTitleValue: string | null = null;

    if (stagedTitle) {
      titleToUse = stagedTitle;
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

    if (processedNewDataInThisRun) {
      toast({
        title: 'Content Ready for New Card',
        description:
          'Your previously started content (or content from another tab/tool) has been loaded. Review and continue.',
        status: 'info',
        duration: 7000,
        isClosable: true,
      });
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

  const handleRewriteContent = async () => {
    if (!editorContent || isEditorEmpty(editorContent)) {
      toast({
        title: 'Cannot Rewrite Empty Content',
        description: 'Please add some content to the editor before rewriting.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    // Reset relevant states before starting
    setRewrittenEditorContent(undefined);
    setShowComparisonView(true);
    setIsRewritingContent(true);
    setRewriteError(null);
    setCurrentProgressMessage('Initiating rewrite task...');
    setPollingAttempts(0);

    const currentAppPartialBlocks: AppPartialBlock[] = editorContent;
    setOriginalEditorContent(currentAppPartialBlocks);

    try {
      const aiServiceBlocks = mapPartialBlocksToAIServiceContentBlocks(
        currentAppPartialBlocks,
        session?.user.id ?? 'unknown-user',
      );

      const payloadToApi = {
        content_blocks_to_rewrite: aiServiceBlocks,
      };

      const response = await fetch('/api/ai/rewrite-content', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadToApi),
      });

      if (response.status === 202) {
        const result = await response.json();
        if (result.taskId) {
          setPollingTaskId(result.taskId); // Set generic polling ID
          setPollingTaskType('rewrite'); // Set task type
          toast({
            title: 'Rewrite Task Submitted',
            description: 'Processing request...',
            status: 'info',
            duration: 3000,
            isClosable: true,
          });
        } else {
          throw new Error('Task ID not found in submission response.');
        }
      } else {
        const errorData = await response.json();
        throw new Error(
          errorData.message ||
            `HTTP error ${response.status} ${response.statusText}`,
        );
      }
    } catch (error) {
      console.error('Error submitting rewrite task:', error);
      const errorMessage =
        error instanceof Error
          ? error.message
          : 'An unknown error occurred during submission';
      setRewriteError(errorMessage);
      toast({
        title: 'Submission Error',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsRewritingContent(false);
      setShowComparisonView(false);
    }
  };

  const handleUseOriginalFromComparison = () => {
    if (originalEditorContent) {
      setEditorContent(originalEditorContent);
      if (_editor) {
        _editor.replaceBlocks(_editor.document, originalEditorContent);
      }
      setDisplayMode('original');
    }
    setShowComparisonView(false);
    toast({
      title: 'Original Content Selected',
      status: 'info',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleUseRewrittenFromComparison = () => {
    if (rewrittenEditorContent) {
      setEditorContent(rewrittenEditorContent);
      if (_editor) {
        _editor.replaceBlocks(_editor.document, rewrittenEditorContent);
      }
      setDisplayMode('rewritten');
    }
    setShowComparisonView(false);
    toast({
      title: 'Rewritten Content Selected',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (title.trim() === '') {
      toast({
        title: 'Title is required',
        description: 'Please enter a title for your card.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      return;
    }

    const contentToProcess =
      displayMode === 'rewritten' &&
      rewrittenEditorContent &&
      !isEditorEmpty(rewrittenEditorContent)
        ? rewrittenEditorContent
        : originalEditorContent;

    if (isEditorEmpty(contentToProcess)) {
      toast({
        title: 'Content is required',
        description: 'Please add some content to your card.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      return;
    }

    setIsSubmitting(true);

    if (!session?.user?.id) {
      toast({
        title: 'Authentication Error',
        description: 'User ID not found. Please re-login.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    try {
      const payload = {
        title: title,
        content: contentToProcess,
        tags: keywords.map((kw) => (kw.startsWith('#') ? kw : `#${kw}`)),
      };

      console.log(
        '[NewCardPage] handleSubmit: Sending payload:',
        JSON.stringify(payload, null, 2),
      );

      const response = await fetch('/api/cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const responseData = (await response.json()) as
        | CreateCardSuccessResponse
        | CreateCardErrorResponse;

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
        const message =
          errorResponse.error ||
          errorResponse.message ||
          'Failed to create card';
        toast({
          title: 'Error Creating Card',
          description: message,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    } catch (error) {
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
    if (sessionStatus !== 'authenticated' || !session?.user?.id) {
      toast({
        title: 'Authentication Required',
        description: 'You must be logged in to suggest titles.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }
    if (!_editor || isEditorEmpty(_editor.document as AppPartialBlock[])) {
      toast({
        title: 'Content Required',
        description: 'Cannot suggest title for empty content.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsSuggestingTitle(true);
    setSuggestedTitle(null);
    setCurrentProgressMessage('Initiating title suggestion...');
    setPollingAttempts(0);

    try {
      const currentContentBlocks = mapPartialBlocksToAIServiceContentBlocks(
        _editor.document as AppPartialBlock[],
        session.user.id,
      );

      const response = await fetch('/api/ai/generate-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_blocks: currentContentBlocks }),
      });

      if (response.status === 202) {
        const result = await response.json();
        if (result.taskId) {
          setPollingTaskId(result.taskId);
          setPollingTaskType('title');
          toast({
            title: 'Title Suggestion Submitted',
            description: 'Processing request...',
            status: 'info',
            duration: 3000,
            isClosable: true,
          });
        } else {
          throw new Error('Task ID not found in submission response.');
        }
      } else {
        const errorData = await response.json();
        throw new Error(
          errorData.message || `HTTP error! status: ${response.status}`,
        );
      }
    } catch (error) {
      console.error('Error suggesting title:', error);
      const message =
        error instanceof Error
          ? error.message
          : 'Unknown error suggesting title';
      toast({
        title: 'Title Suggestion Failed',
        description: message,
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      setIsSuggestingTitle(false);
    }
  };

  const applySuggestedTitle = () => {
    if (suggestedTitle) {
      setTitle(suggestedTitle);
      setSuggestedTitle(null); // Clear suggestion after applying
    }
  };

  const handleKeywordsInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const newKeywords = event.target.value.split(',').map((kw) => kw.trim());
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
    setCurrentProgressMessage('Initiating keyword generation...');
    setPollingAttempts(0);

    try {
      const aiServiceBlocks = mapPartialBlocksToAIServiceContentBlocks(
        contentToProcess,
        session.user.id,
      );

      const response = await fetch('/api/ai/generate-keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_blocks: aiServiceBlocks }),
      });

      if (response.status === 202) {
        const result = await response.json();
        if (result.taskId) {
          setPollingTaskId(result.taskId);
          setPollingTaskType('keywords');
          toast({
            title: 'Keyword Generation Submitted',
            description: 'Processing request...',
            status: 'info',
            duration: 3000,
            isClosable: true,
          });
        } else {
          throw new Error('Task ID not found in submission response.');
        }
      } else {
        const errorData = await response.json();
        throw new Error(
          errorData.error || `HTTP error! status: ${response.status}`,
        );
      }
    } catch (error) {
      console.error('Error generating keywords:', error);
      setKeywordError(
        error instanceof Error
          ? error.message
          : 'An unexpected error occurred while generating keywords.',
      );
      setIsGeneratingKeywords(false);
    }
  };

  const handleRewriteSuccess = (_rewrittenBlocks: AppPartialBlock[]) => {
    // Implementation of handleRewriteSuccess
    setIsRewritingContent(false);
    setShowComparisonView(true);
    setDisplayMode('rewritten');
  };

  if (sessionStatus === 'loading' || isStagingLoading) {
    return (
      <Flex justify="center" align="center" minH="100vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (sessionStatus === 'unauthenticated') {
    // Should be handled by middleware or a higher-order component, but good to have a fallback
    router.push('/auth/signin');
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
                  isEditorEmpty(_editor?.document as AppPartialBlock[])
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
