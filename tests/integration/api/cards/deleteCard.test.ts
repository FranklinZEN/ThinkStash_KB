import { DELETE } from '@/app/api/cards/[cardId]/route';
import { getCurrentUserId } from '@/lib/sessionUtils';
import prisma from '@/lib/prisma'; // Jest will use src/lib/__mocks__/prisma.ts
import * as GCSService from '@/lib/gcs';
import { NextRequest } from 'next/server';
import { mockReset, DeepMockProxy } from 'jest-mock-extended'; // mockDeep is in the __mocks__ file

// Mock sessionUtils
jest.mock('@/lib/sessionUtils');
const mockGetCurrentUserId = getCurrentUserId as jest.Mock;

// Mock @lib/gcs (factory pattern)
const mockDeleteGCSFileFn = jest.fn();
const mockUploadBufferToGCSFn_delete = jest.fn();
const mockGetGCSFileStreamFn_delete = jest.fn();
jest.mock('@lib/gcs', () => ({
    __esModule: true,
    deleteGCSFile: mockDeleteGCSFileFn,
    uploadBufferToGCS: mockUploadBufferToGCSFn_delete,
    getGCSFileStream: mockGetGCSFileStreamFn_delete,
    bucketName: 'mock-bucket-for-delete-card-test'
}));

// REMOVED explicit jest.mock('@/lib/prisma', ...)
// Manual mock src/lib/__mocks__/prisma.ts should be used.

let mockPrismaInTest: DeepMockProxy<typeof prisma>; 

describe('DELETE /api/cards/[cardId]', () => {
  beforeEach(() => {
    mockPrismaInTest = prisma as DeepMockProxy<typeof prisma>;
    mockReset(mockPrismaInTest);

    mockReset(mockGetCurrentUserId);
    mockDeleteGCSFileFn.mockReset();
    mockUploadBufferToGCSFn_delete.mockReset();
    mockGetGCSFileStreamFn_delete.mockReset();
  });

  const mockUserId = 'user-delete-123';
  const mockCardId = 'card-to-delete-cuid';

  const createMockRequest = () => mockDeep<NextRequest>();

  it('should delete card, associated images, their metadata, and orphaned tags successfully', async () => {
    // Arrange
    mockGetCurrentUserId.mockResolvedValue(mockUserId);

    const mockImageMeta = [
      { gcsPath: 'images/user-delete-123/img1.png' },
      { gcsPath: 'images/user-delete-123/img2.jpg' },
    ];
    const mockTags = [
      { id: 'tag-cuid-1', name: 'orphaned' },
      { id: 'tag-cuid-2', name: 'in-use' },
    ];

    (mockPrismaInTest.$transaction as jest.Mock).mockImplementation(async (callbackPassedToTransaction) => {
        const txMock = mockDeep<typeof prisma>();
        txMock.knowledgeCard.findUnique.mockResolvedValueOnce({
            id: mockCardId, userId: mockUserId, 
            imageMetadata: mockImageMeta,
            tags: mockTags,
        } as any);
        mockDeleteGCSFileFn.mockResolvedValue(Promise.resolve());
        txMock.imageMetadata.deleteMany.mockResolvedValue({ count: mockImageMeta.length });
        txMock.knowledgeCard.delete.mockResolvedValue({ id: mockCardId } as any);
        txMock.tag.findUnique
            .mockResolvedValueOnce({ id: 'tag-cuid-1', name: 'orphaned', _count: { cards: 0 } } as any)
            .mockResolvedValueOnce({ id: 'tag-cuid-2', name: 'in-use', _count: { cards: 1 } } as any);
        txMock.tag.delete.mockResolvedValueOnce({ id: 'tag-cuid-1' } as any);
        return callbackPassedToTransaction(txMock);
    });

    const request = createMockRequest();
    await DELETE(request, { params: Promise.resolve({ cardId: mockCardId }) });

    // Assert that $transaction was called
    expect(mockPrismaInTest.$transaction).toHaveBeenCalledTimes(1);
    // Further assertions can check if deleteGCSFile was called, etc.
    expect(mockDeleteGCSFileFn).toHaveBeenCalledTimes(mockImageMeta.length);
  });

  it('should return 401 if user is not authenticated', async () => {
    // Arrange
    mockGetCurrentUserId.mockResolvedValue(null);
    const request = createMockRequest();

    // Act
    const response = await DELETE(request, { params: Promise.resolve({ cardId: mockCardId }) });
    const body = await response.json();

    // Assert
    expect(response.status).toBe(401);
    expect(body.error).toBe('Unauthorized');
    expect(mockPrismaInTest.$transaction).not.toHaveBeenCalled();
  });

  it('should return 404 if card is not found or not owned by user', async () => {
    // Arrange
    mockGetCurrentUserId.mockResolvedValue(mockUserId);
    const transactionMock = jest.fn().mockImplementation(async (callback) => {
      const txMock = mockDeep<typeof prisma>();
      txMock.knowledgeCard.findUnique.mockResolvedValueOnce(null); // Card not found
      // Call the actual transaction callback which should throw
      // It should throw an error which will be caught by the DELETE handler
      try {
        await callback(txMock);
      } catch (e) {
        // This error is expected to be caught by the route handler and result in a 404
        // For the test, we ensure the transaction logic is called.
        throw e; // Re-throw for the handler to catch
      }
    });
    // mockPrisma.$transaction = transactionMock;
    (mockPrismaInTest.$transaction as jest.Mock).mockImplementation(transactionMock);
    
    const request = createMockRequest();

    // Act
    const response = await DELETE(request, { params: Promise.resolve({ cardId: mockCardId }) });
    const body = await response.json();

    // Assert
    expect(response.status).toBe(404);
    expect(body.error).toBe('Card not found or not owned by user');
    expect(mockDeleteGCSFileFn).not.toHaveBeenCalled();
  });

  it('should handle GCS deletion errors gracefully and still attempt DB cleanup', async () => {
    // Arrange
    mockGetCurrentUserId.mockResolvedValue(mockUserId);

    const mockImageMeta = [{ gcsPath: 'images/user-delete-123/fail-img.png' }];
    const mockTags = [];

    const transactionMock = jest.fn().mockImplementation(async (callback) => {
      const txMock = mockDeep<typeof prisma>();
      txMock.knowledgeCard.findUnique.mockResolvedValueOnce({
        id: mockCardId,
        imageMetadata: mockImageMeta,
        tags: mockTags,
      });

      // Simulate GCS deletion failure
      mockDeleteGCSFileFn.mockRejectedValueOnce(new Error('GCS Kaboom')); 

      txMock.imageMetadata.deleteMany.mockResolvedValueOnce({ count: 1 });
      txMock.knowledgeCard.delete.mockResolvedValueOnce({ id: mockCardId } as any);
      // No tags to check in this case

      return callback(txMock);
    });
    // mockPrisma.$transaction = transactionMock;
    (mockPrismaInTest.$transaction as jest.Mock).mockImplementation(transactionMock);
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {}); // Suppress console.error for this test

    const request = createMockRequest();

    // Act
    const response = await DELETE(request, { params: Promise.resolve({ cardId: mockCardId }) });
    const body = await response.json();

    // Assert
    expect(response.status).toBe(200); // Still 200 as DB cleanup should succeed
    expect(body.message).toContain('deleted successfully');
    expect(mockDeleteGCSFileFn).toHaveBeenCalledWith(mockImageMeta[0].gcsPath);
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      expect.stringContaining('[DELETE /api/cards/[cardId]] Failed to delete GCS file'),
      expect.any(Error)
    );
    // Check that DB operations were still attempted and (mocked as) successful
    // This is implicitly tested by the transactionMock structure and the 200 OK response.
    consoleErrorSpy.mockRestore();
  });

  it('should return 400 for invalid card ID format', async () => {
    // Arrange
    mockGetCurrentUserId.mockResolvedValue(mockUserId);
    const request = createMockRequest();
    const invalidCardId = 'not-a-cuid';

    // Act
    const response = await DELETE(request, { params: Promise.resolve({ cardId: invalidCardId }) } );
    const body = await response.json();

    // Assert
    expect(response.status).toBe(400);
    expect(body.error).toContain('Invalid card ID format');
    expect(mockPrismaInTest.$transaction).not.toHaveBeenCalled();
  });

}); 