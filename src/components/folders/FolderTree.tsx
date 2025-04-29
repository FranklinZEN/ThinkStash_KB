'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Box, Spinner, Text, Alert, AlertIcon, Button, VStack, Input, InputGroup, InputLeftElement, InputRightElement, IconButton, useColorModeValue } from '@chakra-ui/react';
import { buildTree, FolderListItem, FolderTreeNode as FolderTreeNodeType } from '@/lib/folderUtils';
import FolderTreeNode from './FolderTreeNode';
import { useFolderStore } from '@/stores/folderStore'; // Import the store
import { AddIcon, SearchIcon, CloseIcon } from '@chakra-ui/icons';
import CreateFolderModal from './CreateFolderModal';
import { useDisclosure } from '@chakra-ui/react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  DragOverEvent,
  useDndMonitor,
  DragMoveEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { motion, AnimatePresence } from 'framer-motion';

// TODO: Integrate with Zustand store later (KC-ORG-FE-2)

export default function FolderTree() {
  // Get state and actions from the store
  const { folders, isLoading, error, fetchFolders, reorderFolders } = useFolderStore();
  const [treeData, setTreeData] = useState<FolderTreeNodeType[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeId, setActiveId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const [dragDirection, setDragDirection] = useState<'above' | 'below' | null>(null);
  const { isOpen: isCreateOpen, onOpen: onCreateOpen, onClose: onCreateClose } = useDisclosure();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const dropIndicatorColor = useColorModeValue('blue.200', 'blue.700');
  const dragOverlayBg = useColorModeValue('white', 'gray.800');

  // Fetch folders using the store action on mount
  useEffect(() => {
    fetchFolders();
  }, [fetchFolders]);

  // Rebuild tree when folders data changes in the store
  useEffect(() => {
    if (folders) {
        const tree = buildTree(folders);
        setTreeData(tree);
    }
  }, [folders]);

  // Filter tree data based on search query
  const filteredTreeData = useMemo(() => {
    if (!searchQuery) return treeData;

    const filterNode = (node: FolderTreeNodeType): FolderTreeNodeType | null => {
      const matches = node.name.toLowerCase().includes(searchQuery.toLowerCase());
      const filteredChildren = node.children
        .map(child => filterNode(child))
        .filter((child): child is FolderTreeNodeType => child !== null);

      if (matches || filteredChildren.length > 0) {
        return {
          ...node,
          children: filteredChildren
        };
      }
      return null;
    };

    return treeData
      .map(node => filterNode(node))
      .filter((node): node is FolderTreeNodeType => node !== null);
  }, [treeData, searchQuery]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const clearSearch = () => {
    setSearchQuery('');
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeRect = active.rect.current.translated;
    const overRect = over.rect.current.translated;
    const overElement = over.data.current?.element as HTMLElement;

    if (!activeRect || !overRect || !overElement) return;

    const overMiddleY = overRect.top + overRect.height / 2;
    const direction = activeRect.top < overMiddleY ? 'above' : 'below';

    setOverId(over.id as string);
    setDragDirection(direction);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    
    if (over && active.id !== over.id) {
      const oldIndex = folders.findIndex(folder => folder.id === active.id);
      const newIndex = folders.findIndex(folder => folder.id === over.id);
      
      if (oldIndex !== -1 && newIndex !== -1) {
        const reorderedFolders = arrayMove(folders, oldIndex, newIndex);
        reorderFolders(reorderedFolders);
      }
    }
    
    setActiveId(null);
    setOverId(null);
    setDragDirection(null);
  };

  if (isLoading && folders.length === 0) {
    return (
      <Box p={4} textAlign="center">
        <Spinner size="md" />
        <Text fontSize="sm" mt={2}>Loading folders...</Text>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert status="error" variant="subtle">
        <AlertIcon />
        Error loading folders: {error}
      </Alert>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <VStack align="stretch" spacing={2} p={2}>
        <InputGroup size="sm">
          <InputLeftElement pointerEvents="none">
            <SearchIcon color="gray.300" />
          </InputLeftElement>
          <Input
            placeholder="Search folders..."
            value={searchQuery}
            onChange={handleSearchChange}
          />
          {searchQuery && (
            <InputRightElement>
              <IconButton
                aria-label="Clear search"
                icon={<CloseIcon />}
                size="xs"
                variant="ghost"
                onClick={clearSearch}
              />
            </InputRightElement>
          )}
        </InputGroup>

        <Button
          leftIcon={<AddIcon />}
          size="sm"
          variant="outline"
          onClick={onCreateOpen}
          aria-label="Create new folder"
        >
          Create Folder
        </Button>

        {filteredTreeData.length === 0 ? (
          <Box p={4} textAlign="center">
            <Text fontSize="sm" color="gray.500">
              {searchQuery ? 'No matching folders found' : 'No folders created yet.'}
            </Text>
          </Box>
        ) : (
          <Box role="tree" aria-label="Folder structure">
            <SortableContext
              items={filteredTreeData.map(node => node.id)}
              strategy={verticalListSortingStrategy}
            >
              <AnimatePresence>
                {filteredTreeData.map((rootNode) => (
                  <motion.div
                    key={rootNode.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ duration: 0.2 }}
                  >
                    <FolderTreeNode
                      key={rootNode.id}
                      node={rootNode}
                      level={0}
                      isSelected={rootNode.id === selectedFolderId}
                      onSelect={setSelectedFolderId}
                      isDragging={activeId === rootNode.id}
                      isOver={overId === rootNode.id}
                      dropDirection={dragDirection}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            </SortableContext>
          </Box>
        )}

        <DragOverlay>
          {activeId ? (
            <Box
              bg={dragOverlayBg}
              p={2}
              borderRadius="md"
              boxShadow="lg"
              opacity={0.9}
              transform="scale(1.02)"
              transition="transform 0.2s"
              border="1px solid"
              borderColor={useColorModeValue('gray.200', 'gray.600')}
            >
              {filteredTreeData.find(node => node.id === activeId)?.name}
            </Box>
          ) : null}
        </DragOverlay>

        <CreateFolderModal
          isOpen={isCreateOpen}
          onClose={onCreateClose}
          parentId={null}
        />
      </VStack>
    </DndContext>
  );
} 