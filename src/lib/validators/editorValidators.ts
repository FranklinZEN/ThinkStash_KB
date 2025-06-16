import { z } from 'zod';

// Zod schema for MyAppImageBlockProps from src/types/editorTypes.ts
// Matches the structure: { url: string, caption?: string }
export const MyAppImageBlockPropsSchema = z.object({
  url: z.string().url({ message: 'Image URL must be a valid URL.' }),
  caption: z.string().optional(),
  // width: z.number().optional(), // Not currently in MyAppImageBlockProps
  // height: z.number().optional(), // Not currently in MyAppImageBlockProps
  // alt: z.string().optional(), // Not currently in MyAppImageBlockProps, caption is used
});

// Base schema for inline content (text with marks)
const InlineContentSchema = z
  .object({
    type: z.string(), // e.g., 'text', 'link', etc.
    text: z.string().optional(), // Optional for non-text inline content like mentions
    styles: z.record(z.any()).optional(), // e.g., { bold: true }
    href: z.string().url().optional(), // For links
    // Add other inline content props as needed (e.g. for mentions, custom inline types)
  })
  .passthrough(); // Allow other properties for inline content

const BaseBlockPropsSchema = z.record(z.string(), z.any()).optional();

// Base Block Schema - common properties for all blocks
const BaseBlockSchema = z.object({
  id: z.string(),
  type: z.string(), // This will be narrowed by z.literal in specific block schemas
  props: BaseBlockPropsSchema,
  content: z
    .union([z.string(), z.array(InlineContentSchema), z.null()])
    .optional(),
  children: z.array(z.lazy(() => BlockSchema)).optional(),
});

// Specific Block Schemas
export const MyAppImageBlockSchema = BaseBlockSchema.extend({
  type: z.literal('image'),
  // For Pattern C, props from the client will be BlockNote's default "fat" props.
  // We make this permissive here; the service layer will narrow to MyAppImageBlockProps before saving.
  props: z.record(z.string(), z.any()).optional(), // Allows any properties for an image block from client
  content: z
    .literal('none')
    .or(z.array(z.object({})).max(0))
    .or(z.null())
    .optional(),
  children: z.array(z.object({})).max(0).optional(),
});

export const ParagraphBlockSchema = BaseBlockSchema.extend({
  type: z.literal('paragraph'),
  props: z
    .object({
      textAlignment: z.string().optional(),
      backgroundColor: z.string().optional(),
    })
    .passthrough()
    .optional(),
  content: z.array(InlineContentSchema).optional(),
});

export const HeadingBlockSchema = BaseBlockSchema.extend({
  type: z.literal('heading'),
  props: z
    .object({
      level: z
        .union([z.number().min(1).max(6), z.string().regex(/^[1-6]$/)])
        .transform((val) => String(val))
        .optional(), // Accept number or string '1'-'6', transform to string, keep optional
      textAlignment: z.string().optional(),
      backgroundColor: z.string().optional(),
    })
    .passthrough()
    .optional(),
  content: z.array(InlineContentSchema).optional(),
});

const ListItemContentSchema = z.array(InlineContentSchema).optional();

export const BulletListItemBlockSchema = BaseBlockSchema.extend({
  type: z.literal('bulletListItem'),
  props: z
    .object({
      textAlignment: z.string().optional(),
      backgroundColor: z.string().optional(),
    })
    .passthrough()
    .optional(),
  content: ListItemContentSchema,
  // Children are handled by the generic BaseBlockSchema's children field (recursive BlockSchema)
});

export const NumberedListItemBlockSchema = BaseBlockSchema.extend({
  type: z.literal('numberedListItem'),
  props: z
    .object({
      textAlignment: z.string().optional(),
      backgroundColor: z.string().optional(),
    })
    .passthrough()
    .optional(),
  content: ListItemContentSchema,
  // Children are handled by the generic BaseBlockSchema's children field
});

export const BlockquoteSchema = BaseBlockSchema.extend({
  type: z.literal('blockquote'),
  props: z
    .object({
      textAlignment: z.string().optional(),
      backgroundColor: z.string().optional(),
    })
    .passthrough()
    .optional(),
  content: z.array(InlineContentSchema).optional(), // Or can contain other blocks depending on strictness
});

export const CodeBlockSchema = BaseBlockSchema.extend({
  type: z.literal('codeBlock'),
  props: z
    .object({
      language: z.string().optional(),
      backgroundColor: z.string().optional(),
    })
    .passthrough()
    .optional(),
  content: z.string().optional(), // Typically a single string for code content
});

export const HorizontalRuleSchema = BaseBlockSchema.extend({
  type: z.literal('horizontalRule'),
  props: z
    .object({ backgroundColor: z.string().optional() })
    .passthrough()
    .optional(),
  content: z
    .literal('none')
    .or(z.array(z.object({})).max(0))
    .or(z.null())
    .optional(),
  children: z.array(z.object({})).max(0).optional(),
});

// Table related schemas (simplified)
export const TableCellSchema = BaseBlockSchema.extend({
  type: z.literal('tableCell'),
  props: z
    .object({
      backgroundColor: z.string().optional(),
      rowspan: z.number().optional(),
      colspan: z.number().optional(),
    })
    .passthrough()
    .optional(),
  content: z.array(InlineContentSchema).optional(), // Simplified: Can contain full blocks in BlockNote
});

export const TableRowSchema = BaseBlockSchema.extend({
  type: z.literal('tableRow'),
  props: z.object({}).passthrough().optional(),
  // Content of a row is an array of tableCell *blocks*, so it goes in children.
  content: z
    .literal('none')
    .or(z.array(z.object({})).max(0))
    .or(z.null())
    .optional(),
  children: z.array(TableCellSchema).optional(),
});

export const TableSchema = BaseBlockSchema.extend({
  type: z.literal('table'),
  props: z.object({}).passthrough().optional(),
  // Content of a table is an array of tableRow *blocks*, so it goes in children.
  content: z
    .literal('none')
    .or(z.array(z.object({})).max(0))
    .or(z.null())
    .optional(),
  children: z.array(TableRowSchema).optional(),
});

// Discriminated union for all known block types
export const BlockSchema: z.ZodTypeAny = z.discriminatedUnion('type', [
  ParagraphBlockSchema,
  MyAppImageBlockSchema,
  HeadingBlockSchema,
  BulletListItemBlockSchema,
  NumberedListItemBlockSchema,
  BlockquoteSchema,
  CodeBlockSchema,
  HorizontalRuleSchema,
  TableSchema,
  // IMPORTANT: Add TableRowSchema and TableCellSchema if they can appear at the top level of content.
  // For now, assuming they only appear nested within TableSchema.
  // If other custom blocks exist, or to allow any unhandled block types:
  // BaseBlockSchema.passthrough(), // Use with caution, bypasses strict type validation for unknown blocks
]);

// Zod schema for the overall card content (array of blocks)
export const CardContentSchema = z.array(BlockSchema);

// Zod schema for validating metadata of an uploaded file
export const UploadedFileMetadataSchema = z.object({
  name: z.string().min(1, { message: 'File name cannot be empty.' }),
  type: z.string().regex(/^image\/(jpeg|png|gif|webp)$/, {
    message: 'Invalid image type. Only JPEG, PNG, GIF, WEBP are allowed.',
  }),
  size: z
    .number()
    .max(5 * 1024 * 1024, { message: 'File size cannot exceed 5MB.' }),
});
