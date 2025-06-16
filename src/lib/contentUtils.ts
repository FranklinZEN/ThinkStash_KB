import type { PartialBlock } from '@blocknote/core';
import type { ContentBlock as AIServiceContentBlock } from '@/types/api/ai-service';
import { v4 as uuidv4 } from 'uuid';
import {
  type AppPartialBlock,
  type AppInlineContent,
  type AppInlineContentArray,
} from '@/lib/blocknote/appSchema';

// ====================================================================================
// FUNCTION 1: Convert AI Service Blocks TO BlockNote Editor Blocks (for DISPLAY)
// ====================================================================================
export const mapContentBlocksToPartialBlocks = (
  aiBlocks: AIServiceContentBlock[] | undefined | null,
): AppPartialBlock[] => {
  if (!aiBlocks || aiBlocks.length === 0) return [];

  const result = aiBlocks.flatMap((block): AppPartialBlock | AppPartialBlock[] | null => {
      const blockId = block.id || uuidv4();

      switch (block.type) {
        case 'heading':
          return {
            id: blockId,
            type: 'heading',
            props: {
              level: block.props?.level || 2,
            },
            content: extractTextFromContent(block.content),
          };

        case 'image':
          return {
            id: blockId,
            type: 'image',
            props: {
              url: block.props?.src || '',
              caption: block.props?.caption || '',
            },
          };
        
        case 'code':
        case 'code_snippet':
            return {
                id: blockId,
                type: 'codeBlock',
                content: extractTextFromContent(block.content),
                props: {
                    language: block.props?.language || 'auto'
                }
            }

        case 'list': {
          const isOrdered = block.props?.ordered || false;
          return (block.children || []).map((child): AppPartialBlock => {
            return {
              id: child.id || uuidv4(),
              type: isOrdered ? 'numberedListItem' : 'bulletListItem',
              content: extractTextFromContent(child.content),
              children: mapContentBlocksToPartialBlocks(child.children)
            };
          });
        }
        
        case 'paragraph':
        case 'text':
        default:
          return {
            id: blockId,
            type: 'paragraph',
            content: extractTextFromContent(block.content),
          };
      }
    }
  );

  return result.filter((b): b is AppPartialBlock => b !== null);
};


// ====================================================================================
// FUNCTION 2: Convert BlockNote Editor Blocks TO AI Service Blocks (for SAVING)
// ====================================================================================
export const mapPartialBlocksToAIServiceContentBlocks = (
  partialBlocks: AppPartialBlock[],
  userId: string,
  documentId?: string | null,
): AIServiceContentBlock[] => {
  if (!partialBlocks || partialBlocks.length === 0) return [];

  const document_id_str = documentId || '';

  const aiBlocks: AIServiceContentBlock[] = [];
  let i = 0;
  while (i < partialBlocks.length) {
    const block = partialBlocks[i];
    const baseAIBlock: Partial<AIServiceContentBlock> = {
      id: block.id || uuidv4(),
      user_id: userId,
      document_id: document_id_str,
      order_index: i,
    };

    // Group list items together
    if (block.type === 'bulletListItem' || block.type === 'numberedListItem') {
      const isOrdered = block.type === 'numberedListItem';
      const listItems: AIServiceContentBlock[] = [];
      
      // Collect all consecutive list items of the same type
      while (
        i < partialBlocks.length &&
        partialBlocks[i].type === block.type
      ) {
        const currentItem = partialBlocks[i];
        const children = currentItem.children 
          ? mapPartialBlocksToAIServiceContentBlocks(currentItem.children as AppPartialBlock[], userId, documentId)
          : [];

        listItems.push({
          id: currentItem.id || uuidv4(),
          type: 'paragraph', // Individual list items are stored as paragraphs
          content: extractTextFromContent(currentItem.content),
          children: children,
          user_id: userId,
          document_id: document_id_str,
        });
        i++;
      }

      aiBlocks.push({
        ...baseAIBlock,
        id: uuidv4(), // The list container gets a new ID
        type: 'list',
        props: { ordered: isOrdered },
        children: listItems,
        content: '',
      } as AIServiceContentBlock);
      continue; // Continue to next block in the outer loop
    }

    let aiBlock: AIServiceContentBlock | null = null;
    switch (block.type) {
      case 'heading':
        aiBlock = {
          ...baseAIBlock,
          type: 'heading',
          props: { level: block.props?.level },
          content: extractTextFromContent(block.content),
          children: [],
        } as AIServiceContentBlock;
        break;
      case 'paragraph':
        aiBlock = {
          ...baseAIBlock,
          type: 'paragraph',
          content: extractTextFromContent(block.content),
          children: [],
        } as AIServiceContentBlock;
        break;
      case 'image':
        aiBlock = {
          ...baseAIBlock,
          type: 'image',
          props: {
            src: block.props?.url,
            caption: block.props?.caption,
          },
          content: '',
          children: [],
        } as AIServiceContentBlock;
        break;
      case 'codeBlock':
        aiBlock = {
          ...baseAIBlock,
          type: 'code',
          props: {
            language: block.props?.language,
          },
          content: extractTextFromContent(block.content),
          children: [],
        } as AIServiceContentBlock;
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
function extractTextFromContent(content: any): string {
  if (!content) {
    return '';
  }
  if (typeof content === 'string') {
    return content;
  }
  if (Array.isArray(content)) {
    return content.map(extractTextFromContent).join('');
  }
  if (typeof content === 'object' && content.text) {
    return content.text;
  }
  return '';
}

export const extractTextFromInlineContent = (
  inlineContent: AppInlineContentArray | string | undefined | null,
): string => {
  if (!inlineContent) return '';
  if (typeof inlineContent === 'string') return inlineContent;
  return inlineContent
    .map((content) => {
      if (typeof content === 'string') {
        return content;
      }
      if (content.type === 'link') {
        return extractTextFromInlineContent(content.content);
      }
      if ('text' in content) {
        return content.text;
      }
      return '';
    })
    .join('');
};