'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';

interface Folder {
  id: string;
  name: string;
  parentId: string | null;
  userId: string;
  createdAt: string;
  updatedAt: string;
}

export function useFolders() {
  const { data: session } = useSession();
  const [folders, setFolders] = useState<Folder[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFolders = async () => {
    if (!session?.user?.id) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/folders');
      if (!response.ok) {
        throw new Error('Failed to fetch folders');
      }
      const data = await response.json();
      setFolders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch folders');
      console.error('Error fetching folders:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFolders();
  }, [session?.user?.id]);

  return {
    folders,
    isLoading,
    error,
    fetchFolders,
  };
} 