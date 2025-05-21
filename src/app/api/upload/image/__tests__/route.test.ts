// src/app/api/upload/image/__tests__/route.test.ts
/**
 * @jest-environment node
 */
import 'next-test-api-route-handler'; // ENSURE THIS IS THE VERY FIRST ACTUAL IMPORT
import { POST as appHandlerPOST } from '../route'; // Import your route handlers
import { getServerSession } from 'next-auth';
import { handleImageUploadLogic } from '@/lib/services/imageUploadService'; // ImageUploadInput is not directly used in this test file after rewrite
import { describe, it, expect, vi, beforeEach /*, afterEach */ } from 'vitest'; // Removed unused afterEach
import { createMocks /*, RequestMethod */ } from 'node-mocks-http'; // Removed unused RequestMethod
import { NextRequest } from 'next/server';

// Mock next-auth
vi.mock('next-auth', async (importOriginal) => {
  const actual = await importOriginal<typeof import('next-auth')>();
  return {
    ...actual,
    getServerSession: vi.fn(),
  };
});

// Mock the image upload service
vi.mock('@/lib/services/imageUploadService', () => ({
  handleImageUploadLogic: vi.fn(),
}));

const mockGetServerSession = getServerSession as ReturnType<typeof vi.fn>;
const mockHandleImageUploadLogic = handleImageUploadLogic as ReturnType<
  typeof vi.fn
>;

// Helper to create a mock File object
const createMockFile = (
  name: string,
  type: string,
  size: number,
  content: string = 'test',
): File => {
  const blob = new Blob([content], { type });
  // In Node.js for Vitest, File might not be globally available like in browser/jest-environment-jsdom.
  // If File is not defined, we might need a polyfill or a simpler mock for File.
  // For now, assuming Vitest/happy-dom provides it or tests won't break on this helper itself.
  if (typeof File === 'undefined') {
    // Basic mock if File is not available
    return {
      name,
      type,
      size,
      arrayBuffer: async () => new ArrayBuffer(0),
    } as File;
  }
  return new File([blob], name, { type });
};

// Helper for FormData requests
async function mockFormDataRequest(formDataInstance: FormData) {
  // For node-mocks-http, we might not directly pass FormData to body.
  // Instead, we mock the req.formData() method.
  const { req } = createMocks({
    method: 'POST',
    url: '/api/upload/image',
    // Headers for FormData are usually set by the client (e.g., multipart/form-data with boundary)
    // For this mock, we might not need to set it explicitly if the handler relies on req.formData()
  });

  const nextReq = req as unknown as NextRequest & {
    formData: () => Promise<FormData>;
  };
  nextReq.formData = async () => formDataInstance; // Mock the formData() method
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (nextReq as any).nextUrl = {
    searchParams: new URLSearchParams(),
    pathname: '/api/upload/image',
  };

  return nextReq;
}

describe('/api/upload/image POST', () => {
  beforeEach(() => {
    vi.resetAllMocks();
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
    expect(mockHandleImageUploadLogic).not.toHaveBeenCalled();
  });

  it('should return 400 if no file is provided', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'user-123' } });
    const formData = new FormData(); // Empty form data
    const req = await mockFormDataRequest(formData);
    const response = await appHandlerPOST(req);
    const json = await response.json();
    expect(response.status).toBe(400);
    expect(json.error).toBe('No file provided');
    expect(mockHandleImageUploadLogic).not.toHaveBeenCalled();
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
    const formData = new FormData();
    formData.append('file', mockFile);
    const req = await mockFormDataRequest(formData);
    const response = await appHandlerPOST(req);
    const json = await response.json();

    expect(mockHandleImageUploadLogic).toHaveBeenCalledWith(
      expect.objectContaining({
        userId,
        originalFilename: mockFile.name,
        contentType: mockFile.type,
        fileSize: mockFile.size,
        fileBuffer: expect.any(Buffer),
      }),
      expect.anything(), // For prismaInstance
    );
    expect(response.status).toBe(serviceResult.status);
    expect(json.success).toBe(true);
    expect(json.appServedUrl).toBe(serviceResult.appServedUrl);
    expect(json.imageRecordId).toBe(serviceResult.imageRecordId);
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
    const formData = new FormData();
    formData.append('file', mockFile);
    const req = await mockFormDataRequest(formData);
    const response = await appHandlerPOST(req);
    const json = await response.json();

    expect(mockHandleImageUploadLogic).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(serviceResult.status);
    expect(json.error).toBe(serviceResult.error);
    expect(json.details).toBe(serviceResult.details);
  });

  it('should return 500 if service logic throws an unexpected error', async () => {
    const userId = 'user-123';
    const mockFile = createMockFile('error-case.gif', 'image/gif', 100);
    mockGetServerSession.mockResolvedValue({ user: { id: userId } });
    mockHandleImageUploadLogic.mockImplementation(async () => {
      throw new Error('Unexpected service crash');
    });
    const formData = new FormData();
    formData.append('file', mockFile);
    const req = await mockFormDataRequest(formData);
    const response = await appHandlerPOST(req);
    const json = await response.json();

    expect(response.status).toBe(500);
    expect(json.error).toBe('Failed to process upload request.');
    expect(json.details).toBe('Unexpected service crash');
  });
});
