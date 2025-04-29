'use client';

import React, { useState, useRef, KeyboardEvent } from 'react';
import {
  Box,
  HStack,
  IconButton,
  Text,
  Spacer,
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
  Badge,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
  useColorModeValue,
} from '@chakra-ui/react';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  EditIcon,
  DeleteIcon,
  HamburgerIcon,
  AddIcon,
  DragHandleIcon
} from '@chakra-ui/icons';
import { FolderTreeNode as FolderTreeNodeType } from '@/lib/folderUtils';
import RenameFolderModal from './RenameFolderModal';
import { useFolderStore } from '@/stores/folderStore';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import CreateFolderModal from './CreateFolderModal';
import { motion } from 'framer-motion';

interface FolderTreeNodeProps {
  node: FolderTreeNodeType;
  level: number;
  isSelected?: boolean;
  onSelect?: (folderId: string) => void;
  isDragging?: boolean;
  isOver?: boolean;
  dropDirection?: 'above' | 'below' | null;
}

export default function FolderTreeNode({ 
  node, 
  level, 
  isSelected = false, 
  onSelect, 
  isDragging = false,
  isOver = false,
  dropDirection = null
}: FolderTreeNodeProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { isOpen: isRenameOpen, onOpen: onRenameOpen, onClose: onRenameClose } = useDisclosure();
  const { isOpen: isDeleteAlertOpen, onOpen: onDeleteAlertOpen, onClose: onDeleteAlertClose } = useDisclosure();
  const [isDeleting, setIsDeleting] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const toast = useToast();
  const deleteFolder = useFolderStore((state) => state.deleteFolder);
  const hasChildren = node.children && node.children.length > 0;
  const { isOpen: isCreateOpen, onOpen: onCreateOpen, onClose: onCreateClose } = useDisclosure();

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging: isSortableDragging
  } = useSortable({ id: node.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isSortableDragging ? 0.5 : 1,
  };

  const dropIndicatorColor = useColorModeValue('blue.200', 'blue.700');
  const hoverBg = useColorModeValue('gray.100', 'gray.700');
  const selectedBg = useColorModeValue('blue.50', 'blue.900');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  const handleClick = (e: React.MouseEvent) => {
    if (!(e.target instanceof SVGElement) && !(e.target instanceof HTMLButtonElement) && !(e.target as HTMLElement).closest('button')) {
      if (onSelect) {
        onSelect(node.id);
      }
      setIsOpen(!isOpen);
    }
  };

  const handleRenameClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onRenameOpen();
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDeleteAlertOpen();
  };

  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    const success = await deleteFolder(node.id);
    setIsDeleting(false);
    onDeleteAlertClose();

    if (success) {
      toast({ title: 'Folder deleted.', status: 'success', duration: 3000 });
    } else {
      const storeError = useFolderStore.getState().error;
      const notEmptyMessage = 'Folder is not empty';
      const errorMessage = storeError?.includes(notEmptyMessage)
                             ? 'Cannot delete a folder that contains cards or sub-folders.'
                             : (storeError || 'Failed to delete folder.');
      toast({ title: 'Error Deleting Folder', description: errorMessage, status: 'error', duration: 5000 });
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    switch (e.key) {
      case 'Enter':
      case ' ':
        e.preventDefault();
        setIsOpen(!isOpen);
        break;
      case 'ArrowRight':
        if (!isOpen && hasChildren) {
          e.preventDefault();
          setIsOpen(true);
        }
        break;
      case 'ArrowLeft':
        if (isOpen) {
          e.preventDefault();
          setIsOpen(false);
        }
        break;
    }
  };

  return (
    <Box 
      ref={setNodeRef}
      style={style}
      mx={1} 
      my="1px"
      role="treeitem"
      aria-expanded={hasChildren ? isOpen : undefined}
      aria-level={level + 1}
      aria-selected={isSelected}
    >
      {/* Drop Indicator Above */}
      {isOver && dropDirection === 'above' && (
        <Box
          h="2px"
          bg={dropIndicatorColor}
          borderRadius="full"
          mx={2}
          mb={1}
          transition="all 0.2s"
        />
      )}

      <HStack
        pl={level * 4}
        py={1}
        pr={2}
        _hover={{ bg: hoverBg }}
        bg={isSelected ? selectedBg : undefined}
        cursor="pointer"
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        spacing={1}
        w="100%"
        borderRadius="md"
        transition="all 0.2s"
        position="relative"
        border={isOver ? `1px dashed ${borderColor}` : undefined}
      >
        {/* Drag Handle */}
        <Box
          {...attributes}
          {...listeners}
          cursor="grab"
          p={1}
          _hover={{ bg: 'gray.200' }}
          borderRadius="md"
          transition="all 0.2s"
        >
          <DragHandleIcon boxSize={3} color="gray.500" />
        </Box>

        {/* Expand/Collapse Icon */}
        <IconButton
          aria-label={isOpen ? 'Collapse folder' : 'Expand folder'}
          icon={hasChildren ? (isOpen ? <ChevronDownIcon /> : <ChevronRightIcon />) : <Box w="14px" />}
          size="xs"
          variant="ghost"
          isRound
          isDisabled={!hasChildren}
          onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
          mr={1}
          flexShrink={0}
        />

        {/* Flex container for Name and Count */}
        <Flex flex={1} align="center" overflow="hidden" mr={1}>
          <Text 
            fontSize="sm" 
            noOfLines={1} 
            title={node.name}
            fontWeight={level === 0 ? "medium" : "normal"}
            color={isSelected ? "blue.600" : undefined}
          >
            {node.name}
          </Text>
        </Flex>

        {/* Display Card Count */}
        {typeof node._count?.cards === 'number' && (
          <Badge
            fontSize="0.7em"
            colorScheme={isSelected ? "blue" : "gray"}
            variant="subtle"
            flexShrink={0}
            px={1.5}
            borderRadius="sm"
          >
            {node._count.cards}
          </Badge>
        )}

        {/* Context Menu */}
        <Menu>
          <MenuButton
            as={IconButton}
            aria-label="Folder actions"
            icon={<HamburgerIcon />}
            size="xs"
            variant="ghost"
            onClick={(e) => e.stopPropagation()}
          />
          <MenuList onClick={(e) => e.stopPropagation()}>
            <MenuItem icon={<AddIcon />} onClick={(e) => { e.stopPropagation(); onCreateOpen(); }}>
              Create Subfolder
            </MenuItem>
            <MenuItem icon={<EditIcon />} onClick={(e) => { e.stopPropagation(); onRenameOpen(); }}>
              Rename
            </MenuItem>
            <MenuDivider />
            <MenuItem icon={<DeleteIcon />} onClick={(e) => { e.stopPropagation(); onDeleteAlertOpen(); }} color="red.500">
              Delete
            </MenuItem>
          </MenuList>
        </Menu>
      </HStack>

      {/* Drop Indicator Below */}
      {isOver && dropDirection === 'below' && (
        <Box
          h="2px"
          bg={dropIndicatorColor}
          borderRadius="full"
          mx={2}
          mt={1}
          transition="all 0.2s"
        />
      )}

      {/* Render Children */}
      {hasChildren && isOpen && (
        <Box>
          <AnimatePresence>
            {node.children.map((childNode) => (
              <motion.div
                key={childNode.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
              >
                <FolderTreeNode
                  key={childNode.id}
                  node={childNode}
                  level={level + 1}
                  isSelected={childNode.id === selectedFolderId}
                  onSelect={onSelect}
                  isDragging={isDragging}
                  isOver={isOver}
                  dropDirection={dropDirection}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        </Box>
      )}

      {/* Rename Modal Instance */}
      <RenameFolderModal
        isOpen={isRenameOpen}
        onClose={onRenameClose}
        folderId={node.id}
        currentName={node.name}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        isOpen={isDeleteAlertOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteAlertClose}
        isCentered
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete Folder
            </AlertDialogHeader>
            <AlertDialogBody>
              Are you sure you want to delete the folder "{node.name}"?
              Cards within this folder will become uncategorized.
              Sub-folders within this folder will be moved to the parent folder (or root if this folder is at the root).
              This action cannot be undone.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteAlertClose} isDisabled={isDeleting}>
                Cancel
              </Button>
              <Button colorScheme="red" onClick={handleConfirmDelete} ml={3} isLoading={isDeleting}>
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      <CreateFolderModal
        isOpen={isCreateOpen}
        onClose={onCreateClose}
        parentId={node.id}
      />
    </Box>
  );
} 