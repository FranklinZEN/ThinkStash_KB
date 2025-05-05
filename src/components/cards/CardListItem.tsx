'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Text,
  Badge,
  HStack,
  IconButton,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
  useDisclosure,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  Button,
  useToast,
  Flex,
  VStack,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  ModalFooter,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverArrow,
  PopoverCloseButton,
  PopoverHeader,
  PopoverBody,
} from '@chakra-ui/react';
import { EditIcon, DeleteIcon, ChevronRightIcon, ChevronLeftIcon, HamburgerIcon, RepeatIcon, StarIcon } from '@chakra-ui/icons';
import { useRouter } from 'next/navigation';
import { Card } from '@prisma/client';
import { extractSnippetFromContent, type Block } from '@/lib/cardUtils';
import ChangeFolderModal from '../folders/ChangeFolderModal';
import { useFolders } from '@/hooks/useFolders';
import '@/styles/cardStyles.css';

interface CardListItemProps {
  card: Card & {
    folder?: { id: string; name: string } | null;
    tags: { name: string }[];
    isStarred: boolean;
  };
  mutate?: () => void;
}

export default function CardListItem({ card, mutate }: CardListItemProps) {
  const router = useRouter();
  const toast = useToast();
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isMoveModalOpen, setIsMoveModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isStarred, setIsStarred] = useState(card.isStarred);
  const [isStarLoading, setIsStarLoading] = useState(false);
  const deleteCancelRef = useRef<HTMLButtonElement>(null);
  const [formattedDate, setFormattedDate] = useState<string | null>(null);

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    router.push(`/cards/${card.id}`);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsDeleteModalOpen(true);
  };

  const handleMove = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsMoveModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/cards/${card.id}`, { method: 'DELETE' });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to delete card');
      }
      toast({
        title: 'Card deleted',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      mutate?.();
    } catch (error) {
      toast({
        title: 'Error deleting card',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
      setIsDeleteModalOpen(false);
    }
  };

  const handleConfirmMove = async (targetFolderId: string | null) => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/cards/${card.id}/move`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folderId: targetFolderId }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to move card');
      }
      toast({
        title: 'Card moved',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      mutate?.();
    } catch (error) {
      toast({
        title: 'Error moving card',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
      setIsMoveModalOpen(false);
    }
  };

  const handleToggleStar = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsStarLoading(true);
    try {
      const response = await fetch(`/api/cards/${card.id}/star`, { method: 'PUT' });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to update star status');
      }
      const updatedCard = await response.json();
      setIsStarred(updatedCard.isStarred);
      toast({
        title: `Card ${updatedCard.isStarred ? 'starred' : 'unstarred'}`,
        status: 'success',
        duration: 2000,
        isClosable: true,
      });
      mutate?.();
    } catch (error) {
      toast({
        title: 'Error updating star status',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsStarLoading(false);
    }
  };

  // Effect to format date client-side
  useEffect(() => {
    const displayTimestamp = Math.max(
      new Date(card.updatedAt).getTime() || 0,
      new Date(card.createdAt).getTime() || 0
    );

    if (displayTimestamp > 0) {
      const displayDate = new Date(displayTimestamp);
      setFormattedDate(`${displayDate.toLocaleDateString()} ${displayDate.toLocaleTimeString()}`);
    } else {
      setFormattedDate('No date');
    }
    // Re-run if card dates change
  }, [card.updatedAt, card.createdAt]);

  // Parse content if it's a JSON string, otherwise assume it's already parsed
  let parsedContent: Block[] | null = null;
  try {
    if (typeof card.content === 'string') {
      parsedContent = JSON.parse(card.content);
    } else if (Array.isArray(card.content)) {
      // Assume it's already the correct array structure if not a string
      // Add more robust type checking if needed
      parsedContent = card.content as Block[]; // Still needs a cast potentially
    }
  } catch (error) {
    // Handle cases where content might be invalid JSON or unexpected type
    parsedContent = null;
  }

  // Pass the parsed content (or null if parsing failed/invalid) to the snippet function
  const snippet = extractSnippetFromContent(parsedContent);

  return (
    <Box position="relative" className="card">
      <Menu placement="bottom-end" isLazy>
        <Popover trigger="hover" placement="bottom" openDelay={300} closeDelay={100}>
          <PopoverTrigger>
            <Box
              p={4}
              bg="white"
              borderRadius="md"
              boxShadow="sm"
              position="relative"
              width="100%"
              minHeight="150px"
              display="flex"
              flexDirection="column"
              justifyContent="space-between"
              _hover={{ boxShadow: 'lg', cursor: 'pointer' }}
            >
              <IconButton
                aria-label={isStarred ? 'Unstar card' : 'Star card'}
                icon={<StarIcon color={isStarred ? 'yellow.400' : 'gray.300'} />}
                variant="ghost"
                size="sm"
                position="absolute"
                top="8px"
                right="40px"
                zIndex="20"
                onClick={(e) => {
                  e.stopPropagation();
                  handleToggleStar(e);
                }}
                isLoading={isStarLoading}
              />

              <MenuButton
                as={IconButton}
                aria-label="Card options"
                icon={<HamburgerIcon />}
                variant="ghost"
                size="sm"
                position="absolute"
                top="8px"
                right="8px"
                zIndex="20"
                onClick={(e) => e.stopPropagation()}
              />

              <Box mr="30px">
                <Text fontSize="lg" fontWeight="bold" noOfLines={3}>
                  {card.title}
                </Text>
                {card.folder && (
                  <Text fontSize="sm" color="gray.500" mt={1} noOfLines={1}>
                    {card.folder.name}
                  </Text>
                )}
              </Box>
              <Text fontSize="xs" color="gray.400" mt={2}>
                Last activity: {formattedDate ?? '...'}
              </Text>
            </Box>
          </PopoverTrigger>
          <PopoverContent maxW="400px" zIndex="popover">
            <PopoverArrow />
            <PopoverBody maxH="600px" overflowY="auto">
              <Text whiteSpace="pre-wrap" fontSize="sm">
                {snippet || 'No content preview available.'}
              </Text>
            </PopoverBody>
          </PopoverContent>
        </Popover>

        <MenuList onClick={(e) => e.stopPropagation()}>
          <MenuItem icon={<EditIcon />} onClick={handleEdit}>
            View/Edit
          </MenuItem>
          <MenuItem icon={<RepeatIcon />} onClick={handleMove}>
            Move to Folder
          </MenuItem>
          <MenuDivider />
          <MenuItem icon={<DeleteIcon />} color="red.500" onClick={handleDelete}>
            Delete
          </MenuItem>
        </MenuList>
      </Menu>

      <AlertDialog
        isOpen={isDeleteModalOpen}
        leastDestructiveRef={deleteCancelRef}
        onClose={() => setIsDeleteModalOpen(false)}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete Card
            </AlertDialogHeader>
            <AlertDialogBody>
              Are you sure you want to delete the card "{card.title}"? This action cannot be undone.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={deleteCancelRef} onClick={() => setIsDeleteModalOpen(false)}>
                Cancel
              </Button>
              <Button colorScheme="red" onClick={handleConfirmDelete} ml={3} isLoading={isLoading}>
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      <ChangeFolderModal
        isOpen={isMoveModalOpen}
        onClose={() => setIsMoveModalOpen(false)}
        onConfirmMove={handleConfirmMove}
        currentFolderId={card.folderId}
        isLoading={isLoading}
      />
    </Box>
  );
} 