'use client';

import { useState, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import type { BlockNoteDocument } from '@/types/blocknote';

interface Card {
  id: string;
  title: string;
  content: BlockNoteDocument | null;
  userId: string;
  folderId: string | null;
  createdAt: string;
  updatedAt: string;
  folder?: {
    id: string;
    name: string;
  } | null;
  tags: { name: string }[];
  isStarred?: boolean;
}

export interface PaginationInfo {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export function useCards() {
  const { data: session } = useSession();
  const [cards, setCards] = useState<Card[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCards = useCallback(
    async (page: number = 1, pageSize: number = 20) => {
      if (!session?.user?.id) return;

      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `/api/cards?page=${page}&pageSize=${pageSize}`,
        );
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.message || 'Failed to fetch cards');
        }
        const result = await response.json();
        setCards(result.data);
        setPagination(result.pagination);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to fetch cards';
        setError(errorMessage);
        console.error('Error fetching cards:', errorMessage);
        setCards([]);
        setPagination(null);
      } finally {
        setIsLoading(false);
      }
    },
    [session?.user?.id],
  );

  return {
    cards,
    pagination,
    isLoading,
    error,
    fetchCards,
  };
}
