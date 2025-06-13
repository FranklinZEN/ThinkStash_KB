import type { PartialBlock } from '@blocknote/core';
import type { ContentBlock as AIServiceContentBlock } from '@/types/api/ai-service';
import { v4 as uuidv4 } from 'uuid';
import {
  type AppPartialBlock,
  type AppInlineContentArray,
} from '@/lib/blocknote/appSchema';

// ====================================================================================
// FUNCTION 1: Convert AI Service Blocks TO BlockNote Editor Blocks (for DISPLAY)
// ====================================================================================
export const mapContentBlocksToPartialBlocks = (
  aiBlocks: AIServiceContentBlock[] | undefined | null,
): PartialBlock[] => {
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
        listItems.push({
          type: ordered ? 'numberedListItem' : 'bulletListItem',
          content: [],
          children: mapAIServiceListToPartialBlocks(
            item.items as (string | AIServiceContentBlock)[],
            item.ordered || false,
          ),
        });
      }
    });
    return listItems;
  };

  const result = aiBlocks.flatMap(block => {
    const blockId = block.block_id || block.tmp_id || uuidv4();
    let partialBlock: PartialBlock | PartialBlock[];

    switch (block.type) {
      case 'heading':
        const level = block.level ? Math.max(1, Math.min(3, block.level)) : 2;
        partialBlock = {
          id: blockId,
          type: 'heading',
          props: {
            level: level as 1 | 2 | 3,
          },
          content: block.content || '',
        };
        break;

      case 'list':
        if (block.items && Array.isArray(block.items)) {
          partialBlock = mapAIServiceListToPartialBlocks(
            block.items as (string | AIServiceContentBlock)[],
            block.ordered || false,
          );
        } else {
          partialBlock = [];
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
      
      case 'table':
        partialBlock = {
          id: blockId,
          type: 'paragraph',
          content: block.content || '[Table Content]',
        };
        break;

      default:
        partialBlock = {
          id: blockId,
          type: 'paragraph',
          content: block.content || '',
        };
        break;
    }
    return partialBlock;
  });

  return result;
};

// ====================================================================================
// FUNCTION 2: Convert BlockNote Editor Blocks TO AI Service Blocks (for SAVING)
// ====================================================================================
export const mapPartialBlocksToAIServiceContentBlocks = (
  partialBlocks: AppPartialBlock[],
  userId: string,
  documentId?: string | null,
): AIServiceContentBlock[] => {
  if (!partialBlocks) return [];

  const document_id_str = documentId || '';

  const recursivelyMapChildren = (
    children: AppPartialBlock[],
    isOrdered: boolean,
  ): (string | AIServiceContentBlock)[] => {
    return children.map(child => {
      if (child.children && child.children.length > 0) {
        return {
          type: 'list',
          ordered: isOrdered,
          items: recursivelyMapChildren(child.children as AppPartialBlock[], isOrdered),
          block_id: child.id || uuidv4(),
          user_id: userId,
          document_id: document_id_str,
        } as AIServiceContentBlock;
      }
      // This is the line we are fixing. We are adding 'as AppInlineContentArray'.
      return extractTextFromInlineContent(child.content as AppInlineContentArray);
    });
  };

  const aiBlocks: AIServiceContentBlock[] = [];
  let i = 0;
  while (i < partialBlocks.length) {
    const block = partialBlocks[i];
    const baseAIBlock = {
      block_id: block.id || uuidv4(),
      user_id: userId,
      document_id: document_id_str,
      order_index: i,
    };

    if (block.type === 'bulletListItem' || block.type === 'numberedListItem') {
      const isOrdered = block.type === 'numberedListItem';
      const listItemsCollector = [];
      while (
        i < partialBlocks.length &&
        partialBlocks[i].type === block.type
      ) {
        const currentItem = partialBlocks[i];
        if (currentItem.children && currentItem.children.length > 0) {
          listItemsCollector.push({
            type: 'list',
            ordered: isOrdered,
            items: recursivelyMapChildren(currentItem.children as AppPartialBlock[], isOrdered),
            block_id: currentItem.id || uuidv4(),
            user_id: userId,
            document_id: document_id_str,
          } as AIServiceContentBlock);
        } else {
          // This is the line we are fixing. We are adding 'as AppInlineContentArray'.
          listItemsCollector.push(extractTextFromInlineContent(currentItem.content as AppInlineContentArray));
        }
        i++;
      }
      aiBlocks.push({
        ...baseAIBlock,
        block_id: uuidv4(),
        type: 'list',
        ordered: isOrdered,
        items: listItemsCollector,
      });
      continue;
    }

    let aiBlock: AIServiceContentBlock | null = null;
    switch (block.type) {
      case 'heading':
        aiBlock = {
          ...baseAIBlock,
          type: 'heading',
          level: block.props?.level,
          content: extractTextFromInlineContent(block.content as AppInlineContentArray),
        };
        break;
      case 'paragraph':
        aiBlock = {
          ...baseAIBlock,
          type: 'text',
          content: extractTextFromInlineContent(block.content as AppInlineContentArray),
        };
        break;
      case 'image':
        aiBlock = {
          ...baseAIBlock,
          type: 'image',
          gcs_url: block.props?.url,
          caption: block.props?.caption,
        };
        break;
      case 'codeBlock':
        aiBlock = {
          ...baseAIBlock,
          type: 'code_snippet',
          language: block.props?.language,
          content: extractTextFromInlineContent(block.content as AppInlineContentArray),
        };
        break;
    }

    if (aiBlock) {
      aiBlocks.push(aiBlock);
    }
    i++;
  }

  return aiBlocks;
};

// ====================================================================================
// FUNCTION 3: Helper to extract plain text from BlockNote's content format.
// ====================================================================================
export const extractTextFromInlineContent = (
  inlineContent: AppInlineContentArray | string | undefined,
): string => {
  if (!inlineContent) return '';
  if (typeof inlineContent === 'string') return inlineContent;
  return inlineContent
    .map(item => {
      if (typeof item === 'string') return item;
      if (item.type === 'text') return item.text;
      if (item.type === 'link')
        return extractTextFromInlineContent(item.content);
      return '';
    })
    .join('');
};