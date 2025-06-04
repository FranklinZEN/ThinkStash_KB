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

  useEffect(() => {
    let dataLoadedInEffect = false;

    if (stagedTitle) {
      setTitle(stagedTitle);
      setSuggestedTitle(null); 
      dataLoadedInEffect = true;
    }
    if (stagedKeywords) {
      setKeywords(stagedKeywords);
      setSuggestedKeywords(null); 
      dataLoadedInEffect = true;
    }

    if (stagedContentBlocks) {
      // When new staged content arrives, it's always the "original"
      const initialContent = mapContentBlocksToPartialBlocks(stagedContentBlocks) as AppPartialBlock[];
      setOriginalEditorContent(initialContent);
      setEditorContent(initialContent); 
      setRewrittenEditorContent(undefined); 
      setDisplayMode('original');        
      setShowComparisonView(false);
      if (_editor) {
        console.log('[NewCardPage useEffect] Editor instance available, calling replaceBlocks for staged content (initial).');
        _editor.replaceBlocks(_editor.document, initialContent);
      }
      setEditorKey(Date.now());
      dataLoadedInEffect = true;
    } else if (stagedTitle || stagedKeywords) { 
      setOriginalEditorContent(undefined);
      setRewrittenEditorContent(undefined);
      setEditorContent(undefined);
      setDisplayMode('original');
      setShowComparisonView(false);
      if (_editor) {
        console.log('[NewCardPage useEffect] Editor instance available, clearing blocks due to absent stagedContentBlocks.');
        _editor.replaceBlocks(_editor.document, []);
      }
      setEditorKey(Date.now());
    }

    if (dataLoadedInEffect) {
      toast({
        title: 'Content Ready',
        description: 'Form has been populated with reconstructed content.',
        status: 'info',
        duration: 3000,
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

    if (stagedTitle || stagedContentBlocks || stagedKeywords || stagingError) {
        clearStagingData();
    }

  }, [_editor, stagedTitle, stagedContentBlocks, stagedKeywords, stagingError, clearStagingData, toast]);

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

    // Show the comparison view immediately and reset rewritten content
    setRewrittenEditorContent(undefined); 
    setShowComparisonView(true);
    setIsRewritingContent(true);
    setRewriteError(null);

    // Explicitly create a new variable that TypeScript knows is AppPartialBlock[]
    const currentAppPartialBlocks: AppPartialBlock[] = editorContent;

    setOriginalEditorContent(currentAppPartialBlocks); 

    try {
      const aiServiceBlocks = mapPartialBlocksToAIServiceContentBlocks(
        currentAppPartialBlocks as any,
        session?.user.id ?? 'unknown-user',
      );

      // Correct the key in the payload to match what the backend API route expects
      const payloadToApi = {
        content_blocks_to_rewrite: aiServiceBlocks,
        // document_metadata can be added here if needed by your API/service
        // user_id will be handled by the session on the backend
      };

      console.log(
        '[NewCardPage] handleRewriteContent: Sending payload to /api/ai/rewrite-content:',
        JSON.stringify(payloadToApi, null, 2),
      );

      const response = await fetch('/api/ai/rewrite-content', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadToApi), // Use the corrected payload
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.message ||
            `HTTP error ${response.status} ${response.statusText}`,
        );
      }

      // Use the correct type and access the correct property for rewritten content
      const result: RewriteContentResponse = await response.json();

      const newRewrittenContent = mapContentBlocksToPartialBlocks(
        result.ai_rewritten_content_blocks, // Changed from result.rewritten_content
      ) as AppPartialBlock[];
      setRewrittenEditorContent(newRewrittenContent);

      toast({
        title: 'Content Rewritten',
        description: 'AI has rewritten the content. Review and choose a version.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Error rewriting content:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'An unknown error occurred';
      setRewriteError(errorMessage);
      toast({
        title: 'Rewrite Error',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsRewritingContent(false);
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
      const blocksToSave = mapPartialBlocksToAIServiceContentBlocks(
        contentToProcess!, 
        session.user.id,
        null 
      );

      const payload = {
        title: title,
        contentBlocks: blocksToSave,
        keywords: keywords.map(kw => kw.startsWith('#') ? kw.substring(1) : kw),
        userId: session.user.id,
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
          <FormControl mt={4}>
            <FormLabel>Content</FormLabel>
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
                  isLoading={isRewritingContent}
                  colorScheme="purple"
                  isDisabled={showComparisonView}
                >
                  AI Rewrite Content
                </Button>
              </HStack>
            </HStack>
            {rewriteError && <Text color="red.500" mt={1} fontSize="sm">Rewrite Error: {rewriteError}</Text>}
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
            <Button size="xs" mt={2} onClick={applyAllSuggestedKeywords}>Apply All New</Button>
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

      {showComparisonView && originalEditorContent && rewrittenEditorContent && (
        <Modal isOpen={showComparisonView} onClose={() => setShowComparisonView(false)} size="6xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Compare Original and Rewritten Content</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <Flex direction={{ base: "column", md: "row" }} gap={4}>
                <Box flex={1} p={2} borderWidth="1px" borderRadius="md">
                  <Heading size="md" mb={2}>Original</Heading>
                  <Box maxHeight="500px" overflowY="auto" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={1}>
                    <BlockNoteEditorComponent
                      key={`original-${editorKey}`}
                      initialContent={originalEditorContent}
                      editable={false}
                      onEditorChange={(_editorInstance) => {}}
                      onContentUpdate={() => {}}
                    />
                  </Box>
                </Box>
                <Box flex={1} p={2} borderWidth="1px" borderRadius="md">
                  <Heading size="md" mb={2}>AI Rewritten</Heading>
                  <Box maxHeight="500px" overflowY="auto" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={1}>
                    <BlockNoteEditorComponent
                      key={`rewritten-${editorKey}`}
                      initialContent={rewrittenEditorContent}
                      editable={true} 
                      onContentUpdate={(newContent) => {
                        setRewrittenEditorContent(newContent);
                      }}
                      onEditorChange={(_editorInstance) => {}}
                    />
                  </Box>
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
