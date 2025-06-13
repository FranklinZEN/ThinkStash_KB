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
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
} from '@chakra-ui/react';
import {
  BlockNoteEditor as BlockNoteEditorType,
  PartialBlock,
} from '@blocknote/core';
import { type AppPartialBlock } from '@/lib/blocknote/appSchema';
import { useStagingCardStore } from '@/stores/stagingCardStore';
import {
  mapPartialBlocksToAIServiceContentBlocks,
  mapContentBlocksToPartialBlocks,
} from '@/lib/contentUtils';

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
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  const toast = useToast();

  const {
    stagedTaskId,
    clearData: clearStagingData,
    isLoading: isStagingLoading,
  } = useStagingCardStore();

  const [title, setTitle] = useState('');
  const [_editor, setEditor] = useState<BlockNoteEditorType | null>(null);
  const [editorContent, setEditorContent] = useState<
    AppPartialBlock[] | undefined
  >(undefined);
  const [editorKey, setEditorKey] = useState(Date.now());

  // New state for file upload
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isFileUploading, setIsFileUploading] = useState(false);

  // Keyword states
  const [keywords, setKeywords] = useState<string[]>([]);
  const [isGeneratingKeywords, setIsGeneratingKeywords] = useState(false);
  const [keywordError, setKeywordError] = useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);

  // --- Task-based Polling State (from Stable Build) ---
  const [pollingTaskId, setPollingTaskId] = useState<string | null>(null);
  const [pollingTaskType, setPollingTaskType] = useState<
    'rewrite' | 'title' | 'keywords' | 'reconstruct' | null
  >(null);
  const [pollingAttempts, setPollingAttempts] = useState(0);
  const [currentProgressMessage, setCurrentProgressMessage] =
    useState<string | null>(null);

  // This useEffect handles the polling logic for a task ID passed via the staging store.
  useEffect(() => {
    if (stagedTaskId) {
      setPollingTaskId(stagedTaskId);
      setPollingTaskType('reconstruct');
      // Important: Clear the taskId from the store so this effect doesn't re-run
      // with the same ID on component re-renders.
      clearStagingData();
    }
  }, [stagedTaskId, clearStagingData]);
  
  const POLLING_INTERVAL_MS = 3000; // 3 seconds
  const MAX_POLLING_ATTEMPTS = 60; // 60 attempts * 3 seconds = 3 minutes timeout

  // Main polling useEffect from Stable Build
  useEffect(() => {
    if (!pollingTaskId || !pollingTaskType) {
      return;
    }

    const intervalId = setInterval(async () => {
      setPollingAttempts((prev) => prev + 1);

      if (pollingAttempts >= MAX_POLLING_ATTEMPTS) {
        clearInterval(intervalId);
        const errorMsg = `Polling timed out for ${pollingTaskType} task.`;
        toast({
          title: 'Task Timeout',
          description: errorMsg,
          status: 'error',
        });
        setPollingTaskId(null);
        setPollingTaskType(null);
        setPollingAttempts(0);
        setCurrentProgressMessage(null);
        return;
      }

      try {
        const res = await fetch(`/api/tasks/${pollingTaskId}/status`);
        const taskData = await res.json();

        if (res.status === 404) {
           if (pollingAttempts > 5) {
                clearInterval(intervalId);
                toast({ title: 'Error', description: 'Task not found.', status: 'error' });
                setPollingTaskId(null);
           }
           return;
        }

        if (!res.ok) {
            clearInterval(intervalId);
            toast({ title: 'Error', description: `Error fetching task status: ${taskData.error}`, status: 'error' });
            setPollingTaskId(null);
            return;
        }
        
        setCurrentProgressMessage(taskData.progressMessage || null);

        if (taskData.status === 'COMPLETED') {
          clearInterval(intervalId);
          toast({
            title: 'Task Successful',
            description: `${pollingTaskType} task completed.`,
            status: 'success',
          });
          
          const resultData = taskData.result;
          
          if (pollingTaskType === 'reconstruct' && resultData?.card_id) {
            router.push(`/cards/${resultData.card_id}`);
          }
          
          setPollingTaskId(null);
          setPollingTaskType(null);
          setPollingAttempts(0);
          setCurrentProgressMessage(null);
          return;
        }

        if (taskData.status === 'FAILED') {
          clearInterval(intervalId);
          const userMessage = taskData.error?.userMessage || `The ${pollingTaskType} task failed. Please try again.`;
          toast({
            title: 'Task Failed',
            description: userMessage,
            status: 'error',
            duration: 9000,
            isClosable: true,
          });
          setPollingTaskId(null);
          setPollingTaskType(null);
          setPollingAttempts(0);
          setCurrentProgressMessage(null);
          return;
        }

      } catch (error) {
        clearInterval(intervalId);
        console.error("Polling error:", error);
        toast({ title: 'Error', description: 'An unexpected error occurred while polling for task status.', status: 'error' });
        setPollingTaskId(null);
      }
    }, POLLING_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [pollingTaskId, pollingTaskType, pollingAttempts, toast, router]);

  const handleUrlSubmit = async (event: FormEvent) => {
    event.preventDefault();
    // ... same as before
  };
  
  // ... other handler functions
  
  // RETURN JSX
}
