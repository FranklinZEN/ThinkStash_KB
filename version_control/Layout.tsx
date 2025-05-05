'use client';

import React, {
  useState,
  useRef // Add useRef
} from 'react';
import { Box, Flex, Button, Text, HStack, Spacer, Spinner, Link as ChakraLink, useToast, useDisclosure, AlertDialog, AlertDialogBody, AlertDialogFooter, AlertDialogHeader, AlertDialogContent, AlertDialogOverlay } from '@chakra-ui/react';
import { useSession, signOut } from 'next-auth/react';
import Link from 'next/link';
import FoldersSidebar from '@/components/FoldersSidebar'; // Import the sidebar
import { DndContext, DragEndEvent, closestCenter } from '@dnd-kit/core';
import { useCardStore, CardListItem } from '@/stores/cardStore'; // Import card store and type
import { useFolderStore } from '@/stores/folderStore'; // Import folder store

interface LayoutProps {
  children: React.ReactNode;
}

// Type for storing move details
interface MoveDetails {
  cardId: string;
  cardTitle: string;
  targetFolderId: string | null;
  targetFolderName: string | null;
  currentFolderId: string | null;
  currentFolderName: string | null;
}

export default function Layout({ children }: LayoutProps) {
  const { data: session, status } = useSession();
  const toast = useToast(); // Initialize toast
  const fetchCards = useCardStore((state) => state.fetchCards); // Get fetchCards action
  const folders = useFolderStore((state) => state.folders); // Get folders from store
  const fetchFolders = useFolderStore((state) => state.fetchFolders); // Get fetchFolders action

  // State for move confirmation dialog
  const [moveDetails, setMoveDetails] = useState<MoveDetails | null>(null);
  const { isOpen: isMoveConfirmOpen, onOpen: onMoveConfirmOpen, onClose: onMoveConfirmClose } = useDisclosure();
  const cancelRef = useRef<HTMLButtonElement>(null); // Ref for AlertDialog

  const handleSignOut = () => {
    signOut({ callbackUrl: '/' });
  };

  const headerHeight = '64px'; // Define header height for consistent use

  // --- DND Handler ---
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;

    // Check if a draggable item ('active') was dropped over a droppable area ('over')
    if (over && active.id !== over.id) {
      // Verify we are dragging a card onto a folder
      const isCard = active.data.current?.type === 'card';
      const isFolder = over.data.current?.type === 'folder';

      if (isCard && isFolder) {
        const cardId = active.id as string;
        const targetFolderId = over.id as string;
        const draggedCardData = active.data.current?.cardData as CardListItem | undefined;

        if (!draggedCardData) {
          console.error('Card data not found in drag event');
          return;
        }

        const cardTitle = draggedCardData.title ?? 'this card';
        const currentFolderId = draggedCardData.folder?.id ?? null;
        const currentFolderName = draggedCardData.folder?.name ?? null;
        const targetFolder = folders.find(f => f.id === targetFolderId);
        const targetFolderName = targetFolder?.name ?? null;

        // Only proceed if we're actually moving to a different folder
        if (currentFolderId !== targetFolderId) {
          console.log(`Attempting to move card ${cardId} (${cardTitle}) from ${currentFolderName || 'Root'} to folder ${targetFolderName || 'Unknown'}`);

          // Set details and open confirmation dialog
          setMoveDetails({
            cardId,
            cardTitle,
            targetFolderId,
            targetFolderName,
            currentFolderId,
            currentFolderName,
          });
          onMoveConfirmOpen();
        }
      } else {
        console.log('Invalid drop target:', { 
          isCard, 
          isFolder, 
          activeData: active.data.current, 
          overData: over.data.current 
        });
      }
    } else {
      console.log('Drag ended without a valid drop target or dropped on same item');
    }
  };

  // --- Move Confirmation Handler ---
  const confirmMove = async () => {
    if (!moveDetails) return;

    const { cardId, targetFolderId } = moveDetails;
    onMoveConfirmClose(); // Close dialog

    console.log(`Confirming move of card ${cardId} to folder ${targetFolderId}`);

    try {
      // Call the API to update the card's folderId
      const response = await fetch(`/api/cards/${cardId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folderId: targetFolderId }), // Send the target folder ID
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to move card: ${response.statusText}`);
      }

      // Refetch data using the store actions
      await fetchCards();
      await fetchFolders(); // Ensure folders (and counts) are updated

      toast({
        title: 'Card moved successfully.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

    } catch (err: any) {
      console.error('Move card error:', err);
      toast({
        title: 'Error Moving Card',
        description: err.message || 'Could not move the card.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setMoveDetails(null); // Clear move details regardless of outcome
    }
  };

  // --- Build Dialog Message --- (Helper function)
  const getMoveConfirmationMessage = () => {
    if (!moveDetails) return '';
    const { cardTitle, currentFolderName, targetFolderName } = moveDetails;

    if (currentFolderName && targetFolderName) {
      return `Move card "${cardTitle}" from folder "${currentFolderName}" to folder "${targetFolderName}"?`;
    } else if (!currentFolderName && targetFolderName) {
      return `Move card "${cardTitle}" to folder "${targetFolderName}"?`;
    } else if (currentFolderName && !targetFolderName) {
      // This case (moving to root) is not fully handled by current drop logic
      // but we include the message for future implementation.
      return `Remove card "${cardTitle}" from folder "${currentFolderName}"?`;
    }
    return 'Confirm move?'; // Fallback
  };

  return (
    <DndContext onDragEnd={handleDragEnd} collisionDetection={closestCenter}> {/* Wrap with DndContext */}
      <Flex direction="column" minHeight="100vh">
        {/* Header */}
        <Box 
          as="header" 
          bg="blue.600" 
          color="white" 
          px={4} 
          boxShadow="sm"
          height={headerHeight} // Set fixed height
          display="flex" // Use flex for vertical alignment
          alignItems="center" // Vertically center header content
          position="fixed" // Make header sticky
          width="100%" 
          zIndex="sticky" // Ensure header stays on top
        >
          <Flex alignItems="center" width="100%">
            <Link href="/" passHref>
              <ChakraLink as="span" _hover={{ textDecoration: 'none' }} fontWeight="bold">
                Knowledge Cards
              </ChakraLink>
            </Link>
            <Spacer />
            <HStack spacing={4}>
              {status === 'loading' && (
                <Spinner size="sm" />
              )}
              {status === 'unauthenticated' && (
                <>
                  <Link href="/auth/signin">
                    <Button variant="outline" colorScheme="whiteAlpha" size="sm">
                      Sign In
                    </Button>
                  </Link>
                  <Link href="/auth/signup">
                    <Button colorScheme="teal" size="sm">
                      Sign Up
                    </Button>
                  </Link>
                </>
              )}
              {status === 'authenticated' && session?.user && (
                <>
                  <Link href="/profile">
                     <Text cursor="pointer" _hover={{ textDecoration: 'underline' }}>
                        Welcome, {session.user.name || session.user.email}
                     </Text>
                  </Link>
                  <Button colorScheme="red" onClick={handleSignOut} size="sm">
                    Sign Out
                  </Button>
                </>
              )}
            </HStack>
          </Flex>
        </Box>
        {/* Main Content Area with Sidebar */}
        <Flex flex="1" pt={headerHeight}> {/* Add padding top equal to header height */}
          {/* Conditionally render sidebar only when authenticated */}
          {status === 'authenticated' && <FoldersSidebar />}

          {/* Main content takes remaining space */}
          <Box 
            as="main" 
            flex="1" 
            p={6} 
            overflowY="auto" // Allow main content to scroll independently
          >
            {children}
          </Box>
        </Flex>
        {/* Footer is removed as sidebar takes full height */}
        {/* 
        <Box as="footer" bg="gray.100" p={4} mt="auto" textAlign="center">
          © {new Date().getFullYear()} Knowledge Cards App
        </Box>
        */}
      </Flex>

      {/* Move Confirmation Dialog */}
      {moveDetails && (
        <AlertDialog
          isOpen={isMoveConfirmOpen}
          leastDestructiveRef={cancelRef}
          onClose={onMoveConfirmClose}
          isCentered
        >
          <AlertDialogOverlay>
            <AlertDialogContent>
              <AlertDialogHeader fontSize="lg" fontWeight="bold">
                Confirm Move
              </AlertDialogHeader>

              <AlertDialogBody>
                {getMoveConfirmationMessage()} 
              </AlertDialogBody>

              <AlertDialogFooter>
                <Button ref={cancelRef} onClick={onMoveConfirmClose}>
                  Cancel
                </Button>
                <Button colorScheme="blue" onClick={confirmMove} ml={3}>
                  Confirm
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialogOverlay>
        </AlertDialog>
      )}
    </DndContext>
  );
} 