'use client';

import { useEffect } from 'react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import {
  Box,
  Heading,
  Text,
  Button,
  SimpleGrid,
  Card,
  CardHeader,
  CardBody,
  Spinner,
  Flex,
  Center,
  VStack,
  Spacer,
  Link as ChakraLink,
  Alert,
  AlertIcon,
} from '@chakra-ui/react';
import CardListItem from '@/components/cards/CardListItem';
import { useCardStore } from '@/stores/cardStore';

export default function Home() {
  const { data: session, status } = useSession();
  const { cards, isLoading: isLoadingCards, error, fetchCards } = useCardStore();

  useEffect(() => {
    if (status === 'authenticated') {
      fetchCards();
    }
  }, [status, fetchCards]);

  // Loading state for session
  if (status === 'loading') {
    return (
      <Flex justify="center" align="center" height="80vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  // Unauthenticated state
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

  // Authenticated state
  return (
    <Box p={5}>
      <Flex mb={6} alignItems="center">
        <Heading as="h2" size="lg">Your Knowledge Cards</Heading>
        <Spacer />
        <Link href="/cards/new">
          <Button colorScheme="green">
            Create New Card
          </Button>
        </Link>
      </Flex>
      {isLoadingCards && (
        <Center p={10}>
          <Spinner size="lg" />
        </Center>
      )}
      {error && (
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          {error}
        </Alert>
      )}
      {!isLoadingCards && !error && cards.length === 0 && (
        <Center p={10} borderWidth="1px" borderRadius="md" bg="gray.50">
          <Text>You haven't created any knowledge cards yet. Get started by creating one!</Text>
        </Center>
      )}
      {!isLoadingCards && !error && cards.length > 0 && (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
          {cards.map((card) => (
            <CardListItem key={card.id} card={card} mutate={fetchCards} />
          ))}
        </SimpleGrid>
      )}
    </Box>
  );
} 