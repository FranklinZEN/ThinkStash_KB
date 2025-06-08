'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
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
} from '@chakra-ui/react';
import CardListItem from '@/components/cards/CardListItem';
import { useCardStore } from '@/stores/cardStore';
import SearchResults from '@/components/search/SearchResults';
import { fetchWithAuth } from '@/lib/fetchWithAuth';
import {
  KnowledgeCard as PrismaKnowledgeCard,
  Folder as PrismaFolder,
} from '@prisma/client';
import type { BlockNoteDocument } from '@/types/blocknote';
import { SearchIcon } from '@chakra-ui/icons';

interface SearchResultCard extends Omit<PrismaKnowledgeCard, 'content'> {
  content: BlockNoteDocument | string | null;
  folder: Pick<PrismaFolder, 'id' | 'name'> | null;
  headline?: string;
}

export default function Home() {
  const { status } = useSession();
  const {
    cards,
    pagination,
    isLoading: isLoadingCards,
    error: cardError,
    fetchCards,
  } = useCardStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultCard[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

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
        height="calc(100vh - 64px)" /* Adjust for layout header */
      >
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
    return (
      <Center height="calc(100vh - 64px)" /* Adjust for layout header */>
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

  // Authenticated view
  return (
    // Overall Page Container (Depth 0, Frame 0 from CSS)
    <Flex
      direction="column"
      alignItems="center" // Center the 1280px content block
      width="100%"
      minHeight="calc(100vh - 64px)" // Full height minus main layout header
      bg="#F5F5F5" // background: #F5F5F5;
      // py="20px" // Padding for the outer container if needed, CSS implies padding is within children
    >
      <Box
        width="100%"
        maxWidth="1280px" // width: 1280px;
      >
        {/* Internal Header Bar (Depth 2, Frame 0 from CSS) */}
        <Flex
          px={{ base: '20px', md: '40px' }} // padding: 12px 40px; (horizontal part)
          py="12px" // padding: 12px 40px; (vertical part)
          height="65px" // height: 65px;
          borderBottom="1px solid #E6E8EB" // border-bottom: 1px solid #E6E8EB;
          alignItems="center"
          justifyContent="space-between"
          bg="white" // CSS for Depth 2, Frame 0 doesn't specify bg, so assume white or transparent to #F5F5F5. Let's use white for typical header bar.
        >
          {/* Left part of internal header: "Your Knowledge Cards" (Depth 3, Frame 0) */}
          <Heading
            as="h2"
            // width: 200px, height: 23px (for text itself)
            // gap: 16px with icon
            fontFamily="'Open Sans', sans-serif" // Was 'Work Sans'
            fontWeight="700"
            fontSize="30px" // font-size: 30px;
            lineHeight="23px" // line-height: 23px;
            color="#141414" // color: #141414;
          >
            {/* Icon from Depth 5, Frame 0 - optional for now, or add Chakra icon */}
            Knowledge Card Exhibition
          </Heading>

          {/* Right part of internal header (Depth 3, Frame 1) */}
          <HStack
            spacing="16px" /* gap: 32px in CSS is between search and buttons group, 8px within buttons group */
          >
            {/* Search Input (Depth 4, Frame 0 / Depth 5, Frame 0 / Depth 6) */}
            <InputGroup
              width={{ base: '150px', md: '256px' }} // width: 256px; max-width: 256px;
              size="md" // Corresponds to height: 40px;
            >
              <InputLeftElement pointerEvents="none">
                <Icon as={SearchIcon} color="#707070" />
              </InputLeftElement>
              <Input
                type="search"
                placeholder="Search" // Search text from CSS
                bg="#E8E8E8" // background: #E8E8E8;
                borderRadius="12px" // border-radius: 12px; (applied to group or input)
                border="none" // CSS shows no border on the input itself, bg makes it distinct
                fontFamily="'Open Sans', sans-serif" // Was 'Work Sans'
                fontSize="16px"
                color="#707070"
                _placeholder={{ color: '#707070' }}
                onChange={(e) => performSearch(e.target.value)}
              />
            </InputGroup>

            {/* Buttons Group (Depth 4, Frame 1) */}
            <HStack spacing="8px">
              <Link href="/cards/new" passHref>
                <Button
                  // width: 149px; height: 40px;
                  // background: #FFFFFF; box-shadow: inset ...; border-radius: 20px;
                  bg="white"
                  boxShadow="inset 0px 1px 3px rgba(0, 0, 0, 0.2)" // Simplified shadow
                  borderRadius="20px"
                  height="40px"
                  px="16px"
                  fontFamily="'Open Sans', sans-serif" // Was 'Work Sans'
                  fontWeight="700"
                  fontSize="14px"
                  color="#141414"
                  lineHeight="21px"
                >
                  Create New Card
                </Button>
              </Link>
              {/* Icons from Depth 5, Frame 1 & 2 (optional for now) */}
            </HStack>
          </HStack>
        </Flex>

        {/* Main content area (Depth 2, Frame 1 from CSS) - This will hold sidebar and card list */}
        {/* This Flex container will be styled further in Layout.tsx or here for the two-column split */}
        <Flex
          direction={{ base: 'column', md: 'row' }}
          // padding: 20px 24px; gap: 4px; (from CSS)
          px={{ base: '10px', md: '24px' }}
          py="20px"
          gap="16px" // Adjusted gap for modern look
          flex="1" // Take remaining height
        >
          {/* Sidebar will be rendered by Layout.tsx and occupy left space */}
          {/* Card listing area will occupy the right space */}
          <Box
            flex="1" /* This Box will contain the search results or card grid */
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
                {isLoadingCards /* Adjusted padding/margin for new layout */ && (
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
                      /* Changed from gray.50 */ my={4}
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
    </Flex>
  );
}
