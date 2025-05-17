'use client';

import React, { useEffect, useState } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import {
  BlockNoteEditor as BlockNoteEditorType,
  PartialBlock,
} from '@blocknote/core';
import '@blocknote/mantine/style.css';
import { customSchema } from '@/lib/editor/blocks';

// Upload handler (copied from previous working version)
const handleFileUpload = async (file: File): Promise<string> => {
  console.log('BlockNote handleFileUpload - Selected file:', file.name);
  const formData = new FormData();
  formData.append('file', file);
  try {
    console.log(
      'BlockNote handleFileUpload - Attempting to upload to /api/upload/image...',
    );
    const response = await fetch('/api/upload/image', {
      method: 'POST',
      body: formData,
    });
    console.log(
      'BlockNote handleFileUpload - Upload response status:',
      response.status,
    );
    const responseBody = await response.text();
    console.log(
      'BlockNote handleFileUpload - Upload response body:',
      responseBody,
    );
    if (!response.ok) {
      let errorData;
      try {
        errorData = JSON.parse(responseBody);
      } catch {
        errorData = {
          message: `Upload failed with status ${response.status}. Response: ${responseBody}`,
        };
      }
      console.error('BlockNote handleFileUpload - Upload failed:', errorData);
      alert(`Failed to upload image: ${errorData.message || responseBody}`);
      throw new Error(`Upload failed: ${errorData.message || responseBody}`);
    }
    const data = JSON.parse(responseBody);
    console.log('BlockNote handleFileUpload - Upload successful, data:', data);
    if (!data.url) {
      console.error(
        'BlockNote handleFileUpload - Upload response missing URL:',
        data,
      );
      alert('Upload succeeded but the server did not return an image URL.');
      throw new Error('Upload response missing URL');
    }
    return data.url;
  } catch (error) {
    console.error(
      'BlockNote handleFileUpload - Error during image upload process:',
      error,
    );
    alert(
      `An unexpected error occurred during upload: ${error instanceof Error ? error.message : String(error)}`,
    );
    throw error;
  }
};

interface BlockNoteEditorProps {
  onChange?: (content: PartialBlock[]) => void;
  readOnly?: boolean;
  onEditorReady?: (editor: BlockNoteEditorType) => void;
  initialContent?: PartialBlock[];
}

export function BlockNoteEditor({
  onChange,
  readOnly = false,
  onEditorReady,
  initialContent,
}: BlockNoteEditorProps) {
  const [editable, setEditable] = useState(!readOnly);

  useEffect(() => {
    setEditable(!readOnly);
  }, [readOnly]);

  const editor = useCreateBlockNote({
    schema: customSchema,
    initialContent: initialContent,
    uploadFile: handleFileUpload,
  });

  useEffect(() => {
    if (editor && onEditorReady) {
      onEditorReady(editor);
    }
  }, [editor, onEditorReady]);

  if (!editor) {
    return <p>Loading editor...</p>;
  }

  return (
    <BlockNoteView
      editor={editor}
      theme="light"
      editable={editable}
      onChange={() => {
        if (onChange && editor) {
          onChange(editor.topLevelBlocks);
        }
      }}
      slashMenu={true}
    ></BlockNoteView>
  );
}
