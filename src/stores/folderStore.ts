import { create } from 'zustand';
import { FolderListItem } from '@/lib/folderUtils';

interface FolderState {
  folders: FolderListItem[];
  isLoading: boolean;
  error: string | null;
  fetchFolders: () => Promise<void>;
  addFolder: (name: string, parentId: string | null) => Promise<boolean>; // Returns true on success
  renameFolder: (folderId: string, newName: string) => Promise<boolean>; // Add rename action
  deleteFolder: (folderId: string) => Promise<boolean>; // Add delete action
  reorderFolders: (reorderedFolders: FolderListItem[]) => Promise<void>;
  // Add deleteFolder action later
}

export const useFolderStore = create<FolderState>((set, get) => ({
  folders: [],
  isLoading: false,
  error: null,

  fetchFolders: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch('/api/folders');
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to fetch folders: ${response.statusText}`);
      }
      const foldersData: FolderListItem[] = await response.json();
      set({ folders: foldersData, isLoading: false });
    } catch (err: any) {
      console.error("Folder fetch error:", err);
      set({ error: err.message || 'Could not load folders.', isLoading: false });
    }
  },

  addFolder: async (name: string, parentId: string | null) => {
    set({ isLoading: true }); // Indicate general loading/processing state
    let success = false;
    try {
      const response = await fetch('/api/folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, parentId }),
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || `Failed to create folder: ${response.statusText} (Status: ${response.status})`);
      }

      // Refresh the folder list on success
      await get().fetchFolders();
      success = true;

    } catch (err: any) {
      console.error("Add folder error:", err);
      // Set error state or rely on toast in component
      set({ error: err.message || 'Could not create folder.' }); 
    } finally {
       set({ isLoading: false }); // Reset general loading state
    }
    return success;
  },

  renameFolder: async (folderId: string, newName: string) => {
    set({ isLoading: true }); // Use general loading state
    let success = false;
    try {
      const response = await fetch(`/api/folders/${folderId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName }),
      });
      const result = await response.json();

      if (!response.ok) {
        // Handle specific errors like 409 conflict
        throw new Error(result.error || `Failed to rename folder: ${response.statusText} (Status: ${response.status})`);
      }

      // Refresh the folder list on success
      await get().fetchFolders();
      success = true;

    } catch (err: any) {
      console.error("Rename folder error:", err);
      set({ error: err.message || 'Could not rename folder.' });
    } finally {
       set({ isLoading: false });
    }
    return success;
  },

  deleteFolder: async (folderId: string) => {
    set({ isLoading: true }); // Use general loading state
    let success = false;
    try {
      const response = await fetch(`/api/folders/${folderId}`, {
        method: 'DELETE',
      });
      const result = await response.json().catch(() => ({})); // Catch errors if body is empty (e.g., 204)

      if (!response.ok) {
          // Handle specific errors like 400 (not empty)
          throw new Error(result.error || `Failed to delete folder: ${response.statusText} (Status: ${response.status})`);
      }

      // Refresh the folder list on success
      await get().fetchFolders();
      success = true;

    } catch (err: any) {
        console.error("Delete folder error:", err);
        set({ error: err.message || 'Could not delete folder.' });
    } finally {
         set({ isLoading: false });
    }
    return success;
  },

  reorderFolders: async (reorderedFolders: FolderListItem[]) => {
    try {
      const response = await fetch('/api/folders/reorder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folders: reorderedFolders }),
      });
      if (!response.ok) {
        throw new Error('Failed to reorder folders');
      }
      set({ folders: reorderedFolders });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Unknown error' });
    }
  },
})); 