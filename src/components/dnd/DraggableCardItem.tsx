'use client';

import React from 'react';
import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { Box } from '@chakra-ui/react';
import { CardListItem } from '@/stores/cardStore'; // Import the card type

interface DraggableCardItemProps {
  card: CardListItem; // Pass the whole card object instead of just id
  children: React.ReactNode;
}

export default function DraggableCardItem({ card, children }: DraggableCardItemProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: card.id, // Use card.id for the draggable ID
    data: {
      type: 'card',
      cardData: card
    }
  });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1, // Make it semi-transparent while dragging
    cursor: isDragging ? 'grabbing' : 'grab', // Change cursor
    touchAction: 'none', // Prevent touch scrolling while dragging
    userSelect: 'none', // Prevent text selection while dragging
    // zIndex: isDragging ? 100 : undefined, // Optional: lift item while dragging
  };

  return (
    <Box
      ref={setNodeRef} // Attach dnd-kit ref
      style={style}
      {...listeners} // Attach dnd-kit event listeners
      {...attributes} // Attach dnd-kit attributes (e.g., role)
      role="button"
      aria-label={`Drag card: ${card.title}`}
    >
      {children} {/* Render the actual card content */}
    </Box>
  );
} 