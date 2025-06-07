// tests/__helpers__/card-service-mock.ts
import { vi } from 'vitest';

// Singletons that every test imports and the handler will use
export const mockGetCardLogic = vi.fn();
export const mockUpdateCardLogic = vi.fn();
export const mockDeleteCardLogic = vi.fn();
export const mockHandleCardImageAssociations = vi.fn(); 