import type { PartialBlock } from '@blocknote/core';
// Ensure this path is correct for your project structure
import type { ContentBlock as AIServiceContentBlock } from '@/types/api/ai-service';
import { v4 as uuidv4 } from 'uuid';
import {
  type AppPartialBlock,
  type AppInlineContentArray,
} from '@/lib/blocknote/appSchema';

/**
 * Maps AI Service content blocks to BlockNote PartialBlock format.
 * Handles various block types and ensures a valid, flat array of PartialBlocks.
 */
// REPLACE the existing mapContentBlocksToPartialBlocks function with this one.
export const mapContentBlocksToPartialBlocks = (
  aiBlocks: AIServiceContentBlock[] | undefined | null,
): PartialBlock[] => {
  console.log(
    '[ContentUtils] mapContentBlocksToPartialBlocks received aiBlocks:',
    JSON.parse(JSON.stringify(aiBlocks || [])),
  );
  if (!aiBlocks || aiBlocks.length === 0) return [];

  const mapAIServiceListToPartialBlocks = (
    items: (string | AIServiceContentBlock)[],
    ordered: boolean,
  ): PartialBlock[] => {
    const listItems: PartialBlock[] = [];
    items.forEach(item => {
      if (typeof item === 'string') {
        listItems.push({
          type: ordered ? 'numberedListItem' : 'bulletListItem',
          content: [{ type: 'text', text: item, styles: {} }],
        });
      } else if (item && item.type === 'list' && item.items) {
        // This handles nested lists.
        // It creates a new list item and nests the sub-list within its children.
        listItems.push({
          type: ordered ? 'numberedListItem' : 'bulletListItem',
          content: [], // The parent list item has no text content itself
          children: mapAIServiceListToPartialBlocks(
            item.items as (string | AIServiceContentBlock)[],
            item.ordered || false,
          ),
        });
      }
    });
    return listItems;
  };

  const result = aiBlocks.flatMap((block, blockIndex) => {
    const blockId = block.block_id || block.tmp_id || uuidv4();
    let partialBlock: PartialBlock | PartialBlock[];

    switch (block.type) {
      case 'heading':
        partialBlock = {
          id: blockId,
          type: 'heading',
          props: {
            level: (block.level && block.level >= 1 && block.level <= 6
              ? block.level
              : 2) as 1 | 2 | 3 | 4 | 5 | 6,
          },
          content: block.content || '',
        };
        break;

      case 'list':
        // This is a special case as a list block from the AI service
        // is converted into multiple BlockNote list items.
        if (block.items && Array.isArray(block.items)) {
          partialBlock = mapAIServiceListToPartialBlocks(
            block.items as (string | AIServiceContentBlock)[],
            block.ordered || false,
          );
        } else {
          partialBlock = []; // Return an empty array if list has no items
        }
        break;

      case 'image':
        if (block.gcs_url) {
          partialBlock = {
            id: blockId,
            type: 'image',
            props: {
              url: block.gcs_url,
              caption: block.caption || '',
            },
          };
        } else {
          // Fallback for an image block without a URL
          partialBlock = {
            id: blockId,
            type: 'paragraph',
            content: '[Image source missing]',
          };
        }
        break;

      case 'code_snippet':
        partialBlock = {
          id: blockId,
          type: 'codeBlock',
          props: {
            language: block.language || 'auto',
          },
          content: block.content || '',
        };
        break;
      
      // Since BlockNote core does not have a native table block,
      // we render the table's HTML content inside a paragraph as a fallback.
      case 'table':
        partialBlock = {
          id: blockId,
          type: 'paragraph',
          content: block.content || '[Table Content]',
        };
        break;

      default:
        // This handles 'text', 'paragraph', and any other unknown types.
        partialBlock = {
          id: blockId,
          type: 'paragraph',
          content: block.content || '',
        };
        break;
    }

    // The flatMap will correctly handle cases where a single AI block
    // (like 'list') generates multiple BlockNote blocks.
    return partialBlock;
  });

  console.log(
    '[ContentUtils] mapContentBlocksToPartialBlocks returning result:',
    JSON.parse(JSON.stringify(result)),
  );
  return result;
};