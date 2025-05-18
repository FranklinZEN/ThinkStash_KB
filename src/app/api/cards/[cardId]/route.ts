import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import prisma from '@/lib/prisma'; // Your default prisma client instance
import { Prisma } from '@prisma/client'; // Import the Prisma namespace for types
import { z } from 'zod';
import { getCurrentUserId } from '@/lib/sessionUtils';
import { deleteGCSFile } from '@lib/gcs'; // Reverted to import deleteGCSFile directly
import { PartialBlock } from '@blocknote/core'; // Import PartialBlock
import { UploadApiResponse as _UploadApiResponse } from '@/app/api/upload/image/route'; // Import this type if not already

// interface RouteParams { // This interface will be removed
//   params: Promise<{ cardId: string }>;
// }

// Schema for validating route parameters
const RouteContextSchema = z.object({
  params: z.object({
    cardId: z.string().cuid({ message: 'Invalid card ID format' }),
  }),
});

// Schema for validating the update request body (PATCH/PUT)
// Allow partial updates: title, content, or folderId
const UpdateCardSchema = z
  .object({
    title: z
      .string()
      .min(1, { message: 'Title cannot be empty' })
      .trim()
      .optional(),
    content: z
      .array(z.any())
      .min(1, { message: 'Content cannot be empty' })
      .optional(), // Basic check for non-empty array
    folderId: z
      .string()
      .cuid({ message: 'Invalid folder ID format' })
      .optional()
      .nullable(), // Allow setting to null
    tags: z.array(z.string().trim()).optional(), // Added tags to schema, expect array of strings
    newImageMetadata: z.array(z.object({
      appServedUrl: z.string(),
      gcsPath: z.string(),
      contentType: z.string(),
      originalFilename: z.string(),
      size: z.number(),
      userId: z.string(), // Assuming client sends this from UploadApiResponse
    })).optional(),
  })
  .partial()
  .refine((data) => Object.keys(data).length > 0, {
    message:
      'At least one field (title, content, folderId, tags, newImageMetadata) must be provided for update',
  });

// --- GET Handler (Get Specific Card) ---
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  console.time('[GET /api/cards/[cardId]] Total Handler');
  console.time('[GET /api/cards/[cardId]] Session Check');
  const session = await getServerSession(authOptions);
  console.timeEnd('[GET /api/cards/[cardId]] Session Check');

  if (!session || !session.user?.id) {
    console.timeEnd('[GET /api/cards/[cardId]] Total Handler'); // End total timer early on auth failure
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const userId = session.user.id;

  console.time('[GET /api/cards/[cardId]] Resolve Params');
  const resolvedParams = await context.params;
  console.timeEnd('[GET /api/cards/[cardId]] Resolve Params');

  try {
    const cardId = resolvedParams.cardId;
    if (!cardId) {
      console.timeEnd('[GET /api/cards/[cardId]] Total Handler'); // End total timer early
      return NextResponse.json(
        { error: 'Card ID is required' },
        { status: 400 },
      );
    }

    console.time('[GET /api/cards/[cardId]] Prisma findUnique');
    const card = await prisma.knowledgeCard.findUnique({
      where: {
        id: cardId,
        userId: userId, // Ensure user owns the card
      },
      include: {
        folder: true, // Include full folder data if needed
        tags: true, // Include full tag data if needed
      },
    });
    console.timeEnd('[GET /api/cards/[cardId]] Prisma findUnique');

    if (!card) {
      console.timeEnd('[GET /api/cards/[cardId]] Total Handler'); // End total timer early
      return NextResponse.json(
        { error: 'Card not found or access denied' },
        { status: 404 },
      );
    }
    console.timeEnd('[GET /api/cards/[cardId]] Total Handler');
    return NextResponse.json(card);
  } catch (error) {
    console.error('Error fetching card:', error);
    console.timeEnd('[GET /api/cards/[cardId]] Total Handler'); // End total timer on error
    return NextResponse.json(
      { error: 'Failed to fetch card' },
      { status: 500 },
    );
  }
}

// --- PUT Handler (Update Specific Card) ---
export async function PUT(
  req: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  console.log('[PUT /api/cards/] Handler Entered');

  let resolvedParams;
  try {
    resolvedParams = await context.params;
  } catch (err) {
    console.error('Error awaiting context.params:', err);
    return NextResponse.json(
      { error: 'Failed to resolve route parameters' },
      { status: 500 },
    );
  }

  const contextValidation = RouteContextSchema.safeParse({
    params: resolvedParams,
  });
  if (!contextValidation.success) {
    console.error(
      'Route context validation failed (after await):',
      contextValidation.error.format(),
    );
    return NextResponse.json(
      { errors: contextValidation.error.format() },
      { status: 400 },
    );
  }
  const { cardId } = contextValidation.data.params;

  const userId = await getCurrentUserId();
  if (!userId) {
    console.error('User ID not found, returning 401');
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let validatedData: z.infer<typeof UpdateCardSchema>;
  let body;
  try {
    body = await req.json();
    const validationResult = UpdateCardSchema.safeParse(body);
    if (!validationResult.success) {
      console.error('Request body validation failed:', validationResult.error.format());
      return NextResponse.json({ errors: validationResult.error.format() }, { status: 400 });
    }
    validatedData = validationResult.data;
  } catch (error) {
    console.error('Error parsing request body:', error);
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  try {
    // Use a Prisma transaction to ensure atomicity for all operations
    const updatedCard = await prisma.$transaction(async (tx) => {
      const existingCardFromDB = await tx.knowledgeCard.findUnique({
        where: { id: cardId, userId: userId },
        include: { imageMetadata: { select: { gcsPath: true } } }, // Get current image GCS paths
      });

      if (!existingCardFromDB) {
        // This specific error message will be caught and handled below to return 404
        throw new Error('Card not found or not owned by user');
      }

      // --- Start: Image Deletion Logic for Update ---
      if (validatedData.content && existingCardFromDB.imageMetadata) {
        const currentGCSPathsInDB = new Set(existingCardFromDB.imageMetadata.map(meta => meta.gcsPath));
        const gcsPathsInNewContent = new Set<string>();

        // Helper to recursively find image URLs and extract GCS paths
        // Note: This assumes block.props.url is the app-served URL like /api/images/images/user/file.png
        // And gcsPath in DB is images/user/file.png
        function extractGCSPathsFromBlocks(blocks: PartialBlock[]): void {
          for (const block of blocks) {
            if (block.type === 'image' && block.props?.url && typeof block.props.url === 'string') {
              try {
                const urlPath = new URL(block.props.url, 'http://localhost').pathname;
                const gcsPathFromUrl = urlPath.startsWith('/api/images/') ? urlPath.substring('/api/images/'.length) : null;
                if (gcsPathFromUrl) {
                  gcsPathsInNewContent.add(gcsPathFromUrl);
                }
              } catch {
                // No need to use the error object, just log a warning
                console.warn('Malformed URL in image block:', block.props.url);
              }
            }
            // Check if children exist and is an array, then cast to PartialBlock[] for recursion
            if (block.children && Array.isArray(block.children)) {
              extractGCSPathsFromBlocks(block.children as PartialBlock[]);
            }
          }
        }

        if (Array.isArray(validatedData.content)) {
          extractGCSPathsFromBlocks(validatedData.content as PartialBlock[]);
        }

        const gcsPathsToDelete = [...currentGCSPathsInDB].filter(path => typeof path === 'string' && !gcsPathsInNewContent.has(path));

        if (gcsPathsToDelete.length > 0) {
          for (const gcsPath of gcsPathsToDelete) {
            if (typeof gcsPath === 'string') {
              try {
                await deleteGCSFile(gcsPath);
                await tx.imageMetadata.deleteMany({
                  where: { gcsPath: gcsPath, knowledgeCardId: cardId },
                });
              } catch (delError) {
                console.error(`[PUT /api/cards/${cardId}] Error deleting GCS file ${gcsPath} or its metadata:`, delError);
                // Optionally, collect errors and decide if transaction should roll back
              }
            }
          }
        }
      }
      // --- End: Image Deletion Logic for Update ---

      // --- ADD: Logic to create ImageMetadata for newly uploaded images --- 
      if (validatedData.newImageMetadata && validatedData.newImageMetadata.length > 0) {
        const newImageMetadataToCreate = validatedData.newImageMetadata.map(meta => ({
          knowledgeCardId: cardId, // Link to the current card
          userId: userId,          // Owner of the image is the current user
          gcsPath: meta.gcsPath,
          appServedUrl: meta.appServedUrl,
          contentType: meta.contentType,
          originalFilename: meta.originalFilename,
          size: meta.size,
        }));
        await tx.imageMetadata.createMany({
          data: newImageMetadataToCreate,
        });
      }
      // --- End New ImageMetadata Logic ---

      // Folder ownership check (can remain as is)
      if (
        validatedData.folderId !== undefined &&
        validatedData.folderId !== null
      ) {
        const targetFolder = await tx.folder.findUnique({
          where: { id: validatedData.folderId, userId: userId },
          select: { id: true },
        });
        if (!targetFolder) {
          // This error will also be caught by the generic catch block, 
          // but a specific message helps differentiate if needed.
          throw new Error('Target folder not found or not owned by user');
        }
      }

      const updateData: Prisma.KnowledgeCardUpdateInput = {};
      if (validatedData.title !== undefined) updateData.title = validatedData.title;
      if (validatedData.content !== undefined) updateData.content = validatedData.content as Prisma.InputJsonValue;

      if (validatedData.folderId !== undefined) {
        if (validatedData.folderId === null) {
          updateData.folder = { disconnect: true };
        } else {
          updateData.folder = { connect: { id: validatedData.folderId } };
        }
      }

      if (validatedData.tags !== undefined) {
        const uniqueTrimmedTags = validatedData.tags
          .map((tag) => tag.trim().toLowerCase()) // Ensure lowercase on update too
          .filter((tag) => tag.length > 0);
        updateData.tags = {
          set: [],
          connectOrCreate: uniqueTrimmedTags.map((tagName: string) => ({
            where: { name: tagName }, // Assumes tag names are unique and lowercase in DB
            create: { name: tagName },
          })),
        };
      }

      // Perform the actual card update
      const finalUpdatedCard = await tx.knowledgeCard.update({
        where: { id: cardId }, // userId check was done with existingCardFromDB
        data: updateData,
        include: { tags: true, folder: true, imageMetadata: true },
      });
      return finalUpdatedCard;
    }); // End of Prisma transaction

    return NextResponse.json(updatedCard);
  } catch (error: unknown) {
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2003') {
        return NextResponse.json(
          { error: 'Invalid related data (e.g., folder ID)' },
          { status: 400 },
        );
      }
    }

    console.error('Failed to update card:', error);
    // Ensure specific error messages thrown in transaction are handled
    if (error instanceof Error && error.message === 'Card not found or not owned by user') {
      return NextResponse.json({ error: error.message }, { status: 404 });
    }
    if (error instanceof Error && error.message === 'Target folder not found or not owned by user') {
      return NextResponse.json({ error: error.message }, { status: 400 });
    }
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}

// --- DELETE Handler (Delete Specific Card) ---
export async function DELETE(
  req: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  let resolvedParams;
  try {
    resolvedParams = await context.params;
  } catch (err) {
    console.error(
      '[DELETE /api/cards/[cardId]] Error awaiting route parameters:',
      err,
    );
    return NextResponse.json(
      { error: 'Failed to resolve route parameters' },
      { status: 500 },
    );
  }

  const paramsValidation = RouteContextSchema.safeParse({
    params: resolvedParams,
  });
  if (!paramsValidation.success) {
    console.error(
      '[DELETE /api/cards/[cardId]] Route parameter validation failed:',
      paramsValidation.error.format(),
    );
    return NextResponse.json(
      {
        error: 'Invalid card ID format in URL',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { cardId } = paramsValidation.data.params;

  const userId = await getCurrentUserId();
  if (!userId) {
    console.error(
      '[DELETE /api/cards/[cardId]] Unauthorized: No userId found from session.',
    );
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // Use a Prisma transaction to ensure atomicity for all delete operations
    await prisma.$transaction(async (tx) => {
      const existingCard = await tx.knowledgeCard.findUnique({
        where: { id: cardId, userId: userId },
        select: { 
          id: true, 
          imageMetadata: { select: { gcsPath: true } }, 
          tags: { select: { id: true, name: true } } // Select tag id and name for logging/checking
        }, 
      });

      if (!existingCard) {
        console.warn(
          `[DELETE /api/cards/[cardId]] Card not found or user does not own it. cardId: ${cardId}, userId: ${userId}`,
        );
        throw new Error('Card not found or not owned by user'); 
      }

      const tagsOfDeletedCard = existingCard.tags; // Store tags before card deletion

      // Delete associated GCS files
      if (existingCard.imageMetadata && existingCard.imageMetadata.length > 0) {
        for (const meta of existingCard.imageMetadata) {
          if (meta.gcsPath && typeof meta.gcsPath === 'string') {
            try {
              await deleteGCSFile(meta.gcsPath); // Call your GCS deletion function
            } catch (gcsError) {
              console.error(`[DELETE /api/cards/[cardId]] Failed to delete GCS file ${meta.gcsPath}:`, gcsError);
              // Decide on error handling: continue, or throw to rollback? 
              // For now, log and continue to ensure DB cleanup even if GCS fails for one file.
              // If GCS deletion is critical, you might throw here to rollback.
            }
          }
        }
        // Delete ImageMetadata records (cascade delete should handle this if schema is set up, but explicit is safer)
        await tx.imageMetadata.deleteMany({
          where: { knowledgeCardId: cardId },
        });
      }

      // Delete the KnowledgeCard
      await tx.knowledgeCard.delete({
        where: { id: cardId },
      });

      // After card is deleted, check and delete orphaned tags
      if (tagsOfDeletedCard && tagsOfDeletedCard.length > 0) {
        console.log(`[DELETE /api/cards/[cardId]] Checking ${tagsOfDeletedCard.length} tags for potential cleanup.`);
        for (const tagInfo of tagsOfDeletedCard) {
          const tagWithCount = await tx.tag.findUnique({
            where: { id: tagInfo.id },
            include: { _count: { select: { cards: true } } },
          });

          if (tagWithCount && tagWithCount._count.cards === 0) {
            console.log(`[DELETE /api/cards/[cardId]] Deleting orphaned tag: ID=${tagInfo.id}, Name=${tagInfo.name}`);
            await tx.tag.delete({ where: { id: tagInfo.id } });
          } else {
            // console.log(`[DELETE /api/cards/[cardId]] Tag ID=${tagInfo.id}, Name=${tagInfo.name} is still in use (Cards: ${tagWithCount?._count.cards}). Skipping deletion.`);
          }
        }
      }
    }); // End of Prisma transaction

    return NextResponse.json(
      { message: 'Card, associated images, and orphaned tags deleted successfully' }, // Updated message
      { status: 200 },
    );
  } catch (err: unknown) {
    console.error(
      `[DELETE /api/cards/[cardId]] Error during deletion process for cardId: ${cardId}:`,
      err,
    );
    // Handle the specific error thrown for card not found/owned
    if (err instanceof Error && err.message === 'Card not found or not owned by user') {
      return NextResponse.json({ error: err.message }, { status: 404 });
    }
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}
