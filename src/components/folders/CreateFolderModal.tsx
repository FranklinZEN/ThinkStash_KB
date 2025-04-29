'use client';

import React, { useState, useRef } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Input,
  useToast,
  FormErrorMessage,
} from '@chakra-ui/react';
import { useFolderStore } from '@/stores/folderStore';

interface CreateFolderModalProps {
  isOpen: boolean;
  onClose: () => void;
  parentId: string | null; // To know where to create the folder
}

export default function CreateFolderModal({ isOpen, onClose, parentId }: CreateFolderModalProps) {
  const [folderName, setFolderName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const initialFocusRef = useRef(null);
  const toast = useToast();
  const addFolder = useFolderStore((state) => state.addFolder); // Get action from store

  const handleSaveFolder = async () => {
    if (!folderName.trim()) {
      setSaveError('Folder name cannot be empty.');
      return;
    }
    setIsSaving(true);
    setSaveError(null);

    const success = await addFolder(folderName.trim(), parentId);

    setIsSaving(false);
    if (success) {
      toast({ title: 'Folder created.', status: 'success', duration: 3000 });
      setFolderName(''); // Clear input on success
      onClose(); // Close modal on success
    } else {
      // Error handling is basic here, assumes store sets an error or API returns specific message
      // More robust error display could parse specific errors (like 409 conflict)
      const storeError = useFolderStore.getState().error; // Get latest error from store
      setSaveError(storeError || 'Failed to create folder. Please try again.');
      toast({ title: 'Error Creating Folder', description: storeError || 'An unexpected error occurred.', status: 'error', duration: 5000 });
    }
  };

  // Clear state when modal closes
  const handleClose = () => {
    setFolderName('');
    setIsSaving(false);
    setSaveError(null);
    onClose();
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} initialFocusRef={initialFocusRef} isCentered>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{parentId ? 'Create Subfolder' : 'Create New Folder'}</ModalHeader>
        <ModalCloseButton isDisabled={isSaving} />
        <ModalBody pb={6}>
          <FormControl isRequired isInvalid={!!saveError}>
            <FormLabel>Folder Name</FormLabel>
            <Input
              ref={initialFocusRef}
              value={folderName}
              onChange={(e) => {
                setFolderName(e.target.value);
                if (saveError) setSaveError(null); // Clear error on type
              }}
              placeholder="Enter folder name"
              isDisabled={isSaving}
              onKeyDown={(e) => {
                 if (e.key === 'Enter' && !isSaving) {
                    e.preventDefault(); // Prevent form submission if wrapped in form
                    handleSaveFolder();
                 }
              }}
            />
            {saveError && <FormErrorMessage>{saveError}</FormErrorMessage>}
          </FormControl>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={handleClose} isDisabled={isSaving}>
            Cancel
          </Button>
          <Button colorScheme="blue" onClick={handleSaveFolder} isLoading={isSaving}>
            Create
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
} 