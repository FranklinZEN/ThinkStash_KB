import type { Block, InlineContent } from '@/types/blocknote';

export function extractSnippetFromContent(document: Block[] | null): string {
  if (!document || !Array.isArray(document)) return '';

  try {
    const textSnippets: string[] = [];
    let currentLength = 0;
    const MAX_LENGTH = 150;

    function processInlineContent(inlineContent: InlineContent): string {
      if (inlineContent.type === 'text') {
        return inlineContent.text;
      }
      if (
        inlineContent.type === 'link' &&
        Array.isArray(inlineContent.content)
      ) {
        return inlineContent.content.map(processInlineContent).join('');
      }
      return '';
    }

    for (const block of document) {
      if (currentLength >= MAX_LENGTH) break;

      let blockText = '';
      // Check if block.content is an array of InlineContent
      if (Array.isArray(block.content)) {
        blockText = block.content.map(processInlineContent).join('');
      }
      // Potentially handle TableContent if snippets from tables are desired
      // else if (block.content?.type === 'tableContent') { ... }

      if (blockText) {
        if (textSnippets.length > 0) {
          textSnippets.push(' '); // Add space between block texts
          currentLength += 1;
        }
        const remainingLength = MAX_LENGTH - currentLength;
        if (blockText.length > remainingLength) {
          textSnippets.push(blockText.substring(0, remainingLength));
          currentLength += remainingLength;
        } else {
          textSnippets.push(blockText);
          currentLength += blockText.length;
        }
      }
      if (currentLength >= MAX_LENGTH) break;
    }

    let snippet = textSnippets.join('');

    if (snippet.length > MAX_LENGTH) {
      snippet = snippet.substring(0, MAX_LENGTH);
    }

    if (
      snippet.length === MAX_LENGTH &&
      document.length > 0 &&
      document[0].content &&
      (document[0].content as InlineContent[]).length > 0
    ) {
      // Only add ellipsis if we actually truncated something meaningful
      snippet += '...';
    }

    return snippet.trim();
  } catch (error) {
    console.error('Error extracting snippet from content:', error);
    // console.error("Problematic content:", document); // Be cautious with logging full content
    return ''; // Return empty string on error
  }
}
