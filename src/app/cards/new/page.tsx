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
} from '@chakra-ui/react';
import {
  BlockNoteEditor as BlockNoteEditorType,
  PartialBlock,
} from '@blocknote/core';
import { useStagingCardStore } from '@/stores/stagingCardStore';

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
  const { status } = useSession();
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
  const [editorContent, setEditorContent] = useState<PartialBlock[] | undefined>(undefined);
  const [editorKey, setEditorKey] = useState(Date.now());
  const [keywords, setKeywords] = useState<string[]>([]);
  const [currentKeyword, setCurrentKeyword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isStagingLoading = useStagingCardStore(state => state.isLoading);

  useEffect(() => {
    let dataLoadedInEffect = false;

    if (stagedTitle) {
      setTitle(stagedTitle);
      dataLoadedInEffect = true;
    }
    if (stagedKeywords) {
      setKeywords(stagedKeywords);
      dataLoadedInEffect = true;
    }

    if (stagedContentBlocks) {
      setEditorContent(stagedContentBlocks);
      if (_editor) {
        console.log('[NewCardPage useEffect] Editor instance available, calling replaceBlocks for staged content.');
        _editor.replaceBlocks(_editor.document, stagedContentBlocks);
      }
      setEditorKey(Date.now());
      dataLoadedInEffect = true;
    } else if (stagedTitle || stagedKeywords) {
      setEditorContent(undefined);
      if (_editor) {
        console.log('[NewCardPage useEffect] Editor instance available, clearing blocks due to absent stagedContentBlocks.');
        _editor.replaceBlocks(_editor.document, []);
      }
      setEditorKey(Date.now());
    }

    if (dataLoadedInEffect) {
      toast({
        title: 'Content Ready',
        description: 'Form has been populated.',
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
    setEditorContent(blocks);
  }, []);

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

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (isStagingLoading) { 
        toast({ title: 'Please wait for initial processing to complete.', status: 'warning'});
        return;
    }

    setIsSubmitting(true);
    const currentBlocks = _editor ? _editor.document : editorContent;

    if (!title.trim()) {
      toast({ title: 'Title is required', status: 'error', duration: 3000, isClosable: true });
      setIsSubmitting(false);
      return;
    }
    if (isEditorEmpty(currentBlocks)) {
      toast({ title: 'Content cannot be empty', description: 'Please add some content to your card.', status: 'error', duration: 3000, isClosable: true });
      setIsSubmitting(false);
      return;
    }

    const cardData = {
      title: title.trim(),
      content: currentBlocks || [], // Ensure content is PartialBlock[]
      tags: keywords.map((kw) => (kw.startsWith('#') ? kw.substring(1) : kw)),
      folderId: null, 
    };

    try {
      const response = await fetch('/api/cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cardData),
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

  if (status === 'loading') {
    return (
      <Flex justify="center" align="center" minH="100vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
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
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter card title"
              isDisabled={isSubmitting || isStagingLoading} 
            />
          </FormControl>
          <FormControl>
            <FormLabel>Content</FormLabel>
            <Box borderWidth="1px" borderRadius="lg" p={1} minH="300px">
              <BlockNoteEditorComponent
                key={editorKey}
                initialContent={editorContent} 
                onContentUpdate={handleEditorContentUpdate}
                onEditorChange={handleEditorInstanceReady}
                editable={!(isSubmitting || isStagingLoading)} 
              />
            </Box>
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
          <Button type="submit" colorScheme="green" isLoading={isSubmitting} loadingText="Saving..." isDisabled={isStagingLoading}>
            Save Knowledge Card
          </Button>
        </VStack>
      </form>
    </Container>
  );
}
