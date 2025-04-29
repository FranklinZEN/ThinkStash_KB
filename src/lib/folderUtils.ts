// src/lib/folderUtils.ts

// Define the structure for the API response (flat list item)
export interface FolderListItem {
  id: string;
  name: string;
  parentId: string | null;
  _count?: {
    cards?: number;
  };
  // Add other fields if needed, e.g., updatedAt
}

// Define the structure for the nested tree node
export interface FolderTreeNode extends FolderListItem {
  children: FolderTreeNode[];
}

/**
 * Converts a flat list of folders into a nested tree structure.
 * Assumes the input list contains all folders for a user.
 */
export function buildTree(folders: FolderListItem[]): FolderTreeNode[] {
  const tree: FolderTreeNode[] = [];
  const map: { [key: string]: FolderTreeNode } = {};

  // First pass: Create nodes and map them by ID
  folders.forEach(folder => {
    map[folder.id] = {
      ...folder,
      children: [],
    };
  });

  // Second pass: Build the tree structure
  folders.forEach(folder => {
    const node = map[folder.id];
    if (folder.parentId && map[folder.parentId]) {
      // If it has a parent and the parent exists in the map, add node to parent's children
      map[folder.parentId].children.push(node);
    } else {
      // If it has no parent or parent doesn't exist (shouldn't happen with clean data), add to root
      tree.push(node);
    }
  });

  // Optional: Sort children alphabetically at each level if needed
  const sortChildren = (nodes: FolderTreeNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    nodes.forEach(node => sortChildren(node.children));
  };
  sortChildren(tree);

  return tree;
} 