'use client';

import React, { useState, FormEvent, useCallback, useRef, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
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
  TagCloseButton
} from '@chakra-ui/react';
import {
  BlockNoteEditor as BlockNoteEditorType,
  PartialBlock,
} from '@blocknote/core';
import { useCardStore } from '@/stores/cardStore';
import dynamic from 'next/dynamic';
import type { UploadApiResponse } from '@/app/api/upload/image/route';

// Dynamically import BlockNoteEditor to prevent SSR issues
const BlockNoteEditor = dynamic(() => import('@/components/editor/BlockNoteEditor'), { 
  ssr: false,
  loading: () => (
    <Flex justify="center" align="center" height="200px">
      <Spinner size="xl" />
      <Text ml={4}>Loading Editor...</Text>
    </Flex>
  )
});

interface ErrorResponse {
  error: string;
  message?: string; // For more detailed error messages from the server
  details?: unknown; // Changed from any to unknown
}

export default function NewCardPage() {
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  const toast = useToast();
  const [title, setTitle] = useState('');
  
  // --- Keyword State and Handlers (Adapted from [cardId]/page.tsx) ---
  const [keywords, setKeywords] = useState<string[]>([]); // Array of keyword strings
  const [currentKeyword, setCurrentKeyword] = useState(''); // Current input value for a keyword
  // --- End Keyword State ---

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeUploads, setActiveUploads] = useState(0); // New state for active uploads
  const editorRef = useRef<BlockNoteEditorType | null>(null);
  const [editorContent, setEditorContent] = useState<
    PartialBlock[] | undefined
  >(undefined);
  const [uploadedImageMetadata, setUploadedImageMetadata] = useState<UploadApiResponse[]>([]);
  const addCard = useCardStore((state) => state.addCard);

  // New Ref to map blob URLs to their permanent metadata
  const blobUrlToPermanentDataMapRef = useRef<Record<string, { appServedUrl: string; gcsPath: string }>>({});

  // useEffect to log editorContent (can be kept or removed for cleaner logs now)
  useEffect(() => {
    if (editorContent) {
      // console.log('[NewCardPage] editorContent state updated:', JSON.parse(JSON.stringify(editorContent)));
      editorContent.forEach(block => {
        if (block.type === 'image') {
          // console.log('[NewCardPage] Image block in updated editorContent state:', JSON.parse(JSON.stringify(block.props)));
        }
      });
    }
  }, [editorContent]);

  const handleEditorInstanceReady = useCallback(
    (editorInstance: BlockNoteEditorType | null) => {
      editorRef.current = editorInstance;
      console.log('[NewCardPage] handleEditorInstanceReady: editor instance set in ref.');
    },
    [],
  );

  // --- Image Upload Callbacks ---
  const handleImageUploadStart = useCallback(() => {
    setActiveUploads(prev => prev + 1);
  }, []);

  const handleImageUploaded = useCallback((blobUrl: string, metadata: UploadApiResponse) => {
    console.log('[NewCardPage] handleImageUploaded (SUCCESS) called. BlobURL:', blobUrl, 'Metadata:', metadata);
    setUploadedImageMetadata((prev) => [...prev, metadata]); // Still store full metadata if needed elsewhere

    // Store the mapping from blobUrl to permanent data
    blobUrlToPermanentDataMapRef.current[blobUrl] = {
      appServedUrl: metadata.appServedUrl,
      gcsPath: metadata.gcsPath,
    };
    console.log('[NewCardPage] Stored mapping for blobUrl:', blobUrl, 'to:', blobUrlToPermanentDataMapRef.current[blobUrl]);

    // No longer trying to editor.updateBlock here for appServedUrl/gcsPath
    
    setActiveUploads(prev => {
      const nextActive = Math.max(0, prev - 1);
      console.log('[NewCardPage] activeUploads decremented to:', nextActive);
      return nextActive;
    });
  }, []); // No dependency on editorRef for this specific logic

  const handleImageUploadError = useCallback((error: Error) => {
    console.error("[NewCardPage] handleImageUploadError called. Error:", error);
    setActiveUploads(prev => {
      const nextActive = Math.max(0, prev - 1);
      console.log('[NewCardPage] activeUploads decremented (due to error) to:', nextActive);
      return nextActive;
    });
    toast({
      title: 'Image Upload Failed',
      description: error.message,
      status: 'error',
      duration: 5000,
      isClosable: true,
    });
  }, [toast]);
  // --- End Image Upload Callbacks ---

  // --- Keyword Handlers (Adapted from [cardId]/page.tsx) ---
  const handleKeywordInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentKeyword(e.target.value);
  };

  const handleKeywordInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && currentKeyword.trim() !== '') {
      e.preventDefault();
      // Ensure keyword is prefixed with #, prevent duplicates
      const newKeyword = currentKeyword.trim().startsWith('#')
        ? currentKeyword.trim()
        : `#${currentKeyword.trim()}`;
      if (!keywords.includes(newKeyword.toLowerCase())) { // Store keywords lowercase for consistency
        setKeywords([...keywords, newKeyword.toLowerCase()]);
      }
      setCurrentKeyword(''); // Clear input
    }
  };

  const removeKeyword = (keywordToRemove: string) => {
    setKeywords(keywords.filter((keyword) => keyword !== keywordToRemove));
  };
  // --- End Keyword Handlers ---

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    console.log('[NewCardPage] handleSubmit triggered.');
    
    const currentEditor = editorRef.current;
    if (!currentEditor) {
      toast({ title: 'Editor not ready', status: 'warning', duration: 3000 });
      return;
    }

    const currentEditorContent = currentEditor.topLevelBlocks;
    console.log('[NewCardPage] Content source for saving (currentEditor.topLevelBlocks from ref):', JSON.parse(JSON.stringify(currentEditorContent)));

    if (!title.trim() || !currentEditorContent || currentEditorContent.length === 0) {
      toast({ title: 'Title and content are required', status: 'warning', duration: 3000 });
      return;
    }

    setIsSubmitting(true);

    const processedEditorContent = currentEditorContent.map(block => {
      if (block.type === 'image' && block.props && block.props.url && block.props.url.startsWith('blob:')) {
        const blobUrl = block.props.url;
        console.log('[NewCardPage] Processing image block with blobUrl:', blobUrl);
        const permanentData = blobUrlToPermanentDataMapRef.current[blobUrl];
        
        if (permanentData) {
          console.log('[NewCardPage] Found permanent data for blobUrl:', permanentData);
          const newProps = {
            ...block.props, // Keep other props like caption, alt, etc.
            url: permanentData.appServedUrl, // Set the main URL to the permanent app-served URL
            appServedUrl: permanentData.appServedUrl, // Also store it explicitly
            gcsPath: permanentData.gcsPath,         // Also store it explicitly
          };
          console.log('[NewCardPage] Image block props updated for saving:', newProps);
          return { ...block, props: newProps };
        } else {
          console.warn('[NewCardPage] No permanent data found for blobUrl:', blobUrl, '. Keeping original block.');
        }
      }
      return block;
    });
    
    // console.log('[NewCardPage] Final processedEditorContent for API:', JSON.parse(JSON.stringify(processedEditorContent)));

    try {
      const response = await fetch('/api/cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          content: processedEditorContent,
          tags: keywords.map(kw => kw.startsWith('#') ? kw.substring(1).toLowerCase() : kw.toLowerCase()),
          // imageMetadata is still sent, containing all UploadApiResponse objects for the session
          // The backend can use this to create ImageMetadata entries if needed, linking them by gcsPath perhaps,
          // though the primary source of truth for the URL in the block is now processedEditorContent.
          imageMetadata: uploadedImageMetadata, 
        }),
      });

      if (!response.ok) {
        let serverError = 'Failed to create card.';
        try {
          const errorData = await response.json();
          serverError = (errorData as ErrorResponse)?.message || errorData.error || serverError;
        } catch {
          serverError = response.statusText || serverError;
        }
        throw new Error(serverError);
      }

      const newCardData = await response.json();

      toast({
        title: 'Card created successfully.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      setUploadedImageMetadata([]);
      router.push('/');
      // router.refresh(); // Consider if needed or if store update is sufficient

      // addCard({ // Adapt this to match your Zustand store's expected structure
      //   id: newCardData.id, 
      //   title: title.trim(),
      //   content: processedEditorContent,
      //   tags: keywords.map(kw => ({id: '', name: kw.startsWith('#') ? kw.substring(1).toLowerCase() : kw.toLowerCase()})), // Adapt if store expects Tag objects
      //   imageMetadata: uploadedImageMetadata.map(im => ({...im, id: '', knowledgeCardId: newCardData.id, userId: session.user.id /* Adapt */, createdAt: new Date(), updatedAt: new Date()})),
      //   folder: null, 
      //   isStarred: false, // Assuming your store uses isStarred
      //   createdAt: new Date().toISOString(), // Or use newCardData.createdAt
      //   updatedAt: new Date().toISOString(), // Or use newCardData.updatedAt
      // });

    } catch (error: unknown) {
      console.error('Create card error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Could not save the card.';
      toast({
        title: 'Error creating card.',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle loading and unauthenticated states
  if (sessionStatus === 'loading') {
    return (
      <Flex justify="center" align="center" height="80vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (sessionStatus === 'unauthenticated') {
    router.push('/api/auth/signin?callbackUrl=/cards/new');
    return (
      <Flex justify="center" align="center" height="80vh">
        <Text>Redirecting to sign in...</Text>
      </Flex>
    );
  }

  return (
    <Container maxW="container.lg" py={8} fontFamily="'Open Sans', sans-serif">
      <Heading
        as="h1"
        size="xl"
        mb={6}
        fontFamily="'Open Sans', sans-serif"
        fontSize="36px"
      >
        Create New Knowledge Card
      </Heading>
      <Box as="form" onSubmit={handleSubmit}>
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
              isDisabled={isSubmitting}
              fontFamily="'Open Sans', sans-serif"
              fontSize="16px"
            />
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
              onChange={handleKeywordInputChange}
              onKeyDown={handleKeywordInputKeyDown}
              placeholder="Type a keyword and press Enter"
              isDisabled={isSubmitting}
              fontFamily="'Open Sans', sans-serif"
              fontSize="16px"
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
                >
                  <TagLabel>{keyword}</TagLabel>
                  <TagCloseButton
                    onClick={() => removeKeyword(keyword)}
                    isDisabled={isSubmitting}
                  />
                </Tag>
              ))}
            </HStack>
          </FormControl>

          <FormControl isRequired>
            <FormLabel fontFamily="'Open Sans', sans-serif" fontSize="24px">
              Content
            </FormLabel>
            <BlockNoteEditor
              initialContent={editorContent}
              onChange={setEditorContent}
              onEditorReady={handleEditorInstanceReady}
              readOnly={false}
              onImageUploadStart={handleImageUploadStart}
              onImageUploaded={handleImageUploaded}
              onImageUploadError={handleImageUploadError}
            />
          </FormControl>

          {/* Buttons */}
          <Flex justify="flex-start" gap={3} mt={4}>
            {' '}
            {/* Use Flex for horizontal alignment and gap */}
            <Button
              colorScheme="green"
              type="submit"
              isLoading={isSubmitting || activeUploads > 0}
              isDisabled={isSubmitting || activeUploads > 0}
              fontFamily="'Open Sans', sans-serif"
              fontSize="16px"
            >
              Create Card
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push('/')}
              isDisabled={isSubmitting}
              fontFamily="'Open Sans', sans-serif"
              fontSize="16px"
            >
              Cancel
            </Button>
          </Flex>
        </VStack>
      </Box>
    </Container>
  );
}
