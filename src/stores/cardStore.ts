import { create } from 'zustand';
import type { BlockNoteDocument } from '@/types/blocknote';

// Update CardListItem type to include isStarred and tags
export interface CardListItem {
  id: string;
  title: string;
  userId: string;
  createdAt: Date;
  updatedAt: Date;
  folderId: string | null;
  folder?: {
    id: string;
    name: string;
  } | null;
  isStarred: boolean; // Added isStarred
  tags: { name: string }[]; // Added tags
  content: BlockNoteDocument | null; // No longer optional
}

// Type for raw card data from API with string dates
interface ApiCard extends Omit<CardListItem, 'createdAt' | 'updatedAt'> {
  createdAt: string;
  updatedAt: string;
}

// Interface for pagination state from the API
export interface PaginationState {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

interface CardState {
  cards: CardListItem[];
  pagination: PaginationState | null;
  isLoading: boolean;
  error: string | null;
  fetchCards: (page?: number, pageSize?: number) => Promise<void>;
  // deleteCard action added
  deleteCard: (cardId: string) => Promise<void>;
  // moveCard action added (if not handled elsewhere)
  moveCard: (cardId: string, targetFolderId: string | null) => Promise<void>;
}

const DEFAULT_PAGE_SIZE = 20;

export const useCardStore = create<CardState>((set, get) => ({
  cards: [],
  pagination: null,
  isLoading: false,
  error: null,

  fetchCards: async (
    page: number = 1,
    pageSize: number = DEFAULT_PAGE_SIZE,
  ) => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch(
        `/api/cards?page=${page}&pageSize=${pageSize}`,
      );
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.message || `Failed to fetch cards: ${response.statusText}`,
        );
      }
      const result = await response.json(); // Expects { data: ApiCard[], pagination: {} }

      // Parse date strings into Date objects
      const parsedCards = result.data.map((card: ApiCard) => ({
        ...card,
        createdAt: new Date(card.createdAt),
        updatedAt: new Date(card.updatedAt),
      }));

      set({
        cards: parsedCards,
        pagination: result.pagination,
        isLoading: false,
      });
    } catch (err: unknown) {
      console.error('Card fetch error:', err);
      const errorMessage =
        err instanceof Error ? err.message : 'Could not load cards.';
      set({
        error: errorMessage,
        isLoading: false,
        cards: [],
        pagination: null,
      });
    }
  },

  deleteCard: async (cardId: string) => {
    const originalCards = get().cards;
    const originalPagination = get().pagination;
    set((state) => ({
      cards: state.cards.filter((card) => card.id !== cardId),
      // Optionally adjust totalItems if on the current page
      pagination: state.pagination
        ? { ...state.pagination, totalItems: state.pagination.totalItems - 1 }
        : null,
    }));

    try {
      const response = await fetch(`/api/cards/${cardId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Failed to delete card');
      }
      // After successful deletion, refetch the current page to ensure data consistency
      // especially if totalPages changes or items shift.
      if (get().pagination) {
        await get().fetchCards(
          get().pagination!.page,
          get().pagination!.pageSize,
        );
      } else {
        await get().fetchCards(); // Fallback to first page
      }
    } catch (err: unknown) {
      console.error('Delete card error:', err);
      const errorMessage =
        err instanceof Error ? err.message : 'Could not delete card.';
      set({
        error: errorMessage,
        cards: originalCards,
        pagination: originalPagination,
      }); // Revert on error
    }
  },

  moveCard: async (cardId: string, targetFolderId: string | null) => {
    // For moving, it's usually best to just refetch the current view as folder association changes.
    set({ isLoading: true });
    try {
      const response = await fetch(`/api/cards/${cardId}/move`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folderId: targetFolderId }),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Failed to move card');
      }
      // Refetch the current page of cards to reflect the change
      if (get().pagination) {
        await get().fetchCards(
          get().pagination!.page,
          get().pagination!.pageSize,
        );
      } else {
        await get().fetchCards(); // Fallback to first page
      }
    } catch (err: unknown) {
      console.error('Move card error:', err);
      const errorMessage =
        err instanceof Error ? err.message : 'Could not move card.';
      set({ error: errorMessage, isLoading: false }); // Don't revert cards, just show error
    } finally {
      if (get().isLoading) {
        // Ensure isLoading is false if fetchCards wasn't called or failed above
        set({ isLoading: false });
      }
    }
  },
}));
