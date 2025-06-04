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
export const mapContentBlocksToPartialBlocks = (
  aiBlocks: AIServiceContentBlock[] | undefined | null,
): PartialBlock[] => {
  console.log(
    '[ContentUtils] mapContentBlocksToPartialBlocks received aiBlocks:',
    JSON.parse(JSON.stringify(aiBlocks || [])),
  );
  if (!aiBlocks || aiBlocks.length === 0) return [];

  // Helper function to recursively process list items
  const mapAIServiceListToPartialBlocks = (
    items: (string | AIServiceContentBlock)[],
    ordered: boolean,
    level: number = 0, // Keep track of nesting level for BlockNote
    parentBlockIdHint?: string, // Optional hint from parent, not strictly used for item IDs yet
  ): PartialBlock[] => {
    console.log(
      `[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) received items:`,
      JSON.parse(JSON.stringify(items)),
      'Ordered:',
      ordered,
    );
    const partialBlocks: PartialBlock[] = [];
    let lastListItem: PartialBlock | null = null;

    items.forEach((item, index) => {
      const listItemId = uuidv4(); // Each list item gets a unique ID
      console.log(
        `[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) processing item ${index} with ID ${listItemId}:`,
        JSON.parse(JSON.stringify(item)),
      );
      if (typeof item === 'string') {
        const listItem: PartialBlock = {
          id: listItemId, // Assign unique ID
          type: ordered ? 'numberedListItem' : 'bulletListItem',
          content: [{ type: 'text', text: item, styles: {} }],
          children: [], // Initialize children for potential sub-lists
        };
        partialBlocks.push(listItem);
        lastListItem = listItem;
        console.log(
          `[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) created string list item:`,
          JSON.parse(JSON.stringify(listItem)),
        );
      } else if (item && item.type === 'list' && item.items) {
        console.log(
          `[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) processing nested list item:`,
          JSON.parse(JSON.stringify(item)),
        );
        const nestedListItems = mapAIServiceListToPartialBlocks(
          item.items as (string | AIServiceContentBlock)[],
          item.ordered || false,
          level + 1, // Pass incremented level
          listItemId, // Pass current list item ID as parent hint for nested items
        );
        if (lastListItem) {
          lastListItem.children = nestedListItems;
          console.log(
            `[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) attached children to lastListItem:`,
            JSON.parse(JSON.stringify(lastListItem)),
          );
        } else {
          console.log(
            `[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) no lastListItem, pushing nested items to current level:`,
            JSON.parse(JSON.stringify(nestedListItems)),
          );
          partialBlocks.push(...nestedListItems);
        }
      } else {
        console.log(
          `[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) SKIPPED item ${index}:`,
          JSON.parse(JSON.stringify(item)),
        );
      }
    });
    console.log(
      `[ContentUtils] mapAIServiceListToPartialBlocks (level ${level}) returning partialBlocks:`,
      JSON.parse(JSON.stringify(partialBlocks)),
    );
    return partialBlocks;
  };

  const result = aiBlocks.flatMap((block, blockIndex) => {
    console.log(
      `[ContentUtils] Processing aiBlocks[${blockIndex}]:`,
      JSON.parse(JSON.stringify(block)),
    );
    // Ensure each block has a unique ID, using existing if available, otherwise generate one.
    const blockId = block.block_id || block.tmp_id || uuidv4();

    let partialBlock: PartialBlock | PartialBlock[] = {
      id: blockId,
      type: 'paragraph',
      content: [{ type: 'text', text: '', styles: {} }],
    };

    switch (block.type) {
      case 'text':
      case 'paragraph':
        let paragraphBnContent: AppPartialBlock['content'] = [];
        if (block.content != null) {
          if (Array.isArray(block.content) && block.content.length > 0 && typeof block.content[0] === 'object' && block.content[0] !== null && 'type' in block.content[0] && 'text' in block.content[0]) {
            // Assume it's already AppInlineContentArray if the first item looks like it
            paragraphBnContent = [...block.content];
            console.log(`[ContentUtils] Block type '${block.type}' (ID: ${blockId}) received pre-formatted AppInlineContentArray.`);
          } else if (typeof block.content === 'string') {
            paragraphBnContent = block.content ? [{ type: 'text', text: block.content, styles: {} }] : [];
          } else {
            console.warn(`[ContentUtils] Block type '${block.type}' (ID: ${blockId}) has unexpected content type. Actual content:`, JSON.stringify(block.content));
            paragraphBnContent = [{ type: 'text', text: '[Unsupported content format - Check console]', styles: { italic: true} }];
          }
        }
        partialBlock = {
          id: blockId,
          type: 'paragraph',
          content: paragraphBnContent,
        };
        break;
      case 'heading':
        let headingBnContent: AppPartialBlock['content'] = [];
        if (block.content != null) {
          if (Array.isArray(block.content) && block.content.length > 0 && typeof block.content[0] === 'object' && block.content[0] !== null && 'type' in block.content[0] && 'text' in block.content[0]) {
            // Assume it's already AppInlineContentArray
            headingBnContent = [...block.content];
            console.log(`[ContentUtils] Block type 'heading' (ID: ${blockId}) received pre-formatted AppInlineContentArray.`);
          } else if (typeof block.content === 'string') {
            headingBnContent = block.content ? [{ type: 'text', text: block.content, styles: {} }] : [];
          } else {
            console.warn(`[ContentUtils] Block type 'heading' (ID: ${blockId}) has unexpected content type. Actual content:`, JSON.stringify(block.content));
            headingBnContent = [{ type: 'text', text: '[Unsupported content format - Check console]', styles: { italic: true} }];
          }
        }
        partialBlock = {
          id: blockId,
          type: 'heading',
          props: {
            level: (block.level && block.level >= 1 && block.level <= 3
              ? block.level
              : 1) as 1 | 2 | 3,
          },
          content: headingBnContent,
        };
        break;
      case 'list':
        console.log(
          `[ContentUtils] Identified 'list' block:`,
          JSON.parse(JSON.stringify(block)),
        );
        if (block.items && Array.isArray(block.items)) {
          partialBlock = mapAIServiceListToPartialBlocks(
            block.items as (string | AIServiceContentBlock)[],
            block.ordered || false,
            0, // Start at level 0 for the main list
            blockId, // Pass parent block ID for context if needed by list mapper
          );
        } else {
          console.warn(
            '[ContentUtils] List block has no items or items is not an array:',
            JSON.parse(JSON.stringify(block)),
          );
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
            children: [],
          };
        } else {
          console.warn(`[ContentUtils] Image block (ID: ${blockId}) is missing gcs_url.`);
          partialBlock = {
            id: blockId,
            type: 'paragraph',
            content: [
              {
                type: 'text',
                text: '[Image source missing]',
                styles: { italic: true },
              },
            ],
          };
        }
        break;
      case 'code_snippet':
        let codeContent = '';
        if (block.content != null) {
          if (typeof block.content === 'string') {
            codeContent = block.content;
          } else {
            // Code snippets content should ideally always be a string from the AI Service
            console.warn(`[ContentUtils] Block type 'code_snippet' (ID: ${blockId}) has non-string content. Forcing to string. Actual content:`, JSON.stringify(block.content));
            codeContent = String(block.content); 
          }
        }
        partialBlock = {
          id: blockId,
          type: 'codeBlock',
          props: {
            language: block.language || 'plaintext',
          },
          content: codeContent ? [{ type: 'text', text: codeContent, styles: {} }] : [],
        };
        break;
      default:
        console.warn(
          `[ContentUtils] Encountered unsupported block type: '${block.type || 'unknown'}' (ID: ${blockId}). Block data:`,
          JSON.parse(JSON.stringify(block)),
        );
        // More robust handling for default case content
        let defaultCaseText = `[Unsupported Block Type: ${block.type || 'unknown'}]`;
        if (block.content != null) {
          if (typeof block.content === 'string') {
            defaultCaseText += ` ${block.content}`;
          } else {
            defaultCaseText += ' [Content is non-string, see console for details.]';
            console.warn(`[ContentUtils] Default case for block type '${block.type}' (ID: ${blockId}) has non-string content:`, JSON.parse(JSON.stringify(block.content)));
          }
        }

        partialBlock = {
          id: blockId,
          type: 'paragraph',
          content: [{ type: 'text', text: defaultCaseText, styles: { italic: true } }],
        };
    }
    console.log(
      `[ContentUtils] FlatMap generated for aiBlocks[${blockIndex}]:`,
      JSON.parse(JSON.stringify(partialBlock)),
    );
    return partialBlock;
  });
  console.log(
    '[ContentUtils] mapContentBlocksToPartialBlocks final result:',
    JSON.parse(JSON.stringify(result)),
  );
  return result;
};

// Helper function to extract plain text from BlockNote InlineContent[]
export const extractTextFromInlineContent = (
  inlineContent: AppInlineContentArray | string | undefined,
): string => {
  if (!inlineContent) return '';
  if (typeof inlineContent === 'string') return inlineContent;
  return inlineContent
    .map((item) => {
      // Ensure item is an object and has a 'type' property before accessing it
      if (typeof item !== 'object' || item === null) return '';

      if (item.type === 'text')
        return (item as { type: 'text'; text: string }).text;
      if (
        item.type === 'link' &&
        (item as { type: 'link'; content: AppInlineContentArray }).content
      ) {
        return extractTextFromInlineContent(
          (item as { type: 'link'; content: AppInlineContentArray }).content,
        );
      }
      // Add other inline types if necessary, for now, just text and link content
      return '';
    })
    .join('');
};

// Function to map BlockNote PartialBlock[] to AIServiceContentBlock[]
export const mapPartialBlocksToAIServiceContentBlocks = (
  partialBlocks: AppPartialBlock[],
  userId: string,
  documentId?: string | null,
): AIServiceContentBlock[] => {
  const aiServiceBlocks: AIServiceContentBlock[] = [];
  if (!partialBlocks || partialBlocks.length === 0) return aiServiceBlocks;

  const docIdToUse = documentId || `temp-doc-${uuidv4()}`;

  let currentOrderIndex = 0;
  let i = 0;

  while (i < partialBlocks.length) {
    const block = partialBlocks[i];
    if (!block || !block.type) {
      i++;
      continue;
    }
    // Use existing block.id if available, else generate a new one
    const block_id = block.id || uuidv4();
    const tmp_id = block_id;

    if (block.type === 'bulletListItem' || block.type === 'numberedListItem') {
      const listItemsContent: string[] = [];
      const isOrdered = block.type === 'numberedListItem';
      const listBlockType = block.type;
      // Use ID of the first item as the list's representative ID for the AI service block
      const listBlockId = block_id;

      let listStartNumber: number | null = null;
      if (isOrdered && block.props?.start) {
        const startNum = parseInt(String(block.props.start), 10);
        if (!isNaN(startNum)) {
          listStartNumber = startNum;
        }
      }

      while (
        i < partialBlocks.length &&
        partialBlocks[i]?.type === listBlockType
      ) {
        const listItem = partialBlocks[i];
        if (listItem.content && Array.isArray(listItem.content)) {
          listItemsContent.push(
            extractTextFromInlineContent(
              listItem.content as AppInlineContentArray,
            ),
          );
        }
        i++;
      }

      if (listItemsContent.length > 0) {
        aiServiceBlocks.push({
          block_id: listBlockId,
          tmp_id: listBlockId,
          user_id: userId,
          document_id: docIdToUse,
          type: 'list',
          order_index: currentOrderIndex,
          items: listItemsContent,
          ordered: isOrdered,
          list_start_number: listStartNumber,
          content: null,
        });
        currentOrderIndex++;
      }
      continue; // Continue to the next block in the outer loop
    } else if (block.type === 'paragraph' || block.type === 'heading') {
      // Ensure block.content is AppInlineContentArray before passing to extractTextFromInlineContent
      const textContent = extractTextFromInlineContent(
        block.content as AppInlineContentArray,
      );
      // Keep empty paragraphs if that's desired, or add specific logic
      // Example: only push if textContent is not empty or if it's a paragraph (even if empty)
      if (textContent.trim() !== '' || block.type === 'paragraph') {
        aiServiceBlocks.push({
          block_id,
          tmp_id,
          user_id: userId,
          document_id: docIdToUse,
          type: block.type === 'heading' ? 'heading' : 'text', // Map 'paragraph' to 'text' for AI service
          order_index: currentOrderIndex,
          content: textContent,
          level:
            block.type === 'heading'
              ? (block.props?.level as (1 | 2 | 3 | 4 | 5 | 6) | undefined)
              : undefined,
          items: null,
          ordered: null,
          list_start_number: null,
          language: null,
          image_id_ref: null,
          gcs_url: null,
          alt_text: null,
          caption: null,
          width: null,
          height: null,
          llm_description: null,
          page_number: null,
          bbox: null,
        });
        currentOrderIndex++;
      }
      i++;
    } else if (block.type === 'image') {
      // Handle image blocks
      const imageUrl = block.props?.url as string | undefined;
      const imageCaption = block.props?.caption as string | undefined;

      // The block.id from BlockNote PartialBlock is the original block_id/tmp_id
      // from the AI Service, which should serve as the image_id_ref.
      const imageIdRef = block.id; 

      if (imageUrl && imageIdRef) {
        aiServiceBlocks.push({
          block_id: imageIdRef, // Use the original block ID as the main identifier
          tmp_id: imageIdRef,   // Can be the same if no separate temp ID concept here
          user_id: userId,
          document_id: docIdToUse,
          type: 'image',
          order_index: currentOrderIndex,
          image_id_ref: imageIdRef,
          gcs_url: imageUrl, // This is the HTTPS URL from BlockNote
          caption: imageCaption || null,
          content: null,
          level: null,
          items: null,
          ordered: null,
          list_start_number: null,
          language: null,
          alt_text: null, // Potentially map from props if available, e.g., block.props.alt
          width: null,    // Potentially map from props if available
          height: null,   // Potentially map from props if available
          llm_description: null,
          page_number: null,
          bbox: null,
        });
        currentOrderIndex++;
      } else {
        console.warn(
          `[ContentUtils] Image block (ID: ${block_id}) is missing URL or ID. Skipping. URL: ${imageUrl}, ID: ${imageIdRef}`,
        );
      }
      i++;
    } else {
      // Handle or skip other block types as needed
      // For now, we'll skip unknown block types to avoid errors
      // console.warn("Unsupported block type for AI service conversion:", block.type);
      i++;
    }
  }
  return aiServiceBlocks;
};
