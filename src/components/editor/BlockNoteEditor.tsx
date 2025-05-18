'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import {
  BlockNoteEditor as BlockNoteEditorCoreType,
  PartialBlock,
} from '@blocknote/core';
import '@blocknote/mantine/style.css';
import { customSchema, customBlockComponents } from '../../lib/editor/blocks';

import type { UploadApiResponse } from '@/app/api/upload/image/route';

// For direct inspection if needed
// import { ImageBlock as DirectlyImportedImageBlock } from '../../components/blocks/ImageBlock';

// Define what handleFileUpload returns for an image block
// It will now include data attributes for the final URLs
interface OptimisticImageBlockUploadResponse {
  type: 'image';
  props: {
    url: string;
    caption: string;
    alt?: string;
    'data-app-served-url': string;
    'data-gcs-path': string;
    contentType?: string;
  };
}

// Keep track of created object URLs globally for this editor instance
// This is not ideal if multiple editors are on the page, but simple for now.
// A better approach would be to manage this within the component's lifecycle using state/refs.
// We will use state within the component instead.

// Upload handler modified for optimistic updates
const createOptimisticHandleFileUpload = (
  addCreatedObjectUrl: (url: string) => void,
  onImageUploadStart?: () => void,
  onImageUploaded?: (blobUrl: string, metadata: UploadApiResponse) => void,
  onImageUploadError?: (error: Error) => void
) => async (
  file: File,
): Promise<OptimisticImageBlockUploadResponse> => {
  if (onImageUploadStart) {
    onImageUploadStart();
  }
  
  const objectUrl = URL.createObjectURL(file);
  addCreatedObjectUrl(objectUrl);

  const formData = new FormData();
  formData.append('file', file);
  try {
    const response = await fetch('/api/upload/image', {
      method: 'POST',
      body: formData,
    });
    const responseBody = await response.text();

    if (!response.ok) {
      let errorDetails = `Upload failed with status ${response.status}`;
      try {
        const errorData = JSON.parse(responseBody);
        errorDetails = errorData.details || errorData.error || errorData.message || responseBody;
      } catch {}
      console.error('[BlockNoteEditor.tsx] handleFileUpload - Upload failed:', errorDetails);
      URL.revokeObjectURL(objectUrl);
      const err = new Error(typeof errorDetails === 'string' ? errorDetails : JSON.stringify(errorDetails));
      if (onImageUploadError) {
        onImageUploadError(err);
      }
      alert(`Failed to upload image: ${errorDetails}`);
      throw err;
    }

    const apiResponseData: UploadApiResponse = JSON.parse(responseBody);

    if (!apiResponseData.appServedUrl || !apiResponseData.gcsPath || !apiResponseData.contentType || !apiResponseData.originalFilename) {
      console.error(
        '[BlockNoteEditor.tsx] handleFileUpload - Upload response missing crucial data:',
        apiResponseData,
      );
      URL.revokeObjectURL(objectUrl);
      const err = new Error('Upload succeeded but the server response was incomplete.');
      if (onImageUploadError) {
        onImageUploadError(err);
      }
      alert('Upload succeeded but the server response was incomplete.');
      throw err;
    }

    if (onImageUploaded) {
      onImageUploaded(objectUrl, apiResponseData);
    }

    return {
      type: 'image',
      props: {
        url: objectUrl,
        caption: apiResponseData.originalFilename,
        alt: apiResponseData.originalFilename,
        'data-app-served-url': apiResponseData.appServedUrl,
        'data-gcs-path': apiResponseData.gcsPath,
        contentType: apiResponseData.contentType,
      }
    };
  } catch (error) {
    console.error(
      '[BlockNoteEditor.tsx] handleFileUpload - Error during image upload process:',
      error,
    );
    const typedError = error instanceof Error ? error : new Error(String(error));
    if (onImageUploadError && !(error instanceof Error && error.message.startsWith("Failed to upload image:")) && !(error instanceof Error && error.message.startsWith("Upload succeeded but the server response was incomplete."))) {
      onImageUploadError(typedError);
    }
    if (!(error instanceof Error && (error.message.startsWith("Failed to upload image:") || error.message.startsWith("Upload succeeded but the server response was incomplete.")))) {
        alert(`An unexpected error occurred during upload: ${typedError.message}`);
    }
    throw typedError;
  }
};

interface BlockNoteEditorProps {
  onChange?: (content: PartialBlock<typeof customSchema>[]) => void;
  readOnly?: boolean;
  onEditorReady?: (editor: BlockNoteEditorCoreType<typeof customSchema>) => void;
  initialContent?: PartialBlock<typeof customSchema>[];
  onImageUploadStart?: () => void;
  onImageUploaded?: (blobUrl: string, metadata: UploadApiResponse) => void;
  onImageUploadError?: (error: Error) => void;
}

export default function BlockNoteEditor({
  onChange,
  readOnly = false,
  onEditorReady,
  initialContent,
  onImageUploadStart,
  onImageUploaded,
  onImageUploadError,
}: BlockNoteEditorProps) {
  const [editable, setEditable] = useState(!readOnly);
  const [createdObjectUrls, setCreatedObjectUrls] = useState<string[]>([]);

  const addCreatedObjectUrl = (url: string) => {
    setCreatedObjectUrls(prev => [...prev, url]);
  };
  
  useEffect(() => {
    return () => {
      createdObjectUrls.forEach(url => URL.revokeObjectURL(url));
    };
  }, [createdObjectUrls]);

  useEffect(() => {
    setEditable(!readOnly);
  }, [readOnly]);
  
  const handleFileUploadOptimistic = useMemo(
    () => createOptimisticHandleFileUpload(addCreatedObjectUrl, onImageUploadStart, onImageUploaded, onImageUploadError),
    [onImageUploadStart, onImageUploaded, onImageUploadError]
  );

  const editor: BlockNoteEditorCoreType<typeof customSchema> = useCreateBlockNote({ 
    schema: customSchema,
    initialContent: initialContent, 
    uploadFile: handleFileUploadOptimistic,
  });

  useEffect(() => {
    if (editor && onEditorReady) {
      onEditorReady(editor); 
    }
  }, [editor, onEditorReady]);

  if (!editor) { return <p>Loading editor...</p>; }

  // @ts-expect-error Known BlockNote type issue with BlockNoteView props, likely due to schema inference.
  return (
    <BlockNoteView
      editor={editor} 
      theme="light"
      editable={editable}
      blockComponents={customBlockComponents}
      onChange={() => {
        if (onChange && editor) {
          onChange(editor.topLevelBlocks as PartialBlock<typeof customSchema>[]); 
        }
      }}
      slashMenu={true}
    ></BlockNoteView>
  );
}
