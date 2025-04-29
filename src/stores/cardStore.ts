import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { fetchWithAuth } from '@/lib/fetchWithAuth'; // Assuming fetchWithAuth handles auth

// Update CardListItem type to include isStarred and tags
export interface CardListItem {
  id: string;
  title: string;
  updatedAt: string;
  folderId?: string | null;
  folder?: {
    id?: string | null;
    name?: string | null;
  } | null;
  isStarred: boolean; // Added isStarred
  tags: { name: string }[]; // Added tags
  content: any; // Added content if needed for snippet extraction in fallback?
}

interface CardState {
  cards: CardListItem[];
  isLoading: boolean;
  error: string | null;
  fetchCards: () => Promise<void>;
  // deleteCard action added
  deleteCard: (cardId: string) => Promise<void>;
  // moveCard action added (if not handled elsewhere)
  moveCard: (cardId: string, targetFolderId: string | null) => Promise<void>;
}

export const useCardStore = create<CardState>((set, get) => ({
  cards: [],
  isLoading: false,
  error: null,

  fetchCards: async () => {
    set({ isLoading: true, error: null });
    try {
      // Assuming fetchWithAuth handles authentication automatically
      // Or use regular fetch if auth is handled server-side via cookies
      const response = await fetch('/api/cards');
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to fetch cards: ${response.statusText}`);
      }
      const cardsData: CardListItem[] = await response.json();
      // Sorting is now handled by the API, no need to sort here unless desired differently
      set({ cards: cardsData, isLoading: false });
    } catch (err: any) {
      console.error("Card fetch error:", err);
      set({ error: err.message || 'Could not load cards.', isLoading: false });
    }
  },

  deleteCard: async (cardId: string) => {
    // Optimistic UI update (optional)
    const originalCards = get().cards;
    set((state) => ({
      cards: state.cards.filter((card) => card.id !== cardId),
    }));

    try {
      const response = await fetch(`/api/cards/${cardId}`, { method: 'DELETE' });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Failed to delete card');
      }
      // No need to refetch if optimistic update is sufficient or fetchCards is called elsewhere
    } catch (err: any) {
      console.error("Delete card error:", err);
      set({ error: err.message || 'Could not delete card.', cards: originalCards }); // Revert on error
      // Optionally re-throw or handle error display
    }
  },

  moveCard: async (cardId: string, targetFolderId: string | null) => {
    // Optimistic UI update or simply refetch after success
    const originalCards = get().cards;
    set({ isLoading: true }); // Indicate loading during move

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
      // Refetch the cards list to reflect the change
      await get().fetchCards();
    } catch (err: any) {
      console.error("Move card error:", err);
      set({ error: err.message || 'Could not move card.', cards: originalCards, isLoading: false }); // Revert/handle error
    } finally {
      // Ensure loading is set to false if fetchCards wasn't called or failed
      if (get().isLoading) {
          set({ isLoading: false });
      }
    }
  },
})); 