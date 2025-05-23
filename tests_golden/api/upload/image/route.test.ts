/**
 * @vitest-environment node
 */
// import 'next-test-api-route-handler'; // Evaluate if still needed, removed for now
import { POST as appHandlerPOST } from '../../../../src/app/api/upload/image/route'; // Corrected path
import { getServerSession } from 'next-auth';
// Service is no longer mocked: import { handleImageUploadLogic } from '@/lib/services/imageUploadService'; 
import {
    MOCK_USER_ID, // For setting up session
    mockImageRecordCreate, // For Prisma interactions in the service
    mockGCSUploadFile,    // For GCS interactions in the service
    mockImageRecordUpdate, // Added import
    // Import other Prisma/GCS mocks if imageUploadService uses them
} from '../../../../tests/helpers/apiTestSetup'; // Corrected path
import { describe, it, expect, vi, beforeEach } from 'vitest'; 
import { createMocks } from 'node-mocks-http';
import { NextRequest } from 'next/server';

// Mock next-auth
vi.mock('next-auth', async (importOriginal) => {
  const actual = await importOriginal<typeof import('next-auth')>();
  return {
    ...actual,
    getServerSession: vi.fn(),
  };
});

// Service is no longer mocked
// vi.mock('@/lib/services/imageUploadService', () => ({
//   handleImageUploadLogic: vi.fn(),
// }));

const mockGetServerSession = getServerSession as ReturnType<typeof vi.fn>;
// const mockHandleImageUploadLogic = handleImageUploadLogic as ReturnType<typeof vi.fn>; // Removed

// Helper to create a mock File object
const createMockFile = (
  name: string,
  type: string,
  size: number,
  content: string = 'test',
): File => {
  const blob = new Blob([content], { type });
  if (typeof File === 'undefined') {
    return {
      name,
      type,
      size,
      arrayBuffer: async () => Buffer.from(content).buffer,
      slice: vi.fn(),
      stream: vi.fn(),
      text: async () => content,
    } as unknown as File;
  }
  return new File([blob], name, { type });
};

// Helper for FormData requests
async function mockFormDataRequest(formDataInstance: FormData) {
  const { req } = createMocks({
    method: 'POST',
    url: '/api/upload/image',
  });

  const nextReq = req as unknown as NextRequest & {
    formData: () => Promise<FormData>;
  };
  nextReq.formData = async () => formDataInstance; 
  (nextReq as any).nextUrl = {
    searchParams: new URLSearchParams(),
    pathname: '/api/upload/image',
  };
  return nextReq;
}

describe('/api/upload/image POST', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    // Reset new mocks
    mockGetServerSession.mockReset();
    mockImageRecordCreate.mockReset();
    mockImageRecordUpdate.mockReset();
    mockGCSUploadFile.mockReset();
  });

  it('should return 401 if not authenticated', async () => {
    mockGetServerSession.mockResolvedValue(null);
    const formData = new FormData();
    formData.append('file', createMockFile('test.jpg', 'image/jpeg', 1024));
    const req = await mockFormDataRequest(formData);
    const response = await appHandlerPOST(req);
    const json = await response.json();
    expect(response.status).toBe(401);
    expect(json.error).toBe('Unauthorized');
    // expect(mockHandleImageUploadLogic).not.toHaveBeenCalled(); // Service not mocked anymore
  });

  it('should return 400 if no file is provided', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    const formData = new FormData(); // Empty form data
    const req = await mockFormDataRequest(formData);
    const response = await appHandlerPOST(req);
    const json = await response.json();
    expect(response.status).toBe(400);
    expect(json.error).toBe('No file provided'); // Corrected assertion
    // expect(mockHandleImageUploadLogic).not.toHaveBeenCalled();
  });

  // Further tests need to be heavily adapted to mock Prisma/GCS calls 
  // and assert based on service logic rather than just mocking the service outcome.

  // Example: Successful upload (simplified)
  it('should call Prisma and GCS on successful upload', async () => {
    const userId = MOCK_USER_ID;
    const mockFile = createMockFile('test.png', 'image/png', 512);
    mockGetServerSession.mockResolvedValue({ user: { id: userId } });

    const mockGcsResult = { filename: 'gcs-file.png', contentType: 'image/png', size: 512, url: 'gcs-url/gcs-file.png' };
    mockGCSUploadFile.mockResolvedValue(mockGcsResult);

    const simplifiedMockPrismaResult = { 
      id: 'fixed-test-id-12345', 
      userId: userId,
      gcsPath: mockGcsResult.filename,
      contentType: mockGcsResult.contentType,
      originalFilename: mockFile.name,
      size: mockFile.size,
      appServedUrl: 'initial-placeholder-url', 
      knowledgeCardId: null,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    mockImageRecordCreate.mockResolvedValue(simplifiedMockPrismaResult);

    // === Add mock for update ===
    const updatedAppServedUrl = `/api/images/serve/${simplifiedMockPrismaResult.id}`;
    const mockPrismaUpdateResult = { ...simplifiedMockPrismaResult, appServedUrl: updatedAppServedUrl };
    mockImageRecordUpdate.mockResolvedValue(mockPrismaUpdateResult);
    // === End add mock for update ===

    const formData = new FormData();
    formData.append('file', mockFile);
    const req = await mockFormDataRequest(formData);
    const response = await appHandlerPOST(req);
    const json = await response.json();

    expect(response.status).toBe(200); 
    expect(json.success).toBe(true);
    expect(json.imageRecordId).toBe(simplifiedMockPrismaResult.id);
    expect(json.appServedUrl).toBe(updatedAppServedUrl);
    expect(mockGCSUploadFile).toHaveBeenCalled();
    expect(mockImageRecordCreate).toHaveBeenCalled();
    expect(mockImageRecordUpdate).toHaveBeenCalled(); // Add assertion for update
  });

}); 