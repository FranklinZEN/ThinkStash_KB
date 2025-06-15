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
} from '@/lib/blocknote/appSchema';
import type { ContentBlock } from '@/types/api/ai-service';
import {
  mapPartialBlocksToAIServiceContentBlocks,
  mapContentBlocksToPartialBlocks,
} from '../../../lib/contentUtils';

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
        return block.content.every(inlineItem => {
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
              return linkContent.every(linkChild => {
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
      <Flex justify="center" align="center" minH="300px">
        <Spinner />
        <Text ml={3}>Loading Editor...</Text>
      </Flex>
    ),
  },
);

interface Tag {
  id: string;
  name: string;
}

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
  tags?: string[];
}

const SideBySideComparisonModal = ({
  isOpen,
  onClose,
  originalContent,
  rewrittenContent,
  onAccept,
  onDiscard,
  isLoadingRewrite,
  errorOnRewrite,
  currentProgressMessageForModal,
  modalEditorKey,
}: {
  isOpen: boolean;
  onClose: () => void;
  originalContent: AppPartialBlock[] | null | undefined;
  rewrittenContent: AppPartialBlock[] | null | undefined;
  onAccept: () => void;
  onDiscard: () => void;
  isLoadingRewrite: boolean;
  errorOnRewrite: string | null;
  currentProgressMessageForModal: string | null;
  modalEditorKey: number;
}) => {
  if (!originalContent) return null;

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
                <Text color="red.500">Error: {errorOnRewrite}</Text>
              ) : (
                <BlockNoteEditorComponent
                  key={`rewritten-comparison-${modalEditorKey}`}
                  initialContent={rewrittenContent ?? []}
                  editable={false}
                  onEditorChange={() => {}}
                  onContentUpdate={() => {}}
                />
              )}
            </Box>
          </Flex>
        </ModalBody>
        <ModalFooter>
          <Button
            colorScheme="red"
            mr={3}
            onClick={onDiscard}
            isDisabled={isLoadingRewrite}
          >
            Discard
          </Button>
          <Button
            colorScheme="green"
            onClick={onAccept}
            isDisabled={isLoadingRewrite || !!errorOnRewrite}
          >
            Accept and Use
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default function CardDetailPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const params = useParams();
  const cardId = params?.cardId as string;
  const toast = useToast();
  const {
    isOpen: isDeleteAlertOpen,
    onOpen: onDeleteAlertOpen,
    onClose: onDeleteAlertClose,
  } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);

  const [card, setCard] = useState<KnowledgeCard | null>(null);
  const [title, setTitle] = useState('');
  const [editorContent, setEditorContent] = useState<
    AppPartialBlock[] | undefined
  >(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isModified, setIsModified] = useState(false);
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagInput, setTagInput] = useState('');

  // AI Features State
  const [pollingTaskId, setPollingTaskId] = useState<string | null>(null);
  const [pollingTaskType, setPollingTaskType] = useState<string | null>(null);
  const [isLoadingRewrite, setIsLoadingRewrite] = useState(false);
  const [errorOnRewrite, setErrorOnRewrite] = useState<string | null>(null);
  const [rewrittenContent, setRewrittenContent] = useState<
    AppPartialBlock[] | null
  >(null);
  const {
    isOpen: isRewriteModalOpen,
    onOpen: onRewriteModalOpen,
    onClose: onRewriteModalClose,
  } = useDisclosure();
  const [currentProgressMessage, setCurrentProgressMessage] = useState<
    string | null
  >(null);
  const [modalEditorKey, setModalEditorKey] = useState(0);

  // New state for title suggestion
  const [suggestedTitle, setSuggestedTitle] = useState<string | null>(null);

  const onContentUpdate = useCallback((newContent: AppPartialBlock[]) => {
    if (JSON.stringify(newContent) !== JSON.stringify(editorContent)) {
      setEditorContent(newContent);
      setIsModified(true);
    }
  }, [editorContent]);

  useEffect(() => {
    if (cardId && session) {
      const fetchCard = async () => {
        setIsLoading(true);
        try {
          const response = await fetch(`/api/cards/${cardId}`);
          if (!response.ok) {
            if (response.status === 404) {
              toast({
                title: 'Not Found',
                description: 'This knowledge card could not be found.',
                status: 'error',
                duration: 5000,
                isClosable: true,
              });
              router.push('/dashboard');
            } else {
              throw new Error('Failed to fetch card');
            }
            return;
          }
          const data: KnowledgeCard = await response.json();
          setCard(data);
          setTitle(data.title);
          if (typeof data.content === 'string') {
            try {
              const parsedContent = JSON.parse(data.content);
              setEditorContent(parsedContent);
            } catch (e) {
              console.error('Failed to parse card content:', e);
              setEditorContent([{ type: 'paragraph', content: '' }]);
            }
          } else {
            setEditorContent(data.content ?? undefined);
          }
          setTags(data.tags);
        } catch (error) {
          console.error('Error fetching card:', error);
          toast({
            title: 'Error',
            description: 'There was an error loading the card.',
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
        } finally {
          setIsLoading(false);
        }
      };
      fetchCard();
    }
  }, [cardId, session, router, toast]);

  // EFFECT: Poll for task status
  useEffect(() => {
    if (pollingTaskId) {
      const interval = setInterval(async () => {
        try {
          const response = await fetch(`/api/tasks/${pollingTaskId}`);
          if (!response.ok) {
            throw new Error('Failed to fetch task status');
          }
          const task = await response.json();

          // Update progress message for all task types
          setCurrentProgressMessage(task.progressMessage || null);
          
          if (task.status === 'COMPLETED') {
            clearInterval(interval);
            setPollingTaskId(null);
            
            // Logic for different completed task types
            if (task.type === 'REWRITE_CONTENT' && task.result) {
                const parsedResult = typeof task.result === 'string' ? JSON.parse(task.result) : task.result;
                const newContent = parsedResult.rewritten_content; 
                setRewrittenContent(newContent);
                setIsLoadingRewrite(false);
            } else if (task.type === 'GENERATE_TITLE' && task.result) {
                const parsedResult = typeof task.result === 'string' ? JSON.parse(task.result) : task.result;
                const newTitle = parsedResult.generated_title;
                if (newTitle) {
                    setSuggestedTitle(newTitle);
                    toast({
                        title: 'New Title Suggested',
                        description: "The AI has generated a new title. Click 'Apply' to save it.",
                        status: 'success',
                        duration: 5000,
                        isClosable: true,
                    });
                } else {
                    toast({
                        title: 'Title generation complete',
                        description: "The AI finished, but didn't return a new title.",
                        status: 'warning',
                        duration: 5000,
                        isClosable: true,
                    });
                }
            } else if (task.type === 'GENERATE_KEYWORDS' && task.result) {
                // Future handling for keyword generation
            }

          } else if (task.status === 'FAILED') {
            clearInterval(interval);
            setPollingTaskId(null);
            const errorMessage = task.error?.userMessage || 'An unknown error occurred.';
            toast({
              title: 'Task Failed',
              description: `The ${task.type} task failed: ${errorMessage}`,
              status: 'error',
              duration: 9000,
              isClosable: true,
            });
            if (task.type === 'REWRITE_CONTENT') {
                setErrorOnRewrite(errorMessage);
                setIsLoadingRewrite(false);
            }
          }
        } catch (error) {
          console.error('Polling error:', error);
          clearInterval(interval);
          setPollingTaskId(null);
          toast({
            title: 'Error',
            description: 'Could not check task status.',
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
          if (pollingTaskType === 'REWRITE_CONTENT') {
             setErrorOnRewrite('Could not check task status due to a network or server error.');
             setIsLoadingRewrite(false);
          }
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [pollingTaskId, pollingTaskType, toast]);

  const handleSuggestTitle = async () => {
    if (!card) return;
    setSuggestedTitle(null); // Clear previous suggestion
    setPollingTaskType('GENERATE_TITLE');
    try {
      const response = await fetch('/api/ai/generate-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card_id: card.id }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to start title generation');
      }
      const { taskId } = await response.json();
      setPollingTaskId(taskId);
      toast({
        title: 'AI Title Generation Started',
        description: 'The AI is thinking of a new title...',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Error suggesting title:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'An unknown error occurred';
      toast({
        title: 'Error',
        description: `Could not start title generation: ${errorMessage}`,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleApplySuggestedTitle = () => {
    if (suggestedTitle) {
      setTitle(suggestedTitle);
      setIsModified(true);
      setSuggestedTitle(null);
      toast({
        title: 'Title Applied',
        description: "Don't forget to save your changes.",
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleKeywordsInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    setTagInput(event.target.value);
  };

  const handleKeywordsInputKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>,
  ) => {
    if (event.key === 'Enter' && tagInput.trim() !== '') {
      event.preventDefault();
      const newTagName = tagInput.trim();
      if (!tags.some(tag => tag.name === newTagName)) {
        // This is a temporary tag, doesn't have a real ID yet
        setTags([...tags, { id: `temp-${Date.now()}`, name: newTagName }]);
        setIsModified(true);
      }
      setTagInput('');
    }
  };

  const removeTag = (tagToRemove: Tag) => {
    setTags(tags.filter(tag => tag.id !== tagToRemove.id));
    setIsModified(true);
  };

  const handleGenerateKeywordsAIClick = async () => {
    // Placeholder for AI Keyword Generation
    toast({
      title: 'Coming Soon!',
      description: 'AI Keyword Generation is under development.',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };

  const handleRewriteContent = async () => {
    if (isEditorEmpty(editorContent)) {
      toast({
        title: 'Cannot Rewrite',
        description: 'There is no content to rewrite.',
        status: 'warning',
        duration: 4000,
        isClosable: true,
      });
      return;
    }
    setIsLoadingRewrite(true);
    setErrorOnRewrite(null);
    setRewrittenContent(null);
    setPollingTaskType('REWRITE_CONTENT');
    setModalEditorKey(prev => prev + 1); // Force remount of editors
    onRewriteModalOpen();

    try {
      const blocksForAI = mapPartialBlocksToAIServiceContentBlocks(
        editorContent ?? [],
        session?.user?.id ?? '',
        cardId
      );
      const response = await fetch('/api/ai/rewrite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_blocks: blocksForAI }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to start rewrite task');
      }
      const { taskId } = await response.json();
      setPollingTaskId(taskId);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'An unknown error occurred';
      console.error('Rewrite error:', error);
      setErrorOnRewrite(errorMessage);
      setIsLoadingRewrite(false);
    }
  };

  const handleAcceptRewrite = () => {
    if (rewrittenContent) {
      setEditorContent(rewrittenContent);
      setIsModified(true);
    }
    onRewriteModalClose();
  };

  const handleDiscardRewrite = () => {
    onRewriteModalClose();
  };

  const handleSaveChanges = async () => {
    if (!card) return;
    setIsSaving(true);
    try {
      const payload: CardUpdatePayload = {};
      if (title !== card.title) {
        payload.title = title;
      }
      if (editorContent && JSON.stringify(editorContent) !== JSON.stringify(card.content)) {
        payload.content = editorContent;
      }
      const newTagNames = tags.map(t => t.name);
      payload.tags = newTagNames;

      const response = await fetch(`/api/cards/${card.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error('Failed to save changes');
      }

      const updatedCard = await response.json();
      setCard(updatedCard);
      setTitle(updatedCard.title);
      setEditorContent(
        typeof updatedCard.content === 'string'
          ? JSON.parse(updatedCard.content)
          : updatedCard.content,
      );
      setTags(updatedCard.tags);
      setIsModified(false);

      toast({
        title: 'Success',
        description: 'Your changes have been saved.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Error saving changes:', error);
      toast({
        title: 'Error',
        description: 'Could not save your changes.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!card) return;
    try {
      const response = await fetch(`/api/cards/${card.id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error('Failed to delete the card');
      }
      toast({
        title: 'Card Deleted',
        description: 'The knowledge card has been successfully deleted.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      router.push('/dashboard');
    } catch (error) {
      console.error('Error deleting card:', error);
      toast({
        title: 'Error',
        description: 'Could not delete the card.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
    onDeleteAlertClose();
  };

  const handleSaveSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSaveChanges();
  };

  const handleDeleteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleDelete();
  };

  if (isLoading) {
    return (
      <Flex justify="center" align="center" h="100vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (!card) {
    return (
      <Flex justify="center" align="center" h="100vh">
        <Text>Card not found.</Text>
      </Flex>
    );
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={8} align="stretch">
        <form onSubmit={handleSaveSubmit}>
          {/* Main Header */}
          <Flex align="center" mb={6}>
            <Heading as="h1" size="xl">
              Edit Knowledge Card
            </Heading>
            <Spacer />
            <Button
              colorScheme="red"
              variant="outline"
              leftIcon={<DeleteIcon />}
              onClick={onDeleteAlertOpen}
              size="sm"
            >
              Delete
            </Button>
          </Flex>

          {/* Section 1: Title */}
          <VStack spacing={2} align="stretch" mb={8}>
            <FormControl isRequired>
              <FormLabel htmlFor="title">Title</FormLabel>
              <Input
                id="title"
                value={title}
                onChange={e => {
                  setTitle(e.target.value);
                  setIsModified(true);
                }}
                placeholder="Enter a title for your card"
              />
            </FormControl>
            {suggestedTitle && (
              <Box p={2} bg="green.100" borderRadius="md">
                <Flex align="center" justify="space-between">
                  <Text fontSize="sm">
                    <b>AI Suggestion:</b> {suggestedTitle}
                  </Text>
                  <HStack>
                      <Button size="xs" colorScheme="green" onClick={handleApplySuggestedTitle}>Apply</Button>
                      <Button size="xs" variant="ghost" onClick={() => setSuggestedTitle(null)}>Dismiss</Button>
                  </HStack>
                </Flex>
              </Box>
            )}
            <HStack>
                <Button
                    colorScheme="blue"
                    onClick={handleSuggestTitle}
                    isLoading={pollingTaskType === 'GENERATE_TITLE' && !!pollingTaskId}
                    loadingText="Thinking..."
                    size="sm"
                >
                    Suggest Title
                </Button>
            </HStack>
          </VStack>

          {/* Section 2: Tags / Keywords */}
          <VStack spacing={2} align="stretch" mb={8}>
            <FormControl>
              <FormLabel>Tags</FormLabel>
              <HStack spacing={2} wrap="wrap">
                {tags.map(tag => (
                  <ChakraTag
                    key={tag.id}
                    size="md"
                    borderRadius="full"
                    variant="solid"
                    colorScheme="blue"
                  >
                    <TagLabel>{tag.name}</TagLabel>
                    <IconButton
                      aria-label="Remove tag"
                      icon={<DeleteIcon />}
                      size="xs"
                      isRound
                      variant="ghost"
                      color="whiteAlpha.800"
                      onClick={() => removeTag(tag)}
                      ml={1}
                    />
                  </ChakraTag>
                ))}
              </HStack>
              <Input
                mt={2}
                value={tagInput}
                onChange={handleKeywordsInputChange}
                onKeyDown={handleKeywordsInputKeyDown}
                placeholder="Type a tag and press Enter"
              />
            </FormControl>
            <HStack>
                <Button
                    colorScheme="teal"
                    onClick={handleGenerateKeywordsAIClick}
                    isDisabled
                    size="sm"
                >
                    Generate Keywords (AI)
                </Button>
            </HStack>
          </VStack>
          
          {/* Section 3: Content */}
          <VStack spacing={2} align="stretch" mb={8}>
            <FormControl>
              <FormLabel>Content</FormLabel>
              <Box borderWidth="1px" borderRadius="lg" p={1}>
                <BlockNoteEditorComponent
                  key={cardId}
                  initialContent={editorContent}
                  editable={true}
                  onEditorChange={() => {}}
                  onContentUpdate={onContentUpdate}
                />
              </Box>
            </FormControl>
             <HStack>
                <Button
                    colorScheme="purple"
                    onClick={handleRewriteContent}
                    isLoading={isLoadingRewrite}
                    loadingText="Rewriting..."
                    size="sm"
                >
                    AI Rewrite
                </Button>
            </HStack>
          </VStack>

          {/* Global Save Action */}
          <Flex mt={6}>
            <Spacer />
            <Button
              type="submit"
              colorScheme="green"
              isLoading={isSaving}
              isDisabled={!isModified || isSaving}
            >
              Save Changes
            </Button>
          </Flex>
        </form>
      </VStack>

      <AlertDialog
        isOpen={isDeleteAlertOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteAlertClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <form onSubmit={handleDeleteSubmit}>
              <AlertDialogHeader fontSize="lg" fontWeight="bold">
                Delete Knowledge Card
              </AlertDialogHeader>
              <AlertDialogBody>
                Are you sure you want to delete this card? This action cannot be
                undone.
              </AlertDialogBody>
              <AlertDialogFooter>
                <Button ref={cancelRef} onClick={onDeleteAlertClose}>
                  Cancel
                </Button>
                <Button colorScheme="red" type="submit" ml={3}>
                  Delete
                </Button>
              </AlertDialogFooter>
            </form>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      <SideBySideComparisonModal
        isOpen={isRewriteModalOpen}
        onClose={onRewriteModalClose}
        originalContent={editorContent}
        rewrittenContent={rewrittenContent}
        onAccept={handleAcceptRewrite}
        onDiscard={handleDiscardRewrite}
        isLoadingRewrite={isLoadingRewrite}
        errorOnRewrite={errorOnRewrite}
        currentProgressMessageForModal={currentProgressMessage}
        modalEditorKey={modalEditorKey}
      />
    </Container>
  );
}