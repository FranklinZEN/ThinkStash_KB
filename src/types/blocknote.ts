export type Styles = {
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  strike?: boolean;
  textColor?: string;
  backgroundColor?: string;
};

export type StyledText = {
  type: 'text';
  text: string;
  styles: Styles;
};

export type Link = {
  type: 'link';
  content: StyledText[];
  href: string;
};

export type InlineContent = Link | StyledText;

export type TableContent = {
  type: 'tableContent';
  rows: {
    cells: InlineContent[][]; // Reverted to original definition
  }[];
};

export type KnownBlockType =
  | 'paragraph'
  | 'heading'
  | 'bulletListItem'
  | 'numberedListItem'
  | 'checkListItem'
  | 'table'
  | 'image'
  | 'file'
  | 'video'
  | 'audio'
  | 'notice'
  | 'codeBlock';

export type Block = {
  id: string;
  type: KnownBlockType | string;
  props: Record<string, boolean | number | string>;
  content: InlineContent[] | TableContent | undefined;
  children: Block[];
};

// The editor document is an array of Blocks
export type BlockNoteDocument = Block[];
