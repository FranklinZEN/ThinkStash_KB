import { create } from 'zustand';
import type { PartialBlock } from '@blocknote/core';

interface StagingCardState {
  stagedTitle: string | null;
  stagedContentBlocks: PartialBlock[] | null;
  stagedKeywords: string[] | null;
  isLoading: boolean;
  error: string | null;
  startLoading: () => void;
  setData: (title: string, contentBlocks: PartialBlock[], keywords: string[]) => void;
  setError: (errorMessage: string) => void;
  clearData: () => void;
}

export const useStagingCardStore = create<StagingCardState>((set) => ({
  stagedTitle: null,
  stagedContentBlocks: null,
  stagedKeywords: null,
  isLoading: false,
  error: null,

  startLoading: () => set({ isLoading: true, error: null }),

  setData: (title, contentBlocks, keywords) =>
    set({
      stagedTitle: title,
      stagedContentBlocks: contentBlocks,
      stagedKeywords: keywords,
      isLoading: false,
      error: null,
    }),

  setError: (errorMessage) =>
    set({ error: errorMessage, isLoading: false, stagedTitle: null, stagedContentBlocks: null, stagedKeywords: null }),

  clearData: () =>
    set({
      stagedTitle: null,
      stagedContentBlocks: null,
      stagedKeywords: null,
      isLoading: false,
      error: null,
    }),
})); 