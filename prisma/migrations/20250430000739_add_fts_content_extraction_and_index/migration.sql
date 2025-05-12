-- This is an empty migration.

-- Drop the old title-only index first
DROP INDEX IF EXISTS knowledge_card_title_fts_idx;

-- Function to extract text from BlockNote-like JSON content
CREATE OR REPLACE FUNCTION extract_card_text(json_content jsonb) RETURNS text AS $$
DECLARE
    block jsonb;
    text_content text := '';
    inline_item jsonb;
BEGIN
    IF jsonb_typeof(json_content) != 'array' THEN
        RETURN ''; -- Return empty if not a JSON array
    END IF;

    FOR block IN SELECT * FROM jsonb_array_elements(json_content)
    LOOP
        -- Check if block is an object and has type and content fields
        IF jsonb_typeof(block) = 'object' AND block ? 'type' AND block ? 'content' THEN
            -- Extract text from paragraph or heading blocks
            IF block->>'type' IN ('paragraph', 'heading') THEN
                IF jsonb_typeof(block->'content') = 'array' THEN
                    -- Iterate through inline content items (text, links, etc.)
                    FOR inline_item IN SELECT * FROM jsonb_array_elements(block->'content')
                    LOOP
                        -- Extract text if it's a text block
                        IF jsonb_typeof(inline_item) = 'object' AND inline_item ? 'type' AND inline_item->>'type' = 'text' AND inline_item ? 'text' THEN
                           text_content := text_content || ' ' || (inline_item->>'text');
                        END IF;
                    END LOOP;
                END IF;
             -- Add other block types to extract from if needed (e.g., list items)
             -- ELSIF block->>'type' = 'listItem' THEN ...
            END IF;
        END IF;
    END LOOP;

    RETURN trim(text_content);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create a composite GIN index on title and extracted content
-- Use COALESCE to handle potentially NULL content fields gracefully
CREATE INDEX knowledge_card_title_content_fts_idx
ON "KnowledgeCard"
USING gin (
    to_tsvector('english', title || ' ' || extract_card_text(COALESCE(content, '[]'::jsonb)))
);