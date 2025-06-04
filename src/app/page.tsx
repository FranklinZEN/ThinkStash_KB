'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Box,
  Heading,
  Text,
  Button,
  SimpleGrid,
  Spinner,
  Flex,
  Center,
  VStack,
  Alert,
  AlertIcon,
  HStack,
  Input,
  InputGroup,
  InputLeftElement,
  Icon,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  useToast,
} from '@chakra-ui/react';
import CardListItem from '@/components/cards/CardListItem';
import { useCardStore } from '@/stores/cardStore';
import SearchResults from '@/components/search/SearchResults';
import { fetchWithAuth } from '@/lib/fetchWithAuth';
import {
  KnowledgeCard as PrismaKnowledgeCard,
  Folder as PrismaFolder,
} from '@prisma/client';
import { SearchIcon } from '@chakra-ui/icons';

import { useStagingCardStore } from '@/stores/stagingCardStore';
import { mapContentBlocksToPartialBlocks } from '@/lib/contentUtils';
import type { OrchestrationOutput } from '@/types/api/ai-service';
import type { AppPartialBlock } from '@/lib/blocknote/appSchema';

interface SearchResultCard extends Omit<PrismaKnowledgeCard, 'content'> {
  content: AppPartialBlock[] | string | null;
  folder: Pick<PrismaFolder, 'id' | 'name'> | null;
  headline?: string;
}

export default function Home() {
  const { status } = useSession();
  const router = useRouter();
  const toast = useToast();
  const {
    cards,
    pagination,
    isLoading: isLoadingCards,
    error: cardError,
    fetchCards,
  } = useCardStore();

  const { startLoading, setData: setStagedData, setError: setStagedError, isLoading: isStaging } = useStagingCardStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultCard[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const { isOpen: isUrlModalOpen, onOpen: onOpenUrlModal, onClose: onCloseUrlModal } = useDisclosure();
  const { isOpen: isFileModalOpen, onOpen: onOpenFileModal, onClose: onCloseFileModal } = useDisclosure();

  const [reconstructUrl, setReconstructUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  useEffect(() => {
    if (status === 'authenticated') {
      fetchCards(1);
    }
  }, [status, fetchCards]);

  const performSearch = useCallback(
    async (query: string) => {
      setSearchQuery(query);
      if (!query) {
        setSearchResults([]);
        setIsSearching(false);
        setSearchError(null);
        if (status === 'authenticated') fetchCards(1);
        return;
      }
      setIsSearching(true);
      setSearchError(null);
      try {
        const response = await fetchWithAuth(
          `/api/search?q=${encodeURIComponent(query)}`,
        );
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.error || `HTTP error! status: ${response.status}`,
          );
        }
        const data: SearchResultCard[] = await response.json();
        setSearchResults(data);
      } catch (err) {
        console.error('Search failed:', err);
        setSearchError(
          err instanceof Error ? err.message : 'An unknown error occurred',
        );
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    },
    [status, fetchCards],
  );

  const normalizeUrlInput = (url: string): string => {
    let normalized = url.trim();

    // Remove chrome-extension://<any_id>/ prefix
    const chromeExtensionPattern = /^chrome-extension:\/\/[^/]+\//;
    normalized = normalized.replace(chromeExtensionPattern, '');

    // Ensure it has a scheme, default to https://
    if (!normalized.match(/^[^:/\/?#]+:\/\//)) {
      normalized = `https://${normalized}`;
    }
    return normalized;
  };

  const handleReconstructFromUrl = async () => {
    if (!reconstructUrl.trim()) {
      toast({ title: 'URL is required', status: 'error', duration: 3000, isClosable: true });
      return;
    }
    startLoading();
    try {
      const normalizedUrl = normalizeUrlInput(reconstructUrl.trim());
      console.log("Normalized URL for reconstruction:", normalizedUrl); // Added for debugging

      const response = await fetch('/api/ai/reconstruct-and-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: normalizedUrl }),
      });
      const data: OrchestrationOutput = await response.json();

      if (!response.ok || data.error_message || !data.status_code.startsWith('success')) {
        const errorMsg = data.error_message || 'Failed to reconstruct from URL.';
        throw new Error(errorMsg);
      }
      
      const titleToSet = data.extracted_title || data.document_metadata?.title || ''; 
      const keywordsToSet: string[] = [];

      setStagedData(titleToSet, data.original_content_blocks, keywordsToSet);
      toast({ title: 'Content Reconstructed!', description: 'Navigating to create card page...', status: 'success', duration: 2000, isClosable: true });
      onCloseUrlModal();
      setReconstructUrl('');
      router.push('/cards/new');

    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'An unknown reconstruction error occurred.';
      console.error('Reconstruction from URL failed:', errMsg);
      setStagedError(errMsg);
      toast({ title: 'Reconstruction Failed', description: errMsg, status: 'error', duration: 5000, isClosable: true });
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
    } else {
      setSelectedFile(null);
    }
  };

  const handleReconstructFromFile = async () => {
    if (!selectedFile) {
      toast({ title: 'Please select a file.', status: 'warning', duration: 3000, isClosable: true });
      return;
    }
    startLoading();
    
    try {
      // Step 1: Upload the file to GCS
      const formData = new FormData();
      formData.append('file', selectedFile);

      const uploadResponse = await fetch('/api/files/upload', {
        method: 'POST',
        body: formData,
        // headers: { 'Content-Type': 'multipart/form-data' } // Not needed, browser sets it with boundary
      });

      if (!uploadResponse.ok) {
        const uploadErrorData = await uploadResponse.json();
        throw new Error(uploadErrorData.error || `File upload failed with status: ${uploadResponse.status}`);
      }

      const uploadResult = await uploadResponse.json();
      const fileId = uploadResult.file_id; // This should be the gs:// path

      if (!fileId) {
        throw new Error('File ID not received from upload service.');
      }

      toast({ title: 'File Uploaded!', description: 'Now reconstructing content...', status: 'info', duration: 2000, isClosable: true });

      // Step 2: Call reconstruct-and-analyze with the file_id
      const reconstructResponse = await fetch('/api/ai/reconstruct-and-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: fileId }), // Sending file_id instead of source_url
      });

      const reconstructData: OrchestrationOutput = await reconstructResponse.json();

      if (!reconstructResponse.ok || reconstructData.error_message || !reconstructData.status_code.startsWith('success')) {
        const errorMsg = reconstructData.error_message || 'Failed to reconstruct from file.';
        throw new Error(errorMsg);
      }
      
      const titleToSet = reconstructData.extracted_title || reconstructData.document_metadata?.title || selectedFile.name.split('.')[0].replace(/_/g, ' ') || 'Untitled Card'; 
      const keywordsToSet: string[] = []; // Keywords are not auto-generated at this stage

      setStagedData(titleToSet, reconstructData.original_content_blocks, keywordsToSet);
      toast({ title: 'Content Reconstructed!', description: 'Navigating to create card page...', status: 'success', duration: 2000, isClosable: true });
      onCloseFileModal();
      setSelectedFile(null);
      router.push('/cards/new');

    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'An unknown error occurred during file processing.';
      console.error('Reconstruction from file failed:', errMsg);
      setStagedError(errMsg);
      toast({ title: 'Processing Failed', description: errMsg, status: 'error', duration: 5000, isClosable: true });
    }
  };

  const handlePreviousPage = () => {
    if (pagination && pagination.page > 1) {
      fetchCards(pagination.page - 1, pagination.pageSize);
    }
  };

  const handleNextPage = () => {
    if (pagination && pagination.page < pagination.totalPages) {
      fetchCards(pagination.page + 1, pagination.pageSize);
    }
  };

  if (status === 'loading') {
    return (
      <Flex
        justify="center"
        align="center"
        height="calc(100vh - 64px)"
      >
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
    return (
      <Center height="calc(100vh - 64px)" >
        <VStack spacing={4}>
          <Heading fontFamily="'Open Sans', sans-serif">
            Welcome to ThinkStash!
          </Heading>
          <Text fontFamily="'Open Sans', sans-serif">
            Your dynamic personal knowledge base.
          </Text>
          <Text fontFamily="'Open Sans', sans-serif">
            Please sign in or sign up to manage your cards.
          </Text>
          <Flex gap={4} mt={4}>
            <Link href="/auth/signin">
              <Button colorScheme="blue" fontFamily="'Open Sans', sans-serif">
                Sign In
              </Button>
            </Link>
            <Link href="/auth/signup">
              <Button colorScheme="teal" fontFamily="'Open Sans', sans-serif">
                Sign Up
              </Button>
            </Link>
          </Flex>
        </VStack>
      </Center>
    );
  }

  return (
    <Flex
      direction="column"
      alignItems="center"
      width="100%"
      minHeight="calc(100vh - 64px)"
      bg="#F5F5F5"
    >
      <Box
        width="100%"
        maxWidth="1280px"
      >
        <Flex
          px={{ base: '20px', md: '40px' }}
          py="12px"
          height="65px"
          borderBottom="1px solid #E6E8EB"
          alignItems="center"
          justifyContent="space-between"
          bg="white"
        >
          <Heading
            as="h2"
            fontFamily="'Open Sans', sans-serif"
            fontWeight="700"
            fontSize="30px"
            lineHeight="23px"
            color="#141414"
          >
            Knowledge Card Exhibition
          </Heading>

          <HStack
            spacing="16px"
          >
            <InputGroup
              width={{ base: '150px', md: '256px' }}
              size="md"
            >
              <InputLeftElement pointerEvents="none">
                <Icon as={SearchIcon} color="#707070" />
              </InputLeftElement>
              <Input
                type="search"
                placeholder="Search"
                bg="#E8E8E8"
                borderRadius="12px"
                border="none"
                fontFamily="'Open Sans', sans-serif"
                fontSize="16px"
                color="#707070"
                _placeholder={{ color: '#707070' }}
                onChange={(e) => performSearch(e.target.value)}
              />
            </InputGroup>

            <HStack spacing="8px">
              <Menu>
                <MenuButton
                  as={Button}
                  bg="white"
                  boxShadow="inset 0px 1px 3px rgba(0, 0, 0, 0.2)"
                  borderRadius="20px"
                  height="40px"
                  px="16px"
                  fontFamily="'Open Sans', sans-serif"
                  fontWeight="700"
                  fontSize="14px"
                  color="#141414"
                  lineHeight="21px"
                  isDisabled={isStaging}
                >
                  Create New Card
                </MenuButton>
                <MenuList>
                  <Link href="/cards/new" passHref legacyBehavior>
                    <MenuItem as="a">Manual Input</MenuItem>
                  </Link>
                  <MenuItem onClick={onOpenUrlModal}>Create from URL</MenuItem>
                  <MenuItem onClick={onOpenFileModal}>Attach Document</MenuItem>
                </MenuList>
              </Menu>
            </HStack>
          </HStack>
        </Flex>

        <Flex
          direction={{ base: 'column', md: 'row' }}
          px={{ base: '10px', md: '24px' }}
          py="20px"
          gap="16px"
          flex="1"
        >
          <Box
            flex="1"
          >
            {searchQuery && (
              <SearchResults
                results={searchResults}
                isLoading={isSearching}
                error={searchError}
                searchQuery={searchQuery}
                mutateResults={() => fetchCards(1)}
              />
            )}

            {!searchQuery && (
              <>
                {isLoadingCards && (
                  <Center py={10}>
                    <Spinner size="lg" />
                  </Center>
                )}
                {cardError && (
                  <Alert status="error" borderRadius="md" my={4}>
                    <AlertIcon />
                    {cardError}
                  </Alert>
                )}
                {!isLoadingCards &&
                  !cardError &&
                  cards.length === 0 &&
                  pagination &&
                  pagination.totalItems === 0 && (
                    <Center
                      py={10}
                      borderWidth="1px"
                      borderRadius="md"
                      bg="white"
                      my={4}
                    >
                      <Text fontFamily="'Open Sans', sans-serif">
                        You haven&apos;t created any knowledge cards yet. Get
                        started by creating one!
                      </Text>
                    </Center>
                  )}
                {!isLoadingCards && !cardError && cards.length > 0 && (
                  <SimpleGrid
                    columns={{ base: 1, md: 2, lg: 3 }}
                    spacing={6}
                    py={4}
                  >
                    {cards.map((card) => (
                      <CardListItem
                        key={card.id}
                        card={card}
                        mutate={() =>
                          fetchCards(pagination?.page, pagination?.pageSize)
                        }
                      />
                    ))}
                  </SimpleGrid>
                )}
                {!isLoadingCards && pagination && pagination.totalPages > 1 && (
                  <Flex justifyContent="center" mt={8} mb={4}>
                    <HStack spacing={4}>
                      <Button
                        onClick={handlePreviousPage}
                        isDisabled={pagination.page <= 1 || isLoadingCards}
                        fontFamily="'Open Sans', sans-serif"
                      >
                        Previous
                      </Button>
                      <Text fontFamily="'Open Sans', sans-serif">
                        Page {pagination.page} of {pagination.totalPages}
                      </Text>
                      <Button
                        onClick={handleNextPage}
                        isDisabled={
                          pagination.page >= pagination.totalPages ||
                          isLoadingCards
                        }
                        fontFamily="'Open Sans', sans-serif"
                      >
                        Next
                      </Button>
                    </HStack>
                  </Flex>
                )}
              </>
            )}
          </Box>
        </Flex>
      </Box>

      <Modal isOpen={isUrlModalOpen} onClose={onCloseUrlModal} isCentered>
        <ModalOverlay />
        <ModalContent as="form" onSubmit={(e) => { e.preventDefault(); handleReconstructFromUrl(); }}>
          <ModalHeader>Create Card from URL</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <FormControl isRequired>
              <FormLabel>URL to Reconstruct</FormLabel>
              <Input
                placeholder="https://example.com/article"
                value={reconstructUrl}
                onChange={(e) => setReconstructUrl(e.target.value)}
                isDisabled={isStaging}
              />
            </FormControl>
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" mr={3} type="submit" isLoading={isStaging} loadingText="Reconstructing...">
              Reconstruct
            </Button>
            <Button variant="ghost" onClick={onCloseUrlModal} isDisabled={isStaging}>Cancel</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal isOpen={isFileModalOpen} onClose={onCloseFileModal} isCentered>
        <ModalOverlay />
        <ModalContent as="form" onSubmit={(e) => { e.preventDefault(); handleReconstructFromFile(); }}>
          <ModalHeader>Create Card from Document</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <FormControl isRequired>
              <FormLabel>Document to Upload</FormLabel>
              <Input
                type="file"
                onChange={handleFileChange}
                isDisabled={isStaging}
                accept=".pdf,.doc,.docx,.txt,.md"
                sx={{
                  '::file-selector-button': {
                    border: 'none', outline: 'none', mr: 2, py: 2, px: 3,
                    borderRadius: 'md', bg: 'gray.100', color: 'gray.700',
                    cursor: 'pointer', _hover: { bg: 'gray.200' },
                  },
                }}
              />
            </FormControl>
            {selectedFile && <Text mt={2} fontSize="sm">Selected: {selectedFile.name}</Text>}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" mr={3} type="submit" isLoading={isStaging} loadingText="Processing..." isDisabled={!selectedFile}>
              Import from File
            </Button>
            <Button variant="ghost" onClick={onCloseFileModal} isDisabled={isStaging}>Cancel</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

    </Flex>
  );
}
