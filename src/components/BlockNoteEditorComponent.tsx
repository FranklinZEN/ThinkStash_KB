'use client';

import React, { useEffect } from 'react';
import { Box, Flex, Spinner, Text } from '@chakra-ui/react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import {
  BlockNoteEditor as BlockNoteEditorType,
  PartialBlock,
  BlockNoteSchema,
  defaultBlockSpecs,
  getDefaultSlashMenuItems,
  insertOrUpdateBlock,
} from '@blocknote/core';
import '@blocknote/mantine/style.css';

// --- Helper functions ---
const handleFileUpload = async (file: File): Promise<string> => {
  console.log(
    '%c[BlockNoteEditorComponent] DRAG-AND-DROP TEST: handleFileUpload CALLED with file:',
    'color: red; font-weight: bold;',
    file.name,
    file.type,
  );
  const formData = new FormData();
  formData.append('file', file);
  try {
    const response = await fetch('/api/upload/image', {
      method: 'POST',
      body: formData,
    });
    const responseBody = await response.text();
    if (!response.ok) {
      let errorData = {
        message: `Upload failed: ${response.statusText} - ${responseBody}`,
      };
      try {
        errorData = JSON.parse(responseBody);
      } catch (parseError) {
        console.warn(
          '[BlockNoteEditorComponent] handleFileUpload - Could not parse error response as JSON:',
          parseError,
        );
      }
      console.error(
        '[BlockNoteEditorComponent] handleFileUpload - Upload FAILED:',
        errorData,
      );
      const finalErrorMessage =
        typeof errorData.message === 'string'
          ? errorData.message
          : responseBody;
      alert(`Failed to upload image: ${finalErrorMessage}`);
      throw new Error(`Upload failed: ${finalErrorMessage}`);
    }
    const data = JSON.parse(responseBody);
    if (!data.appServedUrl) {
      console.error(
        '[BlockNoteEditorComponent] handleFileUpload - Response MISSING appServedUrl',
      );
      throw new Error('Upload response missing appServedUrl');
    }
    return data.appServedUrl;
  } catch (error) {
    console.error(
      '[BlockNoteEditorComponent] handleFileUpload - CATCH block error:',
      error,
    );
    if (
      !(error instanceof Error && error.message.startsWith('Upload failed:'))
    ) {
      alert(
        `Upload error: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
    throw error;
  }
};

const IMAGE_URL_REGEX = /\.(jpeg|jpg|gif|png|webp)(\?.*)?$/i;
const isValidURL = (string: string) => {
  try {
    new URL(string);
    return true;
  } catch {
    return false;
  }
};

async function handlePastedImageURL(
  pastedText: string,
  editor: BlockNoteEditorType<
    typeof appSchema.blockSchema,
    typeof appSchema.inlineContentSchema,
    typeof appSchema.styleSchema
  >,
): Promise<void> {
  console.log(
    '[BlockNoteEditorComponent] handlePastedImageURL triggered with text:',
    pastedText.substring(0, 100) + '...',
  );
  try {
    const response = await fetch('/api/images/import-by-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ externalImageUrl: pastedText }),
    });
    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({ message: 'Failed to import pasted image URL' }));
      console.error(
        '[BlockNoteEditorComponent] Import via URL FAILED:',
        errorData,
      );
      alert(
        `Error importing image URL: ${errorData.message || 'Unknown error'}`,
      );
      return;
    }
    const result = await response.json();
    if (result.appServedUrl) {
      const currentBlock = editor.getTextCursorPosition().block;
      const shouldReplace =
        Array.isArray(currentBlock.content) &&
        currentBlock.content.length === 0 &&
        currentBlock.type === 'paragraph';
      editor.insertBlocks(
        [
          {
            type: 'image',
            props: { url: result.appServedUrl, caption: 'Pasted Image' },
          },
        ],
        currentBlock.id,
        shouldReplace ? undefined : 'after',
      );
    }
  } catch (error) {
    console.error(
      '[BlockNoteEditorComponent] Error in handlePastedImageURL:',
      error,
    );
  }
}

async function processPastedOrDroppedFile(
  file: File,
  editor: BlockNoteEditorType<
    typeof appSchema.blockSchema,
    typeof appSchema.inlineContentSchema,
    typeof appSchema.styleSchema
  >,
): Promise<void> {
  try {
    const appServedUrl = await handleFileUpload(file);
    if (appServedUrl) {
      const currentBlock = editor.getTextCursorPosition().block;
      const shouldReplace =
        Array.isArray(currentBlock.content) &&
        currentBlock.content.length === 0 &&
        currentBlock.type === 'paragraph';
      editor.insertBlocks(
        [{ type: 'image', props: { url: appServedUrl, caption: file.name } }],
        currentBlock.id,
        shouldReplace ? undefined : 'after',
      );
    }
  } catch (error) {
    console.error(
      '[BlockNoteEditorComponent] Error processing pasted/dropped file:',
      error,
    );
  }
}

// Export appSchema so it can be used by parent components for typing
export const appSchema = BlockNoteSchema.create({
  blockSpecs: defaultBlockSpecs,
});

interface BlockNoteEditorComponentProps {
  onEditorChange: (editor: BlockNoteEditorType | null) => void;
  onContentUpdate?: (blocks: PartialBlock[]) => void;
  editable?: boolean;
  initialContent?: PartialBlock[];
}

export default function BlockNoteEditorComponent({
  onEditorChange,
  onContentUpdate,
  editable = false,
  initialContent,
}: BlockNoteEditorComponentProps) {
  const editorOptions = {
    schema: appSchema,
    initialContent:
      initialContent && initialContent.length > 0 ? initialContent : undefined,
    uploadFile: handleFileUpload,
    pasteHandler: ({
      event,
      editor: currentEditor,
      defaultPasteHandler,
    }: {
      event: ClipboardEvent;
      editor: BlockNoteEditorType<
        typeof appSchema.blockSchema,
        typeof appSchema.inlineContentSchema,
        typeof appSchema.styleSchema
      >;
      defaultPasteHandler: () => boolean;
    }) => {
      console.log(
        '%c[BlockNoteEditorComponent] PASTE EVENT DETECTED',
        'color: blue; font-weight: bold;',
      );
      if (event.clipboardData) {
        const types = event.clipboardData.types;
        console.log('[BlockNoteEditorComponent] Clipboard types:', types);
        types.forEach((type) => {
          try {
            const data = event.clipboardData!.getData(type);
            console.log(
              `[BlockNoteEditorComponent] Data for type "${type}":`,
              type === 'text/html' ||
                type === 'text/plain' ||
                type.startsWith('image/')
                ? data.length > 300
                  ? data.substring(0, 300) + '... (truncated)'
                  : data
                : `[Non-text or too long: ${data.length} chars/bytes]`,
            );
            if (type === 'text/html') {
              const tempDiv = document.createElement('div');
              tempDiv.innerHTML = data;
              const imagesInHtml = Array.from(tempDiv.querySelectorAll('img'));
              console.log(
                '[BlockNoteEditorComponent] Images found in pasted HTML (src attributes):',
                imagesInHtml.map((img) => img.src),
              );
            }
          } catch (e) {
            console.warn(
              `[BlockNoteEditorComponent] Could not getData for type "${type}"`,
              e,
            );
          }
        });

        const pastedFiles = event.clipboardData.files;
        if (pastedFiles && pastedFiles.length > 0) {
          console.log(
            '[BlockNoteEditorComponent] Files found on clipboard (event.clipboardData.files) - count:',
            pastedFiles.length,
          );
          let imageFileProcessed = false;
          Array.from(pastedFiles).forEach((file) => {
            console.log('[BlockNoteEditorComponent] Pasted file details:', {
              name: file.name,
              size: file.size,
              type: file.type,
            });
            if (file.type.startsWith('image/')) {
              console.log(
                '[BlockNoteEditorComponent] Processing pasted image FILE via processPastedOrDroppedFile:',
                file.name,
              );
              processPastedOrDroppedFile(file, currentEditor);
              imageFileProcessed = true;
            }
          });
          if (imageFileProcessed) {
            console.log(
              '[BlockNoteEditorComponent] Image file from clipboard processed, returning true from pasteHandler.',
            );
            return true; // Indicate paste was handled if an image file was processed
          }
        } else {
          console.log(
            '[BlockNoteEditorComponent] No files found on clipboard via event.clipboardData.files.',
          );
        }
      } else {
        console.log('[BlockNoteEditorComponent] event.clipboardData is null.');
      }

      const pastedText = event.clipboardData?.getData('text/plain');
      if (pastedText && isValidURL(pastedText)) {
        const isDirectImageExtension = IMAGE_URL_REGEX.test(pastedText);
        const isKnownImageDomain = pastedText.includes('gstatic.com/images');

        if (isDirectImageExtension || isKnownImageDomain) {
          console.log(
            '[BlockNoteEditorComponent] HTTP/HTTPS Image URL detected for import via handlePastedImageURL:',
            pastedText.substring(0, 100) + '...',
          );
          handlePastedImageURL(pastedText, currentEditor);
          return true;
        }
      }

      // New check for plain text data: URLs pasted directly
      if (
        pastedText &&
        pastedText.startsWith('data:image') &&
        pastedText.includes(';base64,')
      ) {
        console.log(
          '[BlockNoteEditorComponent] Plain text data: URL pasted, creating image block:',
          pastedText.substring(0, 100) + '...',
        );

        // Use insertOrUpdateBlock utility function, passing the editor as the first argument
        insertOrUpdateBlock(currentEditor, {
          type: 'image',
          props: { url: pastedText, caption: 'Pasted Image' },
        });
        return true; // We've handled this paste.
      }

      return defaultPasteHandler();
    },
    slashMenuItems: getDefaultSlashMenuItems,
  };

  const editor = useCreateBlockNote<
    typeof appSchema.blockSchema,
    typeof appSchema.inlineContentSchema,
    typeof appSchema.styleSchema
  >(editorOptions);

  useEffect(() => {
    if (editor) {
      onEditorChange(editor);
    }
  }, [editor, onEditorChange]);

  return (
    <Box borderWidth="1px" borderRadius="md" p={0} minH="300px">
      {editor ? (
        <BlockNoteView
          editor={editor}
          theme="light"
          editable={editable}
          onChange={() => {
            if (onContentUpdate && editor) {
              onContentUpdate(editor.topLevelBlocks);
            }
          }}
          slashMenu={true}
        />
      ) : (
        <Flex justify="center" align="center" height="100%" minH="200px">
          <Spinner />
          <Text ml={3}>Initializing Editor...</Text>
        </Flex>
      )}
    </Box>
  );
}
