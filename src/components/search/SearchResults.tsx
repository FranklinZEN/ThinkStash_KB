import React from 'react';
import {
  Box,
  Text,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  SimpleGrid,
} from '@chakra-ui/react';
import CardListItem from '@/components/cards/CardListItem';
import { KnowledgeCard as PrismaKnowledgeCard, Folder } from '@prisma/client';
import type { AppPartialBlock } from '@/lib/blocknote/appSchema';

// Define SearchResultCard with content as AppPartialBlock[]
export interface SearchResultCard extends Omit<PrismaKnowledgeCard, 'content'> {
  content: AppPartialBlock[] | string | null;
  folder: Pick<Folder, 'id' | 'name'> | null;
  _count?: { cards?: number }; // This seems to be from an old query, might not be used by CardListItem
  headline?: string; // Headline might still be present but not used by CardListItem
}

interface SearchResultsProps {
  results: SearchResultCard[];
  isLoading: boolean;
  error: string | null;
  searchQuery: string;
  mutateResults: () => void;
}

const SearchResults: React.FC<SearchResultsProps> = ({
  results,
  isLoading,
  error,
  searchQuery,
  mutateResults,
}) => {
  if (isLoading) {
    return (
      <Box textAlign="center" p={5}>
        <Spinner size="xl" />
        <Text mt={2}>Searching...</Text>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert status="error" mt={4}>
        <AlertIcon />
        <AlertTitle>Search Error: {error}</AlertTitle>
      </Alert>
    );
  }

  if (results.length === 0 && searchQuery) {
    return (
      <Text mt={4} color="gray.500">
        No results found for &quot;{searchQuery}&quot;.
      </Text>
    );
  }

  if (results.length === 0 && !searchQuery) {
    return null;
  }

  return (
    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6} mt={4}>
      {results.map((card) => (
        <CardListItem key={card.id} card={card} mutate={mutateResults} />
      ))}
    </SimpleGrid>
  );
};

export default SearchResults;
