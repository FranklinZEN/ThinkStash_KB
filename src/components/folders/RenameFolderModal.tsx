'use client';

import React, { useState, useRef, useEffect } from 'react';
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

interface RenameFolderModalProps {
  isOpen: boolean;
  onClose: () => void;
  folderId: string;
  currentName: string;
}

export default function RenameFolderModal({ isOpen, onClose, folderId, currentName }: RenameFolderModalProps) {
  const [newName, setNewName] = useState(currentName);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const initialFocusRef = useRef(null);
  const toast = useToast();
  const renameFolder = useFolderStore((state) => state.renameFolder);

  // Update state if props change (e.g., opening modal for a different folder)
  useEffect(() => {
    if (isOpen) {
      setNewName(currentName);
      setSaveError(null);
      setIsSaving(false);
    }
  }, [isOpen, currentName]);

  const handleRenameFolder = async () => {
    const trimmedName = newName.trim();
    if (!trimmedName) {
      setSaveError('Folder name cannot be empty.');
      return;
    }
    if (trimmedName === currentName) {
      toast({ title: 'No changes detected.', status: 'info', duration: 3000 });
      onClose();
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    const success = await renameFolder(folderId, trimmedName);

    setIsSaving(false);
    if (success) {
      toast({ title: 'Folder renamed.', status: 'success', duration: 3000 });
      onClose(); // Close modal on success
    } else {
      const storeError = useFolderStore.getState().error;
      // Check for specific 409 error message from API/Store
      const conflictMessage = 'A folder with this name already exists at this level.';
      const errorMessage = storeError?.includes(conflictMessage) 
                             ? conflictMessage 
                             : (storeError || 'Failed to rename folder. Please try again.');
      setSaveError(errorMessage);
      toast({ title: 'Error Renaming Folder', description: errorMessage, status: 'error', duration: 5000 });
    }
  };

  // Reset internal state on close
  const handleClose = () => {
     // setNewName(currentName); // Resetting in useEffect instead
     setIsSaving(false);
     setSaveError(null);
     onClose();
   }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} initialFocusRef={initialFocusRef} isCentered>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Rename Folder</ModalHeader>
        <ModalCloseButton isDisabled={isSaving} />
        <ModalBody pb={6}>
          <FormControl isRequired isInvalid={!!saveError}>
            <FormLabel>New Folder Name</FormLabel>
            <Input
              ref={initialFocusRef}
              value={newName}
              onChange={(e) => {
                 setNewName(e.target.value);
                 if (saveError) setSaveError(null);
              }}
              placeholder="Enter new folder name"
              isDisabled={isSaving}
              onKeyDown={(e) => {
                 if (e.key === 'Enter' && !isSaving) {
                   e.preventDefault();
                   handleRenameFolder();
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
          <Button colorScheme="blue" onClick={handleRenameFolder} isLoading={isSaving}>
            Rename
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
} 