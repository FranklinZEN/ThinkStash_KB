'use client';

import React, { useState, FormEvent, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
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
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Progress,
} from '@chakra-ui/react';

interface Task {
  id: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress: number;
  progressMessage: string | null;
  result: { cardId: string } | null;
  error: { userMessage: string } | null;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function NewCardFromUrlPage() {
  const { status, data: session } = useSession();
  const router = useRouter();
  const toast = useToast();

  const [sourceUrl, setSourceUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);

  const { data: task, error: swrError } = useSWR<Task>(
    taskId ? `/api/tasks/${taskId}/status` : null,
    fetcher,
    {
      refreshInterval: (latestData) => {
        // Stop polling if the task is completed or failed
        if (latestData?.status === 'COMPLETED' || latestData?.status === 'FAILED') {
          return 0;
        }
        return 2000; // Poll every 2 seconds
      },
      onSuccess: (data) => {
        if (data.status === 'COMPLETED') {
          toast({
            title: 'Processing complete!',
            description: 'Redirecting to the new card...',
            status: 'success',
            duration: 3000,
            isClosable: true,
          });
          if (data.result?.cardId) {
            router.push(`/cards/${data.result.cardId}`);
          }
        }
      },
    }
  );

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!sourceUrl.trim()) {
      toast({
        title: 'Source URL is required',
        status: 'warning',
        duration: 3000,
      });
      return;
    }
    setIsSubmitting(true);
    setTaskId(null);

    try {
      const response = await fetch('/api/ai/reconstruct-and-analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sourceUrl }),
      });

      if (response.status === 202) {
        const { taskId } = await response.json();
        setTaskId(taskId);
        toast({
          title: 'Task submitted.',
          description: 'The AI is starting its work. You can see progress below.',
          status: 'info',
          duration: 5000,
          isClosable: true,
        });
      } else {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to start task.');
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'An unexpected error occurred.';
      toast({
        title: 'Error submitting task.',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/api/auth/signin?callbackUrl=/cards/new');
    }
  }, [status, router]);
  
  if (status === 'loading') {
    return (
      <Flex justify="center" align="center" height="80vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  const renderStatusBox = () => {
    if (!taskId) return null;

    if (swrError) {
      return (
        <Alert status="error">
          <AlertIcon />
          <AlertTitle>Could not fetch task status!</AlertTitle>
          <AlertDescription>Please try submitting the URL again.</AlertDescription>
        </Alert>
      );
    }

    if (!task) {
      return (
        <Box>
            <Text mb={2}>Waiting for task to start...</Text>
            <Spinner />
        </Box>
      );
    }

    if (task.status === 'FAILED') {
        return (
            <Alert status="error">
              <AlertIcon />
              <AlertTitle>Task Failed!</AlertTitle>
              <AlertDescription>{task.error?.userMessage || 'An unknown error occurred.'}</AlertDescription>
            </Alert>
          );
    }

    return (
        <Box p={5} borderWidth="1px" borderRadius="md" boxShadow="sm">
            <Heading size="md" mb={3}>Processing Status</Heading>
            <Text fontSize="lg" mb={4}>{task.progressMessage || '...'}</Text>
            <Progress value={task.progress} hasStripe isAnimated={task.status === 'PROCESSING'} />
        </Box>
    );
  }

  return (
    <Container maxW="container.lg" py={8}>
      <Heading as="h1" size="xl" mb={6}>
        Create New Card from URL
      </Heading>
      <Box as="form" onSubmit={handleSubmit}>
        <VStack spacing={6} align="stretch">
          <FormControl isRequired>
            <FormLabel>Source URL</FormLabel>
            <Input
              type="url"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://example.com/article"
              isDisabled={isSubmitting || !!taskId}
            />
          </FormControl>
          <Button
            type="submit"
            colorScheme="blue"
            isLoading={isSubmitting}
            isDisabled={!!taskId && task?.status !== 'FAILED'}
          >
            Create Card
          </Button>
        </VStack>
      </Box>

      {taskId && (
         <Box mt={8}>
            {renderStatusBox()}
         </Box>
      )}

    </Container>
  );
}
