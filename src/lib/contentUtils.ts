import type { PartialBlock } from '@blocknote/core';
// Ensure this path is correct for your project structure
import type { ContentBlock as AIServiceContentBlock } from '@/types/api/ai-service';

/**
 * Maps AI Service content blocks to BlockNote PartialBlock format.
 * Handles various block types and ensures a valid, flat array of PartialBlocks.
 */
export const mapContentBlocksToPartialBlocks = (
  aiBlocks: AIServiceContentBlock[] | undefined | null,
): PartialBlock[] => {
  console.log('[ContentUtils] mapContentBlocksToPartialBlocks received aiBlocks:', JSON.parse(JSON.stringify(aiBlocks || [])));
  if (!aiBlocks || aiBlocks.length === 0) return [];

  // Helper function to recursively process list items
  const mapAIServiceListToPartialBlocks = (
    items: (string | AIServiceContentBlock)[],
    ordered: boolean,
    level: number = 0 // Keep track of nesting level for BlockNote
  ): PartialBlock[] => {
    console.log(`[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) received items:`, JSON.parse(JSON.stringify(items)), 'Ordered:', ordered);
    const partialBlocks: PartialBlock[] = [];
    let lastListItem: PartialBlock | null = null;

    items.forEach((item, index) => {
      console.log(`[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) processing item ${index}:`, JSON.parse(JSON.stringify(item)));
      if (typeof item === 'string') {
        const listItem: PartialBlock = {
          type: ordered ? 'numberedListItem' : 'bulletListItem',
          content: [{ type: 'text', text: item, styles: {} }],
          children: [], // Initialize children for potential sub-lists
        };
        partialBlocks.push(listItem);
        lastListItem = listItem; 
        console.log(`[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) created string list item:`, JSON.parse(JSON.stringify(listItem)));
      } else if (item && item.type === 'list' && item.items) {
        console.log(`[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) processing nested list item:`, JSON.parse(JSON.stringify(item)));
        const nestedListItems = mapAIServiceListToPartialBlocks(
          item.items as (string | AIServiceContentBlock)[],
          item.ordered || false,
          level + 1
        );
        if (lastListItem) {
          lastListItem.children = nestedListItems;
          console.log(`[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) attached children to lastListItem:`, JSON.parse(JSON.stringify(lastListItem)));
        } else {
          console.log(`[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) no lastListItem, pushing nested items to current level:`, JSON.parse(JSON.stringify(nestedListItems)));
          partialBlocks.push(...nestedListItems);
        }
      } else {
        console.log(`[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) SKIPPED item ${index}:`, JSON.parse(JSON.stringify(item)));
      }
    });
    console.log(`[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) returning partialBlocks:`, JSON.parse(JSON.stringify(partialBlocks)));
    return partialBlocks;
  };

  const result = aiBlocks.flatMap((block, blockIndex) => {
    console.log(`[ContentUtils] Processing aiBlocks[${blockIndex}]:`, JSON.parse(JSON.stringify(block)));
    let partialBlock: PartialBlock | PartialBlock[] = {
      type: 'paragraph',
      content: [{ type: 'text', text: '', styles: {} }], 
    };

    switch (block.type) {
      case 'text':
        partialBlock = {
          type: 'paragraph',
          content: block.content ? [{ type: 'text', text: block.content, styles: {} }] : [],
        };
        break;
      case 'heading':
        partialBlock = {
          type: 'heading',
          props: {
            level: (block.level && block.level >= 1 && block.level <= 3 ? block.level : 1) as 1 | 2 | 3,
          },
          content: block.content ? [{ type: 'text', text: block.content, styles: {} }] : [],
        };
        break;
      case 'list':
        console.log(`[ContentUtils] Identified 'list' block:`, JSON.parse(JSON.stringify(block)));
        if (block.items && Array.isArray(block.items)) {
          partialBlock = mapAIServiceListToPartialBlocks(block.items as (string | AIServiceContentBlock)[], block.ordered || false);
        } else {
          console.warn('[ContentUtils] List block has no items or items is not an array:', JSON.parse(JSON.stringify(block)));
          partialBlock = []; 
        }
        break;
      case 'image':
        if (block.gcs_url) {
          // console.log('[ImageDebug] Mapping image with URL (should be signed):', block.gcs_url); // Original log, can be re-enabled if needed
          partialBlock = {
            type: 'image',
            props: {
              url: block.gcs_url, 
              caption: block.caption || '',
            },
            children: [], 
          };
        } else {
           partialBlock = { type: 'paragraph', content: [{type: 'text', text: '[Image source missing]', styles: {italic: true}}]};
        }
        break;
      case 'code_snippet':
        partialBlock = {
          type: 'codeBlock', 
          props: {
            language: block.language || 'plaintext', 
          },
          content: block.content || '', 
        };
        break;
      default:
        console.warn('[ContentUtils] Encountered unsupported block type:', JSON.parse(JSON.stringify(block)));
        partialBlock = {
          type: 'paragraph',
          content: [
            { type: 'text', text: `[Unsupported Block Type: ${block.type || 'unknown'}] `, styles: { italic: true } },
            { type: 'text', text: String(block.content || ''), styles: {} },
          ],
        };
    }
    console.log(`[ContentUtils] FlatMap generated for aiBlocks[${blockIndex}]:`, JSON.parse(JSON.stringify(partialBlock)));
    return partialBlock; 
  });
  console.log('[ContentUtils] mapContentBlocksToPartialBlocks final result:', JSON.parse(JSON.stringify(result)));
  return result;
}; 