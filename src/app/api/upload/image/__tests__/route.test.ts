// src/app/api/upload/image/__tests__/route.test.ts
/**
 * @jest-environment node
 */
import 'next-test-api-route-handler'; // ENSURE THIS IS THE VERY FIRST ACTUAL IMPORT
import { testApiHandler } from 'next-test-api-route-handler';
import * as appHandler from '../route'; // Import your route handlers
import { getServerSession } from 'next-auth';
import { handleImageUploadLogic } from '@/lib/services/imageUploadService';

// Mock next-auth
jest.mock('next-auth', () => ({
  getServerSession: jest.fn(),
}));

// Mock the image upload service
jest.mock('@/lib/services/imageUploadService', () => ({
  handleImageUploadLogic: jest.fn(),
}));

const mockGetServerSession = getServerSession as jest.Mock;
const mockHandleImageUploadLogic = handleImageUploadLogic as jest.Mock;

// Helper to create a mock File object
const createMockFile = (
  name: string,
  type: string,
  size: number,
  content: string = 'test',
): File => {
  const blob = new Blob([content], { type });
  return new File([blob], name, { type });
};

describe('/api/upload/image POST (Route Handler with next-test-api-route-handler)', () => {
  beforeEach(() => {
    mockGetServerSession.mockReset();
    mockHandleImageUploadLogic.mockReset();
  });

  it('should return 401 if not authenticated', async () => {
    mockGetServerSession.mockResolvedValue(null);

    await testApiHandler({
      appHandler,
      test: async ({ fetch }) => {
        const formData = new FormData();
        formData.append('file', createMockFile('test.jpg', 'image/jpeg', 1024));

        const res = await fetch({ method: 'POST', body: formData });
        const json = await res.json();

        expect(res.status).toBe(401);
        expect(json.error).toBe('Unauthorized');
        expect(mockHandleImageUploadLogic).not.toHaveBeenCalled();
      },
    });
  });

  it('should return 400 if no file is provided', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'user-123' } });

    await testApiHandler({
      appHandler,
      test: async ({ fetch }) => {
        const formData = new FormData(); // Empty form data
        const res = await fetch({ method: 'POST', body: formData });
        const json = await res.json();

        expect(res.status).toBe(400);
        expect(json.error).toBe('No file provided');
        expect(mockHandleImageUploadLogic).not.toHaveBeenCalled();
      },
    });
  });

  it('should call handleImageUploadLogic and return its success response', async () => {
    const userId = 'user-123';
    const mockFile = createMockFile('test.png', 'image/png', 512);
    mockGetServerSession.mockResolvedValue({ user: { id: userId } });

    const serviceResult = {
      success: true,
      appServedUrl: '/api/images/serve/img-id-123',
      imageRecordId: 'img-id-123',
      status: 200,
    };
    mockHandleImageUploadLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler,
      test: async ({ fetch }) => {
        const formData = new FormData();
        formData.append('file', mockFile);

        const res = await fetch({ method: 'POST', body: formData });
        const json = await res.json();

        expect(mockHandleImageUploadLogic).toHaveBeenCalledWith(
          expect.objectContaining({
            userId,
            originalFilename: mockFile.name,
            contentType: mockFile.type,
            fileSize: mockFile.size,
            fileBuffer: expect.any(Buffer),
          }),
          expect.anything(),
        );
        expect(res.status).toBe(serviceResult.status);
        expect(json.success).toBe(true);
        expect(json.appServedUrl).toBe(serviceResult.appServedUrl);
        expect(json.imageRecordId).toBe(serviceResult.imageRecordId);
      },
    });
  });

  it('should call handleImageUploadLogic and return its error response', async () => {
    const userId = 'user-123';
    const mockFile = createMockFile('another.jpg', 'image/jpeg', 2048);
    mockGetServerSession.mockResolvedValue({ user: { id: userId } });

    const serviceResult = {
      success: false,
      error: 'Service failed',
      details: 'Service detail error',
      status: 500,
    };
    mockHandleImageUploadLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler,
      test: async ({ fetch }) => {
        const formData = new FormData();
        formData.append('file', mockFile);

        const res = await fetch({ method: 'POST', body: formData });
        const json = await res.json();

        expect(mockHandleImageUploadLogic).toHaveBeenCalledTimes(1);
        expect(res.status).toBe(serviceResult.status);
        expect(json.error).toBe(serviceResult.error);
        expect(json.details).toBe(serviceResult.details);
      },
    });
  });

  it('should return 500 if service logic throws an unexpected error', async () => {
    const userId = 'user-123';
    const mockFile = createMockFile('error-case.gif', 'image/gif', 100);
    mockGetServerSession.mockResolvedValue({ user: { id: userId } });
    mockHandleImageUploadLogic.mockRejectedValue(
      new Error('Unexpected service crash'),
    );

    await testApiHandler({
      appHandler,
      test: async ({ fetch }) => {
        const formData = new FormData();
        formData.append('file', mockFile);

        const res = await fetch({ method: 'POST', body: formData });
        const json = await res.json();

        expect(res.status).toBe(500);
        expect(json.error).toBe('Failed to process upload request.');
        expect(json.details).toBe('Unexpected service crash');
      },
    });
  });
});
