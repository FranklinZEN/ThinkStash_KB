'use client';

import React, { useEffect } from 'react';
import { Box, Flex, Spinner, Text } from '@chakra-ui/react';

// Import hook from react, but View component and styles from mantine
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/mantine"; // Import from mantine
import { BlockNoteEditor } from "@blocknote/core";
import "@blocknote/mantine/style.css"; // Import mantine styles

interface BlockNoteEditorComponentProps {
  onEditorChange: (editor: BlockNoteEditor | null) => void;
  editable?: boolean;
}

export default function BlockNoteEditorComponent({ onEditorChange, editable = false }: BlockNoteEditorComponentProps) {
  // Remove toast and UI component state
  // const toast = useToast();
  // const [BlockNoteUIComponent, setBlockNoteUIComponent] = useState<React.ComponentType<any> | null>(null);

  // Initialize editor instance using useCreateBlockNote
  const editor = useCreateBlockNote();

  // Effect to pass the editor instance up when it's ready
  useEffect(() => {
    if (editor) {
      onEditorChange(editor);
    }
  }, [editor, onEditorChange]);

  // Remove the useEffect hook for dynamic import
  // useEffect(() => { ... });

  // Render the mantine BlockNoteView component
  return (
    // The mantine component might not need the Chakra Box wrapper,
    // but let's keep it for now for layout consistency.
    // Removing padding as the mantine component likely handles its own.
    <Box borderWidth="1px" borderRadius="md" p={0} minH="300px">
      {editor ? (
        // Render BlockNoteView from @blocknote/mantine, pass editable prop
        <BlockNoteView editor={editor} theme="light" editable={editable} />
      ) : (
        <Flex justify="center" align="center" height="100%" minH="200px">
          <Spinner />
          <Text ml={3}>Initializing Editor...</Text>
        </Flex>
      )}
    </Box>
  );
} 