import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Assuming authOptions are here
import prisma from '@/lib/prisma'; // Assuming prisma client is here
import { KnowledgeCard, Folder } from '@prisma/client'; // Import types for full card data

// Define the structure returned by the query, now including full card data + folder
// Note: Adjust based on fields actually needed by CardListItem
type SearchResultCard = KnowledgeCard & {
  folder: Pick<Folder, 'id' | 'name'> | null;
  _count?: { cards?: number }; // Assuming CardListItem doesn't need _count
  headline?: string; // Keep headline for potential use, though CardListItem won't use it directly
};

export async function GET(request: Request) {
  const session = await getServerSession(authOptions);

  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q');

  if (!query) {
    return NextResponse.json({ error: 'Search query (q) is required' }, { status: 400 });
  }

  const userId = session.user.id;

  console.log(`--- Searching ---`);
  console.log(`User ID: ${userId}`);
  console.log(`Raw Query Param (q): ${query}`);
  console.log(`-----------------`);

  try {
    // Query against the composite index (title + extracted content)
    // Select all relevant KnowledgeCard fields and included folder name
    // Use COALESCE for potentially null content
    const results = await prisma.$queryRawUnsafe<SearchResultCard[]>(`
      SELECT
        kc.id,
        kc.title,
        kc.content,
        kc."userId",
        kc."folderId",
        kc."createdAt",
        kc."updatedAt",
        kc."isStarred",
        -- Include folder name via a JOIN
        json_build_object('id', f.id, 'name', f.name) as folder,
        -- Calculate headline based on combined text for highlighting context
        ts_headline(
            'english',
            kc.title || ' ' || extract_card_text(COALESCE(kc.content, '[]'::jsonb)),
            websearch_to_tsquery('english', $1),
            'StartSel=*, StopSel=*, HighlightAll=TRUE, MaxFragments=1, FragmentDelimiter=..., MaxWords=30, MinWords=10' -- Adjust headline options
        ) as headline
      FROM "KnowledgeCard" kc
      LEFT JOIN "Folder" f ON kc."folderId" = f.id
      WHERE
        kc."userId" = $2 AND
        to_tsvector('english', kc.title || ' ' || extract_card_text(COALESCE(kc.content, '[]'::jsonb))) @@ websearch_to_tsquery('english', $1)
      ORDER BY
        ts_rank(to_tsvector('english', kc.title || ' ' || extract_card_text(COALESCE(kc.content, '[]'::jsonb))), websearch_to_tsquery('english', $1)) DESC
      LIMIT 20;
    `, query, userId);

    // Optional: If headline generation fails for some rows, it might be null.
    // Handle this if necessary, e.g., by providing a default snippet.

    return NextResponse.json(results);

  } catch (error) {
    console.error("Search API Error:", error);
    // Check for specific Prisma or DB errors if needed
    return NextResponse.json({ error: 'Failed to perform search' }, { status: 500 });
  }
} 