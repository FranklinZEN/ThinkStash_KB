'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';

interface Card {
  id: string;
  title: string;
  content: any;
  userId: string;
  folderId: string | null;
  createdAt: string;
  updatedAt: string;
  folder?: {
    id: string;
    name: string;
  } | null;
  tags: { name: string }[];
}

export function useCards() {
  const { data: session } = useSession();
  const [cards, setCards] = useState<Card[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCards = async () => {
    if (!session?.user?.id) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/cards');
      if (!response.ok) {
        throw new Error('Failed to fetch cards');
      }
      const data = await response.json();
      setCards(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch cards');
      console.error('Error fetching cards:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCards();
  }, [session?.user?.id]);

  return {
    cards,
    isLoading,
    error,
    fetchCards,
  };
} 