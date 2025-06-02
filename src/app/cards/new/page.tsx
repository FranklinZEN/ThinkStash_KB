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
  RadioGroup,
  Radio,
  Stack,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Collapse,
} from '@chakra-ui/react';
import {
  BlockNoteEditor as BlockNoteEditorType,
  PartialBlock,
} from '@blocknote/core';
import type { OrchestrationOutput, ContentBlock as AIServiceContentBlock } from '@/types/api/ai-service';

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

type CreationMode = 'manual' | 'url' | 'file';

// Function to map AIServiceContentBlock to BlockNote PartialBlock
const mapContentBlocksToPartialBlocks = (
  aiBlocks: AIServiceContentBlock[],
): PartialBlock[] => {
  if (!aiBlocks) return [];
  return aiBlocks.map((block) => {
    let partialBlock: PartialBlock = {
      type: 'paragraph',
      content: [{ type: 'text', text: '', styles: {} }], // Default empty paragraph
    };

    switch (block.type) {
      case 'text':
        partialBlock = {
          type: 'paragraph',
          content: block.content ? [{ type: 'text', text: block.content, styles: {} }] : [],
        };
        break;
      case 'heading':
        partialBlock = {
          type: 'heading',
          props: {
            level: (block.level && block.level >= 1 && block.level <= 3 ? block.level : 1) as 1 | 2 | 3,
          },
          content: block.content ? [{ type: 'text', text: block.content, styles: {} }] : [],
        };
        break;
      case 'list':
        partialBlock = {
          type: block.ordered ? 'numberedListItem' : 'bulletListItem',
          content: block.items
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ? (block.items as any[]).map((item) => (
                typeof item === 'string'
                  ? { type: 'text', text: item, styles: {} }
                  : { type: 'text', text: JSON.stringify(item), styles: {} } // Fallback for complex items
              ))
            : [],
        };
        break;
      case 'image':
        if (block.gcs_url) {
          // The gcs_url from the backend should now be a fully signed HTTPS URL
          console.log('[ImageDebug] Received URL from API (should be signed):', block.gcs_url);
          
          partialBlock = {
            type: 'image',
            props: {
              url: block.gcs_url, // Use the URL directly
              caption: block.caption || '',
            },
            children: [], 
          };
        }
        break;
      case 'code_snippet':
        partialBlock = {
          type: 'paragraph', // BlockNote might have a 'codeBlock' or similar, using paragraph for now
          content: [
            { type: 'text', text: `Code (${block.language || ''}):`, styles: { bold: true } },
            { type: 'text', text: '\n' + (block.content || ''), styles: {} },
          ],
        };
        break;
      // Add more cases for other block types as needed (e.g., table, math_text)
      default:
        partialBlock = {
          type: 'paragraph',
          content: [
            { type: 'text', text: `[Unsupported Block Type: ${block.type}] `, styles: { italic: true } },
            { type: 'text', text: block.content || '', styles: {} },
          ],
        };
    }
    return partialBlock;
  });
};

export default function NewCardPage() {
  const { status } = useSession();
  const router = useRouter();
  const toast = useToast();

  const [title, setTitle] = useState('');
  const [_editor, setEditor] = useState<BlockNoteEditorType | null>(null);
  const [editorContent, setEditorContent] = useState<
    PartialBlock[] | undefined
  >(undefined);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [currentKeyword, setCurrentKeyword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [creationMode, setCreationMode] = useState<CreationMode>('manual');
  const [reconstructUrl, setReconstructUrl] = useState('');
  const [isReconstructing, setIsReconstructing] = useState(false);
  const [reconstructionError, setReconstructionError] = useState<string | null>(
    null,
  );
  const [reconstructedData, setReconstructedData] = useState<OrchestrationOutput | null>(null);

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

  const handleReconstructFromUrl = async () => {
    if (!reconstructUrl.trim()) {
      toast({ title: 'URL is required', status: 'error' });
      return;
    }
    setIsReconstructing(true);
    setReconstructionError(null);
    setReconstructedData(null);

    try {
      const response = await fetch('/api/ai/reconstruct-and-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: reconstructUrl.trim() }),
      });

      const data: OrchestrationOutput = await response.json();
      console.log('[TitleDebug] OrchestrationOutput data:', JSON.stringify(data, null, 2));

      if (!response.ok) {
        throw new Error(data.error_message || 'Failed to reconstruct content from URL');
      }
      
      setReconstructedData(data);
      const titleToSet = data.extracted_title || data.document_metadata?.title || '';
      console.log('[TitleDebug] Setting title to:', titleToSet);
      setTitle(titleToSet);

      const mappedBlocks = mapContentBlocksToPartialBlocks(data.original_content_blocks);

      if (_editor) {
        // _editor.replaceBlocks(_editor.document, data.original_content_blocks as PartialBlock[]);
        _editor.replaceBlocks(_editor.document, mappedBlocks);
      } else {
        // setEditorContent(data.original_content_blocks as PartialBlock[]);
        setEditorContent(mappedBlocks);
      }
      toast({ title: 'Content reconstructed successfully!', status: 'success' });
      setCreationMode('manual');

    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'An unknown error occurred';
      setReconstructionError(errMsg);
      toast({ title: 'Reconstruction Failed', description: errMsg, status: 'error' });
    } finally {
      setIsReconstructing(false);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (isReconstructing) {
        toast({ title: 'Please wait for reconstruction to complete.', status: 'warning'});
        return;
    }

    setIsSubmitting(true);

    const currentBlocks = _editor ? _editor.document : editorContent;

    if (!title.trim()) {
      toast({
        title: 'Title is required',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    if (isEditorEmpty(currentBlocks)) {
      toast({
        title: 'Content cannot be empty',
        description: 'Please add some content to your card.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    const cardData = {
      title: title.trim(),
      content: currentBlocks || [],
      tags: keywords.map((kw) => (kw.startsWith('#') ? kw.substring(1) : kw)),
      folderId: null,
    };

    console.log('Creating card with data (content stringified):', {
      ...cardData,
      content: JSON.stringify(cardData.content),
    });

    try {
      const response = await fetch('/api/cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cardData),
      });

      const responseData = (await response.json()) as
        | CreateCardSuccessResponse
        | CreateCardErrorResponse;
      console.log('API response for new card:', responseData);

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
        if (errorResponse.details) {
          console.error('Validation Details:', errorResponse.details);
        }
        const message = errorResponse.error || errorResponse.message || 'Failed to create card';
        toast({
          title: 'Error Creating Card',
          description: message,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error('Submit Card Error:', error);
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

  if (status === 'loading') {
    return (
      <Flex justify="center" align="center" minH="100vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
    router.push('/auth/signin');
    return null;
  }

  return (
    <Container maxW="container.lg" py={8}>
      <Heading mb={6}>Create New Knowledge Card</Heading>

      <FormControl mb={6}>
        <FormLabel>Creation Mode</FormLabel>
        <RadioGroup onChange={(value) => setCreationMode(value as CreationMode)} value={creationMode}>
          <Stack direction="row" spacing={4}>
            <Radio value="manual">Manual Input</Radio>
            <Radio value="url">Import from URL</Radio>
            {/* <Radio value="file" isDisabled>Import from File (Coming Soon)</Radio> */}
          </Stack>
        </RadioGroup>
      </FormControl>

      <Collapse in={creationMode === 'url'} animateOpacity>
        <VStack spacing={4} mb={6} as="form" onSubmit={(e) => { e.preventDefault(); handleReconstructFromUrl(); }}>
          <FormControl isRequired>
            <FormLabel htmlFor="reconstructUrl">URL to Reconstruct</FormLabel>
            <Input
              id="reconstructUrl"
              type="url"
              placeholder="https://example.com/article"
              value={reconstructUrl}
              onChange={(e) => setReconstructUrl(e.target.value)}
              isDisabled={isReconstructing}
            />
          </FormControl>
          <Button 
            type="submit"
            colorScheme="blue"
            isLoading={isReconstructing}
            loadingText="Reconstructing..."
            w="full"
          >
            Import and Reconstruct from URL
          </Button>
          {reconstructionError && (
            <Alert status="error" mt={4}>
              <AlertIcon />
              <AlertTitle mr={2}>Reconstruction Failed!</AlertTitle>
              <AlertDescription>{reconstructionError}</AlertDescription>
            </Alert>
          )}
        </VStack>
      </Collapse>
      
      <Collapse in={creationMode === 'manual' || !!reconstructedData} animateOpacity>
        <form onSubmit={handleSubmit}>
          <VStack spacing={6} align="stretch">
            {/* <Text>DEBUG Current Title State: "{title}"</Text> */}

            <FormControl isRequired>
              <FormLabel htmlFor="title">Title</FormLabel>
              <Input
                id="title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter card title"
                isDisabled={isSubmitting || isReconstructing}
              />
            </FormControl>

            <FormControl>
              <FormLabel>Content</FormLabel>
              <Box borderWidth="1px" borderRadius="lg" p={1} minH="300px">
                <BlockNoteEditorComponent
                  initialContent={editorContent}
                  onContentUpdate={handleEditorContentUpdate}
                  onEditorChange={handleEditorInstanceReady}
                  editable={!(isSubmitting || isReconstructing)}
                />
              </Box>
            </FormControl>

            <FormControl>
              <FormLabel htmlFor="keywords">Keywords (Tags)</FormLabel>
              <HStack spacing={2} wrap="wrap" mb={2}>
                {keywords.map((keyword) => (
                  <Tag
                    key={keyword}
                    borderRadius="full"
                    variant="solid"
                    colorScheme="teal"
                  >
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
                isDisabled={isSubmitting || isReconstructing}
              />
            </FormControl>

            <Button
              type="submit"
              colorScheme="green"
              isLoading={isSubmitting}
              loadingText="Saving..."
              isDisabled={isReconstructing}
            >
              Save Knowledge Card
            </Button>
          </VStack>
        </form>
      </Collapse>
    </Container>
  );
}
