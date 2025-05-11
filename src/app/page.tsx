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
  Spacer,
  Alert,
  AlertIcon,
  HStack,
} from '@chakra-ui/react';
import CardListItem from '@/components/cards/CardListItem';
import { useCardStore } from '@/stores/cardStore';
import SearchInput from '@/components/search/SearchInput';
import SearchResults from '@/components/search/SearchResults';
import { fetchWithAuth } from '@/lib/fetchWithAuth';
import {
  KnowledgeCard as PrismaKnowledgeCard,
  Folder as PrismaFolder,
} from '@prisma/client';
import type { BlockNoteDocument } from '@/types/blocknote';

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
      <Flex justify="center" align="center" height="80vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
    return (
      <Center height="80vh">
        <VStack spacing={4}>
          <Heading>Welcome to Knowledge Cards!</Heading>
          <Text>Your dynamic personal knowledge base.</Text>
          <Text>Please sign in or sign up to manage your cards.</Text>
          <Flex gap={4} mt={4}>
            <Link href="/api/auth/signin">
              <Button colorScheme="blue">Sign In</Button>
            </Link>
            <Link href="/auth/signup">
              <Button colorScheme="teal">Sign Up</Button>
            </Link>
          </Flex>
        </VStack>
      </Center>
    );
  }

  return (
    <Box p={5}>
      <Flex mb={6} alignItems="center" wrap="wrap" gap={4}>
        <Heading as="h2" size="lg">
          Your Knowledge Cards
        </Heading>
        <Spacer />
        <SearchInput onSearchSubmit={performSearch} />
        <Link href="/cards/new">
          <Button colorScheme="green">Create New Card</Button>
        </Link>
      </Flex>

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
            <Center p={10}>
              <Spinner size="lg" />
            </Center>
          )}
          {cardError && (
            <Alert status="error" borderRadius="md">
              <AlertIcon />
              {cardError}
            </Alert>
          )}
          {!isLoadingCards &&
            !cardError &&
            cards.length === 0 &&
            pagination &&
            pagination.totalItems === 0 && (
              <Center p={10} borderWidth="1px" borderRadius="md" bg="gray.50">
                <Text>
                  You haven&apos;t created any knowledge cards yet. Get started
                  by creating one!
                </Text>
              </Center>
            )}
          {!isLoadingCards && !cardError && cards.length > 0 && (
            <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
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
                >
                  Previous
                </Button>
                <Text>
                  Page {pagination.page} of {pagination.totalPages}
                </Text>
                <Button
                  onClick={handleNextPage}
                  isDisabled={
                    pagination.page >= pagination.totalPages || isLoadingCards
                  }
                >
                  Next
                </Button>
              </HStack>
            </Flex>
          )}
        </>
      )}
    </Box>
  );
}
