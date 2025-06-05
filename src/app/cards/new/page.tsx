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
  Tag,
  TagLabel,
  TagCloseButton,
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
import { mapPartialBlocksToAIServiceContentBlocks, mapContentBlocksToPartialBlocks } from '@/lib/contentUtils';
import type {
  ContentBlock as AIServiceContentBlock,
  RewriteContentResponse,
} from '@/types/api/ai-service';

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
    stagedKeywords,
    error: stagingError,
    clearData: clearStagingData,
  } = useStagingCardStore();

  const [title, setTitle] = useState('');
  const [_editor, setEditor] = useState<BlockNoteEditorType | null>(null);
  const [editorContent, setEditorContent] = useState<AppPartialBlock[] | undefined>(undefined);
  const [editorKey, setEditorKey] = useState(Date.now());
  const [keywords, setKeywords] = useState<string[]>([]);
  const [currentKeyword, setCurrentKeyword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isStagingLoading = useStagingCardStore(state => state.isLoading);

  // State for AI suggestions (adapted from CardDetailPage)
  const [suggestedTitle, setSuggestedTitle] = useState<string | null>(null);
  const [isSuggestingTitle, setIsSuggestingTitle] = useState(false);
  const [suggestedKeywords, setSuggestedKeywords] = useState<string[] | null>(
    null,
  );
  const [isSuggestingKeywords, setIsSuggestingKeywords] = useState(false);

  // New state variables for AI Rewrite functionality
  const [originalEditorContent, setOriginalEditorContent] = useState<AppPartialBlock[] | undefined>(undefined);
  const [rewrittenEditorContent, setRewrittenEditorContent] = useState<AppPartialBlock[] | undefined>(undefined);
  const [isRewritingContent, setIsRewritingContent] = useState(false);
  const [rewriteError, setRewriteError] = useState<string | null>(null);
  const [displayMode, setDisplayMode] = useState<'original' | 'rewritten'>('original');
  const [showComparisonView, setShowComparisonView] = useState(false);

  // ADDED for asynchronous polling
  const [taskId, setTaskId] = useState<string | null>(null);
  const [pollingIntervalId, setPollingIntervalId] = useState<NodeJS.Timeout | null>(null);
  const [pollingAttempts, setPollingAttempts] = useState(0);
  const [currentProgressMessage, setCurrentProgressMessage] = useState<string | null>(null);
  const [hasShownInitialContentReadyToast, setHasShownInitialContentReadyToast] = useState(false);

  const POLLING_INTERVAL_MS = 3000; // 3 seconds
  const MAX_POLLING_ATTEMPTS = 40; // 2 minutes timeout (40 * 3s)

  useEffect(() => {
    console.log('[NewCardPage useEffect] Running. Initial StagedTitle:', stagedTitle);
    console.log('[NewCardPage useEffect] Initial StagedContentBlocks present:', !!stagedContentBlocks && stagedContentBlocks.length > 0);
    console.log('[NewCardPage useEffect] hasShownInitialContentReadyToast state at start:', hasShownInitialContentReadyToast);

    let processedNewDataInThisRun = false; // Renamed from dataLoadedInEffect
    let titleToUse: string | null = null;
    let autoExtractedTitleValue: string | null = null; 

    // Reset toast flag if no data is currently staged, allowing toast for next new data load
    if (!stagedTitle && !stagedContentBlocks && !stagedKeywords) {
      if (hasShownInitialContentReadyToast) { // Only log if it's actually changing
        console.log('[NewCardPage useEffect] No staged data found, resetting hasShownInitialContentReadyToast to false.');
        setHasShownInitialContentReadyToast(false);
      }
    }

    // Step 1: Handle content blocks
    if (stagedContentBlocks) {
      const initialContentForEditor = mapContentBlocksToPartialBlocks(stagedContentBlocks) as AppPartialBlock[];
      setOriginalEditorContent(initialContentForEditor);
      setEditorContent(initialContentForEditor);
      setRewrittenEditorContent(undefined);
      setDisplayMode('original');
      setShowComparisonView(false);
      if (_editor) {
        console.log('[NewCardPage useEffect] Editor instance available, calling replaceBlocks for staged content.');
        _editor.replaceBlocks(_editor.document, initialContentForEditor);
      }
      setEditorKey(Date.now());
      processedNewDataInThisRun = true; 

      // Attempt to auto-extract title from content, will be used if stagedTitle is not suitable
      const firstTextBlock = stagedContentBlocks.find(block => 
        block.type === 'text' && 
        typeof block.content === 'string' && 
        block.content.trim() !== ''
      );
      if (firstTextBlock && typeof firstTextBlock.content === 'string') { 
        let potentialTitle = firstTextBlock.content.trim();
        const MAX_TITLE_LENGTH = 150;
        if (potentialTitle.length > MAX_TITLE_LENGTH) {
          potentialTitle = potentialTitle.substring(0, MAX_TITLE_LENGTH) + '...';
        }
        autoExtractedTitleValue = potentialTitle;
        console.log("[NewCardPage useEffect] Auto-extracted title candidate from content:", autoExtractedTitleValue);
      } else {
        console.log("[NewCardPage useEffect] No suitable first text block found for auto-title extraction.");
      }
    } else if (stagedTitle || stagedKeywords) { 
      // Content blocks are absent, but title or keywords might be staged (e.g. error during content fetch but title came through)
      setOriginalEditorContent(undefined);
      setRewrittenEditorContent(undefined);
      setEditorContent(undefined);
      setDisplayMode('original');
      setShowComparisonView(false);
      if (_editor) {
        _editor.replaceBlocks(_editor.document, []);
      }
      setEditorKey(Date.now());
    }

    // Step 2: Determine the title to actually use for the input field
    if (stagedTitle && stagedTitle.trim() !== '') {
      titleToUse = stagedTitle.trim();
      console.log('[NewCardPage useEffect] Prioritizing non-empty stagedTitle from metadata:', titleToUse);
    } else if (autoExtractedTitleValue) {
      titleToUse = autoExtractedTitleValue;
      console.log('[NewCardPage useEffect] Using auto-extracted title because stagedTitle was null or empty:', titleToUse);
    } else {
      console.log('[NewCardPage useEffect] No title found from metadata or auto-extraction from content.');
    }

    // Step 3: Set the local state for the title input field if a title was determined
    if (titleToUse !== null) {
      console.log('[NewCardPage useEffect] Calling setTitle with:', titleToUse);
      setTitle(titleToUse);
      setSuggestedTitle(null); // Clear any previous AI suggestion for title
      // processedNewDataInThisRun is likely true if content was processed or if stagedTitle was present
      // If only keywords were staged, processedNewDataInThisRun might be false here, but title wouldn't be set anyway.
    } else {
      // If titleToUse is null, we might want to ensure the local title is cleared
      // This is important if a previous card had a title and this one doesn't
      console.log('[NewCardPage useEffect] No definitive title to use. Ensuring local title state is empty.');
      setTitle(''); // Explicitly set to empty if no title is derived
      setSuggestedTitle(null); // Also clear suggestions
    }
    
    // Handle keywords (can be independent of title/content)
    if (stagedKeywords) { 
      setKeywords(stagedKeywords);
      setSuggestedKeywords(null); 
      processedNewDataInThisRun = true; 
    }

    // Toast and cleanup logic
    if (processedNewDataInThisRun && !hasShownInitialContentReadyToast) {
      console.log('[NewCardPage useEffect] Conditions met for showing Content Ready toast.');
      toast({
        title: 'Content Ready',
        description: 'Form has been populated with reconstructed content.',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      setHasShownInitialContentReadyToast(true);
      console.log('[NewCardPage useEffect] setHasShownInitialContentReadyToast to true.');
    } else if (processedNewDataInThisRun && hasShownInitialContentReadyToast) {
      console.log('[NewCardPage useEffect] Processed new data, but initial content ready toast already shown for this batch.');
    } else if (!processedNewDataInThisRun) {
      console.log('[NewCardPage useEffect] No new data processed in this run, not showing content ready toast.');
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

  }, [stagedTitle, stagedContentBlocks, stagedKeywords, stagingError, clearStagingData, toast]);

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

  const handleEditorContentUpdate = useCallback((blocks: PartialBlock[]) => {
    if (!showComparisonView) {
      const appBlocks = blocks as AppPartialBlock[];
      setEditorContent(appBlocks);
      if (JSON.stringify(appBlocks) === JSON.stringify(rewrittenEditorContent)) {
        setDisplayMode('rewritten');
      } else {
        setDisplayMode('original');
      }
    }
  }, [showComparisonView, rewrittenEditorContent]);

  const handleKeywordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentKeyword(e.target.value);
  };

  const handleKeywordKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && currentKeyword.trim() !== '') {
      e.preventDefault();
      const newKeyword = currentKeyword.trim().startsWith('#')
        ? currentKeyword.trim()
        : `#${currentKeyword.trim()}`;
      // Ensure keyword uniqueness, case-insensitively for comparison but store with original casing preference
      if (!keywords.some(kw => kw.toLowerCase() === newKeyword.toLowerCase())) {
        setKeywords([...keywords, newKeyword]);
      }
      setCurrentKeyword('');
    }
  };

  const removeKeyword = (keywordToRemove: string) => {
    setKeywords(keywords.filter(keyword => keyword !== keywordToRemove));
  };

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
    setShowComparisonView(true); // Show comparison view immediately
    setIsRewritingContent(true);
    setRewriteError(null);
    setTaskId(null); // Reset task ID
    setPollingAttempts(0); // Reset polling attempts
    setCurrentProgressMessage("Initiating rewrite process...");
    if (pollingIntervalId) clearInterval(pollingIntervalId); // Clear any existing interval
    setPollingIntervalId(null);

    const currentAppPartialBlocks: AppPartialBlock[] = editorContent;
    setOriginalEditorContent(currentAppPartialBlocks);

    try {
      const aiServiceBlocks = mapPartialBlocksToAIServiceContentBlocks(
        currentAppPartialBlocks as any, // Consider if 'as any' can be more specific
        session?.user.id ?? 'unknown-user',
      );

      const payloadToApi = {
        content_blocks_to_rewrite: aiServiceBlocks,
      };

      console.log(
        '[NewCardPage] handleRewriteContent: Sending payload to /api/ai/rewrite-content for task submission:',
        JSON.stringify(payloadToApi, null, 2),
      );

      const response = await fetch('/api/ai/rewrite-content', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadToApi),
      });

      if (response.status === 202) {
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
        error instanceof Error ? error.message : 'An unknown error occurred during submission';
      setRewriteError(errorMessage);
      toast({
        title: 'Submission Error',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsRewritingContent(false); // Stop loading on submission error
      setShowComparisonView(false); // Hide comparison view if submission fails
    }
    // No finally block setting setIsRewritingContent(false) here, polling handles it
  };

  // useEffect for polling task status
  useEffect(() => {
    if (!taskId || !isRewritingContent) {
      if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        setPollingIntervalId(null);
      }
      // Reset attempts when polling stops or doesn't start
      // setPollingAttempts(0); // Let's reset attempts only when a new task starts or polling ends decisively.
      return;
    }

    const intervalId = setInterval(async () => {
      // Incrementing pollingAttempts via setPollingAttempts directly based on its previous value
      // can be tricky due to closure. It's often better to pass a function to the setter.
      // However, for a simple counter in a setInterval, managing it via a local letiable is also an option.
      // Let's stick to setPollingAttempts with functional update for safety.
      let currentAttemptForLog = 0;
      setPollingAttempts(prevAttempts => {
        currentAttemptForLog = prevAttempts + 1;
        return currentAttemptForLog;
      });

      console.log(`[NewCardPage] Polling task status for ID: ${taskId}, Attempt: ${currentAttemptForLog}`);

      try {
        const response = await fetch(`/api/ai/rewrite-status/${taskId}`);
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ message: `HTTP error ${response.status} ${response.statusText}` }));
          throw new Error(errorData.message || `Failed to poll task status: ${response.statusText}`);
        }

        const data = await response.json();
        // Log the exact data received by the client
        console.log(`[NewCardPage] Polling response data for task ${taskId}, attempt ${currentAttemptForLog}:`, JSON.stringify(data, null, 2));

        if (data.status === 'COMPLETED') {
          console.log(`[NewCardPage] Task ${taskId} COMPLETED. Full data:`, JSON.stringify(data, null, 2));
          console.log(`[NewCardPage] Task ${taskId} COMPLETED. ai_rewritten_content_blocks from data:`, JSON.stringify(data.ai_rewritten_content_blocks, null, 2));

          clearInterval(intervalId);
          setPollingIntervalId(null);
          setIsRewritingContent(false);
          setPollingAttempts(0); // Reset attempts on completion
          setTaskId(null);

          if (data.ai_rewritten_content_blocks) {
            console.log(`[NewCardPage] Task ${taskId} COMPLETED: data.ai_rewritten_content_blocks is truthy. Content:`, JSON.stringify(data.ai_rewritten_content_blocks, null, 2));
            try {
              const newRewrittenContent = mapContentBlocksToPartialBlocks(
                data.ai_rewritten_content_blocks, 
              ) as AppPartialBlock[];
              console.log(`[NewCardPage] Task ${taskId} COMPLETED: newRewrittenContent after mapping:`, JSON.stringify(newRewrittenContent, null, 2));
              
              if (newRewrittenContent) { // Additional check for safety, though mapContentBlocksToPartialBlocks should ideally not return null/undefined if input is array
                setRewrittenEditorContent(newRewrittenContent);
                setCurrentProgressMessage(null);
                console.log(`[NewCardPage] Task ${taskId} COMPLETED: Called setRewrittenEditorContent.`);
                toast({
                  title: 'Content Rewritten Successfully',
                  description: 'AI has completed rewriting the content.',
                  status: 'success',
                  duration: 3000,
                  isClosable: true,
                });
              } else {
                const mappingError = 'Rewrite completed, content was present, but mapping resulted in empty content.';
                console.error(`[NewCardPage] Task ${taskId} COMPLETED: ${mappingError}`);
                setRewriteError(mappingError);
                setCurrentProgressMessage(null);
                toast({ title: 'Rewrite Mapping Error', description: mappingError, status: 'error', duration: 5000, isClosable: true });
                setShowComparisonView(false);
              }
            } catch (mappingOrSetError) {
                const processingError = 'Error processing or setting rewritten content.';
                console.error(`[NewCardPage] Task ${taskId} COMPLETED: ${processingError}`, mappingOrSetError);
                setRewriteError(processingError + (mappingOrSetError instanceof Error ? `: ${mappingOrSetError.message}`: ''));
                setCurrentProgressMessage(null);
                toast({ title: 'Rewrite Processing Error', description: processingError, status: 'error', duration: 5000, isClosable: true });
                setShowComparisonView(false);
            }
          } else {
            const completionError = 'Rewrite completed, but data.ai_rewritten_content_blocks was falsy.';
            console.warn(`[NewCardPage] Task ${taskId} COMPLETED: ${completionError} Value:`, data.ai_rewritten_content_blocks);
            setRewriteError(completionError);
            setCurrentProgressMessage(null);
            toast({ title: 'Rewrite Data Missing', description: completionError, status: 'error', duration: 5000, isClosable: true });
            setShowComparisonView(false);
          }
        } else if (data.status === 'FAILED') {
          clearInterval(intervalId);
          setPollingIntervalId(null);
          setIsRewritingContent(false);
          setPollingAttempts(0); // Reset attempts on failure
          setTaskId(null);
          setCurrentProgressMessage(null);
          const errorMessage = data.errorMessage || 'Rewrite task failed with no specific error message.';
          setRewriteError(errorMessage);
          toast({
            title: 'Rewrite Task Failed',
            description: errorMessage,
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
          setShowComparisonView(false); // Hide comparison on failure
        } else if (data.status === 'PENDING' || data.status === 'PROCESSING') {
          // Polling continues, check against MAX_POLLING_ATTEMPTS
          setCurrentProgressMessage(data.progressStage || 'Processing...');
          if (currentAttemptForLog >= MAX_POLLING_ATTEMPTS) {
            clearInterval(intervalId);
            setPollingIntervalId(null);
            setIsRewritingContent(false);
            setPollingAttempts(0); // Reset attempts on timeout
            setTaskId(null);
            setCurrentProgressMessage(null);
            const timeoutMessage = 'Rewrite task timed out after several attempts.';
            setRewriteError(timeoutMessage);
            toast({
              title: 'Rewrite Timeout',
              description: timeoutMessage,
              status: 'error',
              duration: 5000,
              isClosable: true,
            });
            setShowComparisonView(false); // Hide comparison on timeout
          }
        } else {
          // Unknown status
          clearInterval(intervalId);
          setPollingIntervalId(null);
          setIsRewritingContent(false);
          setPollingAttempts(0); // Reset attempts on unknown status
          setTaskId(null);
          setCurrentProgressMessage(null);
          const unknownStatusMessage = `Received an unknown task status: ${data.status}`;
          setRewriteError(unknownStatusMessage);
          toast({
            title: 'Unknown Task Status',
            description: unknownStatusMessage,
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
          setShowComparisonView(false);
        }
      } catch (error) {
        clearInterval(intervalId);
        setPollingIntervalId(null);
        setIsRewritingContent(false);
        setPollingAttempts(0); // Reset attempts on polling error
        setTaskId(null);
        setCurrentProgressMessage(null);
        const errorMessage =
          error instanceof Error ? error.message : 'An unknown error occurred during polling';
        setRewriteError(errorMessage);
        toast({
          title: 'Polling Error',
          description: errorMessage,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        setShowComparisonView(false);
      }
    }, POLLING_INTERVAL_MS);

    setPollingIntervalId(intervalId);

    return () => {
      if (intervalId) clearInterval(intervalId);
      setPollingIntervalId(null);
    };
  }, [taskId, isRewritingContent, toast]);

  const handleUseOriginalFromComparison = () => {
    if (originalEditorContent) {
      setEditorContent(originalEditorContent);
      if (_editor) {
        _editor.replaceBlocks(_editor.document, originalEditorContent);
      }
      setDisplayMode('original');
    }
    setShowComparisonView(false);
    toast({ title: "Original Content Selected", status: "info", duration: 2000, isClosable: true });
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
    toast({ title: "Rewritten Content Selected", status: "success", duration: 2000, isClosable: true });
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
    
    const contentToProcess = displayMode === 'rewritten' && rewrittenEditorContent && !isEditorEmpty(rewrittenEditorContent) 
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
        tags: keywords.map(kw => kw.startsWith('#') ? kw.substring(1) : kw),
      };
      
      console.log('[NewCardPage] handleSubmit: Sending payload:', JSON.stringify(payload, null, 2));

      const response = await fetch('/api/cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const responseData = await response.json() as CreateCardSuccessResponse | CreateCardErrorResponse;

      if (response.ok && (responseData as CreateCardSuccessResponse).id) {
        toast({ title: 'Card created successfully!', status: 'success', duration: 3000, isClosable: true });
        router.push(`/cards/${(responseData as CreateCardSuccessResponse).id}`);
      } else {
        const errorResponse = responseData as CreateCardErrorResponse;
        const message = errorResponse.error || errorResponse.message || 'Failed to create card';
        toast({ title: 'Error Creating Card', description: message, status: 'error', duration: 5000, isClosable: true });
      }
    } catch (error) {
      toast({ title: 'An unexpected error occurred', description: error instanceof Error ? error.message : String(error), status: 'error', duration: 5000, isClosable: true });
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
    try {
      const currentContentBlocks = mapPartialBlocksToAIServiceContentBlocks(
        _editor.document as AppPartialBlock[],
        session.user.id,
      );

      if (currentContentBlocks.length === 0) {
        toast({
          title: 'Cannot Suggest Title',
          description: 'Failed to prepare content for title suggestion.',
          status: 'warning',
          duration: 3000,
          isClosable: true,
        });
        setIsSuggestingTitle(false);
        return;
      }
      
      console.log('[NewCardPage] handleSuggestTitle: Sending content for title suggestion:', JSON.stringify(currentContentBlocks, null, 2));

      const response = await fetch('/api/ai/generate-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_blocks: currentContentBlocks }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.message || `HTTP error! status: ${response.status}`,
        );
      }
      const data = await response.json();
      console.log('[NewCardPage] handleSuggestTitle: Received suggested title:', data.suggested_title);
      setSuggestedTitle(data.suggested_title);
      toast({
        title: 'Title Suggested',
        description: 'A new title has been suggested.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Error suggesting title:', error);
      const message =
        error instanceof Error ? error.message : 'Unknown error suggesting title';
      toast({
        title: 'Title Suggestion Failed',
        description: message,
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setIsSuggestingTitle(false);
    }
  };

  const applySuggestedTitle = () => {
    if (suggestedTitle) {
      setTitle(suggestedTitle);
      setSuggestedTitle(null); // Clear suggestion after applying
      toast({
        title: 'Title Updated',
        description: 'The suggested title has been applied.',
        status: 'info',
        duration: 2000,
        isClosable: true,
      });
    }
  };

  const handleSuggestKeywords = async () => {
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
    if (!_editor || isEditorEmpty(_editor.document as AppPartialBlock[])) {
      toast({
        title: 'Content Required',
        description: 'Cannot suggest keywords for empty content.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }
    setIsSuggestingKeywords(true);
    setSuggestedKeywords(null);
    try {
      const currentContentBlocks = mapPartialBlocksToAIServiceContentBlocks(
        _editor.document as AppPartialBlock[],
        session.user.id,
      );

      if (currentContentBlocks.length === 0) {
        toast({
          title: 'Cannot Suggest Keywords',
          description: 'Failed to prepare content for keyword suggestion.',
          status: 'warning',
          duration: 3000,
          isClosable: true,
        });
        setIsSuggestingKeywords(false);
        return;
      }
      
      console.log('[NewCardPage] handleSuggestKeywords: Sending content for keyword suggestion:', JSON.stringify(currentContentBlocks, null, 2));

      const response = await fetch('/api/ai/generate-keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_blocks: currentContentBlocks }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.message || `HTTP error! status: ${response.status}`,
        );
      }
      const data = await response.json();
      console.log('[NewCardPage] handleSuggestKeywords: Received suggested keywords:', data.suggested_keywords);
      setSuggestedKeywords(data.suggested_keywords.map((kw: string) => kw.startsWith('#') ? kw : `#${kw}`));
      toast({
        title: 'Keywords Suggested',
        description: 'New keywords have been suggested.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Error suggesting keywords:', error);
      const message =
        error instanceof Error
          ? error.message
          : 'Unknown error suggesting keywords';
      toast({
        title: 'Keyword Suggestion Failed',
        description: message,
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setIsSuggestingKeywords(false);
    }
  };

  const applySuggestedKeyword = (keyword: string) => {
    const newKeyword = keyword.startsWith('#') ? keyword : `#${keyword}`;
    if (!keywords.some(kw => kw.toLowerCase() === newKeyword.toLowerCase())) {
      setKeywords([...keywords, newKeyword]);
    }
    // Optionally remove from suggested list or indicate it's been added
  };

  const applyAllSuggestedKeywords = () => {
    if (suggestedKeywords) {
      const keywordsToAdd = suggestedKeywords.filter(
        sk => !keywords.some(kw => kw.toLowerCase() === sk.toLowerCase())
      );
      setKeywords([...keywords, ...keywordsToAdd]);
      setSuggestedKeywords(null); // Clear suggestions after applying
      toast({
        title: 'Keywords Updated',
        description: 'All new suggested keywords have been added.',
        status: 'info',
        duration: 2000,
        isClosable: true,
      });
    }
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
  if (isStagingLoading && !stagedTitle && !stagedContentBlocks) { // Only show if not yet populated
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
                disabled={isSuggestingTitle || !_editor || isEditorEmpty(_editor?.document as AppPartialBlock[])}
              >
                Suggest Title
              </Button>
              {suggestedTitle && (
                <Button size="sm" colorScheme="teal" variant="outline" onClick={applySuggestedTitle}>
                  Apply: "{suggestedTitle.substring(0,30)}{suggestedTitle.length > 30 ? '...' : ''}"
                </Button>
              )}
            </HStack>
          </FormControl>
          <FormControl>
            <FormLabel htmlFor="keywords">Keywords (Tags)</FormLabel>
            <HStack spacing={2} wrap="wrap" mb={2}>
              {keywords.map((keyword) => (
                <Tag key={keyword} borderRadius="full" variant="solid" colorScheme="teal">
                  <TagLabel>{keyword}</TagLabel>
                  <TagCloseButton onClick={() => removeKeyword(keyword)} />
                </Tag>
              ))}
            </HStack>
            <Input
              id="keywords"
              type="text"
              value={currentKeyword}
              onChange={handleKeywordChange}
              onKeyDown={handleKeywordKeyDown}
              placeholder="Type a keyword and press Enter (e.g., #example)"
              isDisabled={isSubmitting || isStagingLoading} 
            />
          </FormControl>
          <FormControl>
            <FormLabel>Suggested Keywords</FormLabel>
            <Flex wrap="wrap" gap={2}>
              {suggestedKeywords && suggestedKeywords.map((kw, index) => (
                <Tag key={index} size="sm" variant="solid" colorScheme="purple">
                  <TagLabel>{kw}</TagLabel>
                  <TagCloseButton onClick={() => applySuggestedKeyword(kw)} aria-label={`Add keyword ${kw}`} />
                </Tag>
              ))}
            </Flex>
            {suggestedKeywords && suggestedKeywords.length > 0 && (
              <Button size="xs" mt={2} onClick={applyAllSuggestedKeywords} isLoading={isSuggestingKeywords}>Apply All New</Button>
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
            <Box border="1px solid" borderColor="gray.200" borderRadius="md" p={1} minH="300px">
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
            {rewriteError && <Text color="red.500" mt={1} fontSize="sm">Rewrite Error: {rewriteError}</Text>}
          </FormControl>
          <Button
            mt={6}
            colorScheme="blue"
            type="submit"
            isLoading={isSubmitting}
            disabled={isSubmitting || title.trim() === '' || isEditorEmpty(displayMode === 'rewritten' && rewrittenEditorContent ? rewrittenEditorContent : originalEditorContent)}
          >
            Save Card
          </Button>
        </VStack>
      </form>

      {showComparisonView && originalEditorContent && (
        <Modal isOpen={showComparisonView} onClose={() => setShowComparisonView(false)} size="6xl" scrollBehavior="inside">
          <ModalOverlay />
          <ModalContent maxH="90vh">
            <ModalHeader>Compare Original and Rewritten Content</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <Flex direction={{ base: "column", md: "row" }} gap={4}>
                <Box flex={1} p={2} borderWidth="1px" borderRadius="md" overflowY="auto" maxH="70vh">
                  <Heading size="sm" mb={2}>Original</Heading>
                  <BlockNoteEditorComponent
                    key={`original-comp-${editorKey}`}
                    initialContent={originalEditorContent}
                    editable={false}
                    onEditorChange={(_editorInstance) => {}}
                    onContentUpdate={() => {}}
                  />
                </Box>
                <Box flex={1} p={2} borderWidth="1px" borderRadius="md" overflowY="auto" maxH="70vh">
                  <Heading size="sm" mb={2}>AI Rewritten</Heading>
                  {isRewritingContent && !rewrittenEditorContent ? (
                    <Flex justify="center" align="center" minH="200px" direction="column">
                      <Spinner size="xl" />
                      <Text mt={3}>AI Rewriting in progress...</Text>
                      <Text mt={1} fontSize="sm" color="gray.500">{currentProgressMessage || 'Initializing...'}</Text>
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
                    <Flex justify="center" align="center" minH="200px" direction="column">
                        <Text color="red.500">Rewrite Error: {rewriteError}</Text>
                        <Text fontSize="sm" color="gray.500" mt={2}>You can close this window and try again.</Text>
                    </Flex>
                  ) : (
                    <Flex justify="center" align="center" minH="200px">
                      <Text color="gray.500">Waiting for rewritten content...</Text>
                    </Flex>
                  )}
                </Box>
              </Flex>
            </ModalBody>
            <ModalFooter>
              <Button colorScheme="blue" mr={3} onClick={handleUseRewrittenFromComparison}>
                Use Rewritten Content
              </Button>
              <Button variant="ghost" mr={3} onClick={handleUseOriginalFromComparison}>
                Use Original Content
              </Button>
              <Button variant="outline" onClick={() => setShowComparisonView(false)}>Cancel</Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      )}
    </Container>
  );
}
