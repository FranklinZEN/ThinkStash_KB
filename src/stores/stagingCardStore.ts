import { create } from 'zustand';
// import type { PartialBlock } from '@blocknote/core'; // No longer needed here
import type { ContentBlock as AIServiceContentBlock } from '@/types/api/ai-service'; // Use the correct type

interface StagingCardState {
  stagedTitle: string | null;
  stagedContentBlocks: AIServiceContentBlock[] | null; // Changed type from PartialBlock[]
  stagedKeywords: string[] | null;
  isLoading: boolean;
  error: string | null;
  startLoading: () => void;
  setData: (
    title: string | null, // Allow null for title as well for consistency
    contentBlocks: AIServiceContentBlock[] | null, // Changed type and allow null
    keywords: string[] | null, // Allow null
  ) => void;
  setError: (errorMessage: string) => void;
  clearData: () => void;
}

export const useStagingCardStore = create<StagingCardState>((set) => ({
  stagedTitle: null,
  stagedContentBlocks: null, // Initialize as null
  stagedKeywords: null,
  isLoading: false,
  error: null,

  startLoading: () => set({ isLoading: true, error: null }),

  setData: (title, contentBlocks, keywords) => // contentBlocks is now AIServiceContentBlock[] | null
    set({
      stagedTitle: title,
      stagedContentBlocks: contentBlocks, // Stored as AIServiceContentBlock[] | null
      stagedKeywords: keywords,
      isLoading: false,
      error: null,
    }),

  setError: (errorMessage) =>
    set({
      error: errorMessage,
      isLoading: false,
      stagedTitle: null,
      stagedContentBlocks: null,
      stagedKeywords: null,
    }),

  clearData: () =>
    set({
      stagedTitle: null,
      stagedContentBlocks: null,
      stagedKeywords: null,
      isLoading: false,
      error: null,
    }),
})); 