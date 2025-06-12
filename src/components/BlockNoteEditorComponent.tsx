'use client';

import React, { useEffect } from 'react';
import { Box, Flex, Spinner, Text } from '@chakra-ui/react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
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
  };

  const editor: AppEditor | null = useCreateBlockNote<
    typeof appSchema.blockSchema,
    typeof appSchema.inlineContentSchema,
    typeof appSchema.styleSchema
  >(editorOptions) as AppEditor;

  useEffect(() => {
    if (typeof onEditorChange === 'function') {
      onEditorChange(editor);
    } else {
      console.warn('[BlockNoteEditorComponent] onEditorChange is not a function. Editor instance was:', editor);
    }
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
          // @ts-expect-error - Linter struggles with type inference here despite the typeof check
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
