'use client';

import React from 'react';
import {
  Box,
  VStack,
  Heading,
  IconButton,
  Flex,
  Spacer,
  useDisclosure,
} from '@chakra-ui/react';
import { AddIcon } from '@chakra-ui/icons';
import FolderTree from '@/components/folders/FolderTree';
import CreateFolderModal from './folders/CreateFolderModal';

export default function FoldersSidebar() {
  // Modal state hook
  const { isOpen: isCreateOpen, onOpen: onCreateOpen, onClose: onCreateClose } = useDisclosure();

  const handleAddFolderClick = () => {
    onCreateOpen(); // Open the modal for creating a root folder
  };

  const headerHeight = '64px'; // Assuming this is the header height from Layout.tsx

  return (
    <Box
      as="aside"
      width="250px" // Keep the desired width
      bg="gray.50"
      p={4}
      borderRight="1px"
      borderColor="gray.200"
      // Calculate height to fill space below header, considering padding
      height={`calc(100vh - ${headerHeight})`}
      overflowY="auto" // Allow sidebar content to scroll if needed
    >
      <VStack align="stretch" spacing={4}>
        <Flex mb={0} align="center"> {/* Reduced margin bottom */}
          <Heading size="md">Folders</Heading>
          <Spacer />
          <IconButton
            aria-label="Add Folder"
            icon={<AddIcon />}
            size="sm"
            onClick={handleAddFolderClick}
            // isDisabled={isProcessing} // Disable based on state from store later
          />
        </Flex>

        {/* Render the FolderTree component */}
        <Box flex="1"> {/* Allow FolderTree to take available space */}
          <FolderTree />
        </Box>
      </VStack>

      {/* Render the Create Folder Modal */}
      <CreateFolderModal
        isOpen={isCreateOpen}
        onClose={onCreateClose}
        parentId={null} // Explicitly pass null for root folder creation
      />
    </Box>
  );
} 