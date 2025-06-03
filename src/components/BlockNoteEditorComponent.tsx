'use client';

import React, { useEffect } from 'react';
import { Box, Flex, Spinner, Text } from '@chakra-ui/react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import {
  insertOrUpdateBlock,
} from '@blocknote/core';
import '@blocknote/mantine/style.css';

// Import the centralized schema and its derived types
import {
  appSchema,
  type AppEditor,
  type AppPartialBlock,
} from '@/lib/blocknote/appSchema';

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
  editor: AppEditor,
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
  editor: AppEditor,
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

// ADDED HELPER: Convert data URI to File object
async function dataUriToImageFile(dataUri: string, filenamePrefix = 'pasted_data_uri'): Promise<File | null> {
  try {
    const response = await fetch(dataUri);
    const blob = await response.blob();
    const extension = blob.type.split('/')[1] || 'png'; // Default to png if type is generic
    const filename = `${filenamePrefix}_${Date.now()}.${extension}`;
    return new File([blob], filename, { type: blob.type });
  } catch (error) {
    console.error('[BlockNoteEditorComponent] Error converting data URI to File:', error);
    return null;
  }
}

interface BlockNoteEditorComponentProps {
  onEditorChange: (editor: AppEditor | null) => void;
  onContentUpdate?: (documentState: AppPartialBlock[]) => void;
  editable?: boolean;
  initialContent?: AppPartialBlock[];
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
      editor: AppEditor;
      defaultPasteHandler: () => boolean;
    }) => {
      console.log(
        '%c[BlockNoteEditorComponent] PASTE EVENT DETECTED',
        'color: blue; font-weight: bold;',
      );

      if (!event.clipboardData) {
        return defaultPasteHandler();
      }

      // --- 1. Handle Direct File Pastes ---
      const pastedFiles = event.clipboardData.files;
      if (pastedFiles && pastedFiles.length > 0) {
        let imageFilePasted = false;
        for (const file of Array.from(pastedFiles)) {
          if (file.type.startsWith('image/')) {
            console.log(
              '[BlockNoteEditorComponent] Processing pasted image FILE via processPastedOrDroppedFile:',
              file.name,
            );
            event.preventDefault(); // Prevent default if we are handling an image file
            // Fire-and-forget: processPastedOrDroppedFile is async but we don't await it here.
            // It will insert the image into the editor when done.
            processPastedOrDroppedFile(file, currentEditor);
            imageFilePasted = true;
          }
        }
        if (imageFilePasted) {
          console.log('[BlockNoteEditorComponent] Direct image file paste initiated.');
          return true; // Indicate paste was handled (or initiated)
        }
      }

      // --- 2. Handle Pasted HTML for <img> tags with data: URIs ---
      const htmlContent = event.clipboardData.getData('text/html');
      let dataUriImagesFoundInHtml = false;
      if (htmlContent) {
        console.log('[BlockNoteEditorComponent] Checking pasted HTML content for data URI images...');
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = htmlContent;
        const imagesInHtml = Array.from(tempDiv.querySelectorAll('img'));

        for (const img of imagesInHtml) {
          const originalSrc = img.getAttribute('src');
          if (originalSrc && originalSrc.startsWith('data:image/')) {
            dataUriImagesFoundInHtml = true;
            event.preventDefault(); // Prevent default paste of original HTML if we process data URIs
            console.log('[BlockNoteEditorComponent] Found data URI image in HTML. Kicking off async upload...', originalSrc.substring(0,50) + '...');
            
            // Async IIFE to handle upload and insertion
            (async () => {
              const imageFile = await dataUriToImageFile(originalSrc);
              if (imageFile) {
                try {
                  const appServedUrl = await handleFileUpload(imageFile);
                  if (appServedUrl) {
                    console.log('[BlockNoteEditorComponent] Data URI image uploaded. Inserting new image block with URL:', appServedUrl);
                    currentEditor.insertBlocks([
                      { type: 'image', props: { url: appServedUrl, caption: imageFile.name } }
                    ], currentEditor.getTextCursorPosition().block, 'after');
                  } else {
                     console.warn('[BlockNoteEditorComponent] Upload of data URI successful but no appServedUrl returned.');
                  }
                } catch (uploadError) {
                  console.error('[BlockNoteEditorComponent] Failed to upload image from data URI:', uploadError);
                }
              }
            })(); // End of async IIFE
          }
        }
        
        if (dataUriImagesFoundInHtml) {
            console.log('[BlockNoteEditorComponent] data: URI image processing initiated from HTML paste.');
            // We already called preventDefault inside the loop if a data URI was found.
            // The original HTML (minus data URIs if they get replaced by this async process, or plus new blocks)
            // won't be pasted by default. This simple version doesn't try to re-paste the non-image parts of HTML.
            return true; // Indicate we've started handling it.
        }
      }

      // --- 3. Handle Pasted Plain Text for Image URLs ---
      // This should run only if direct files or data URIs in HTML weren't the primary content handled.
      if (!dataUriImagesFoundInHtml) { // Avoid processing plain text URL if it was part of an HTML data URI image.
        const pastedText = event.clipboardData.getData('text/plain');
        if (pastedText && isValidURL(pastedText) && IMAGE_URL_REGEX.test(pastedText)) {
            console.log(
                '[BlockNoteEditorComponent] Pasted text is a valid image URL, processing via handlePastedImageURL:',
                pastedText,
            );
            event.preventDefault(); // Prevent default paste of plain text
            // Fire-and-forget: handlePastedImageURL is async.
            handlePastedImageURL(pastedText, currentEditor);
            console.log('[BlockNoteEditorComponent] Plain text image URL paste initiated.');
            return true; // Indicate paste was handled (or initiated)
        }
      }

      // If none of the above custom handlers dealt with the paste, use BlockNote's default.
      console.log('[BlockNoteEditorComponent] No custom image handlers applied, falling back to defaultPasteHandler.');
      return defaultPasteHandler();
    },
  };

  // Ensure the type of editor from useCreateBlockNote matches AppEditor for consistency if needed elsewhere.
  const editor = useCreateBlockNote<typeof appSchema.blockSchema, typeof appSchema.inlineContentSchema, typeof appSchema.styleSchema>(editorOptions) as AppEditor;

  useEffect(() => {
    onEditorChange(editor); // Removed `as AppEditor | null` because `editor` is now typed as AppEditor.
  }, [editor, onEditorChange]);

  useEffect(() => {
    if (editor && onContentUpdate && editable) {
      // Define the event handler function within the useEffect scope
      const handleChange = () => {
        // The onContentUpdate captured by this useEffect closure
        if (onContentUpdate) { 
          onContentUpdate(editor.document as AppPartialBlock[]);
        }
      };

      const unsubscribe = editor.onEditorContentChange(handleChange);
      
      return () => {
        if (typeof unsubscribe === 'function') {
          // @ts-ignore - Linter struggles with type inference here despite the typeof check
          unsubscribe();
        }
      };
    }
  }, [editor, onContentUpdate, editable]);

  if (!editor) {
    return (
      <Flex justify="center" align="center" minH="300px">
        <Spinner />
        <Text ml={3}>Loading Editor Core...</Text>
      </Flex>
    );
  }

  return (
    <Box className="bn-container" data-color-mode="light" w="100%" h="100%">
      <BlockNoteView editor={editor} editable={editable} />
    </Box>
  );
}
