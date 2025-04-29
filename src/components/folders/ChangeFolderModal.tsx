'use client';

import React, { useState } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  VStack,
  Text,
  useToast,
  Input,
  HStack,
  FormControl,
  FormLabel,
} from '@chakra-ui/react';
import { useFolderStore } from '@/stores/folderStore';

interface ChangeFolderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirmMove: (folderId: string | null) => Promise<void>;
  currentFolderId?: string | null;
  isLoading?: boolean;
}

export default function ChangeFolderModal({
  isOpen,
  onClose,
  onConfirmMove,
  currentFolderId,
  isLoading = false,
}: ChangeFolderModalProps) {
  const { folders, addFolder } = useFolderStore();
  const toast = useToast();
  const [newFolderName, setNewFolderName] = useState('');
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);

  const handleMove = async (folderId: string | null) => {
    if (folderId === currentFolderId) {
        toast({
            title: "Card is already in this folder",
            status: "info",
            duration: 2000,
            isClosable: true,
        });
        return;
    }
    try {
      await onConfirmMove(folderId);
      onClose();
    } catch (error) {
      toast({
        title: 'Error moving card',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      toast({ title: "Folder name cannot be empty", status: "warning", duration: 2000 });
      return;
    }
    setIsCreatingFolder(true);
    const success = await addFolder(newFolderName.trim(), null);

    if (success) {
        toast({ title: `Folder "${newFolderName.trim()}" created`, status: "success", duration: 2000 });
        setNewFolderName('');
    } else {
        const storeError = useFolderStore.getState().error;
        toast({
            title: 'Error Creating Folder',
            description: storeError || 'Failed to create folder. See console for details.',
            status: 'error',
            duration: 5000,
        });
    }
    setIsCreatingFolder(false);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Move Card to Folder</ModalHeader>
        <ModalBody>
          <VStack spacing={4} align="stretch">
            <Button
              variant="ghost"
              onClick={() => handleMove(null)}
              isLoading={isLoading}
              isDisabled={isLoading || currentFolderId === null}
            >
              Root (No Folder)
            </Button>
            {folders.map((folder) => (
              <Button
                key={folder.id}
                variant="ghost"
                onClick={() => handleMove(folder.id)}
                isLoading={isLoading}
                isDisabled={isLoading || folder.id === currentFolderId}
              >
                {folder.name}
              </Button>
            ))}

            <FormControl mt={6}>
              <FormLabel fontSize="sm">Create New Folder</FormLabel>
              <HStack>
                <Input
                  placeholder="New folder name"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  isDisabled={isLoading || isCreatingFolder}
                />
                <Button
                  onClick={handleCreateFolder}
                  isLoading={isCreatingFolder}
                  isDisabled={isLoading}
                  colorScheme="blue"
                >
                  Create
                </Button>
              </HStack>
            </FormControl>
          </VStack>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" onClick={onClose} isDisabled={isCreatingFolder}>
            Cancel
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
} 