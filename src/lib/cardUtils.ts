import { PartialBlock } from '@blocknote/core';

// Updated Block interface to reflect actual content structure
interface TextContent {
  type: 'text';
  text: string;
  styles: Record<string, any>;
}

interface Block {
  id: string;
  type: string;
  props: Record<string, any>;
  // Content is an array, potentially containing TextContent or other inline types
  content: (TextContent | Record<string, any>)[];
  children: Block[];
}

export function extractSnippetFromContent(content: Block[] | null | any): string {
  // Added 'any' to handle potential initial type mismatch before casting
  if (!content || !Array.isArray(content)) return '';

  try {
    const textBlocks = (content as Block[]) // Cast to our updated Block type
      .slice(0, 5) // Maybe take a few more blocks for a better snippet
      .map(block => {
        // Check if it's a paragraph and has content array
        if (block.type === 'paragraph' && Array.isArray(block.content) && block.content.length > 0) {
          // Extract text from the content array within the block
          return block.content
            .map(inlineContent => {
              // Check if it's a text node and has text
              if (inlineContent.type === 'text' && typeof inlineContent.text === 'string') {
                return inlineContent.text;
              }
              return ''; // Return empty string for non-text nodes or unexpected formats
            })
            .join(''); // Join text within the same paragraph block without spaces
        }
        // Handle other block types that might contain text if necessary
        // else if (block.type === 'heading' && ...) { ... }
        return ''; // Return empty string for non-paragraph blocks or empty paragraphs
      })
      .filter(text => text.length > 0); // Filter out empty strings resulting from non-text blocks

    // Join the text from different blocks with spaces
    const snippet = textBlocks.join(' ');

    // Truncate if too long
    const MAX_LENGTH = 150; // Adjusted max length slightly
    if (snippet.length > MAX_LENGTH) {
      return snippet.substring(0, MAX_LENGTH).trim() + '...';
    }

    return snippet.trim();
  } catch (error) {
    console.error("Error extracting snippet from content:", error);
    console.error("Problematic content:", content);
    return ''; // Return empty string on error
  }
} 