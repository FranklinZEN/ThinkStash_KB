// tests/__helpers__/card-service-mock.ts
import { jest } from '@jest/globals';

// Singletons that every test imports and the handler will use
export const mockGetCardLogic = jest.fn();
export const mockUpdateCardLogic = jest.fn();
export const mockDeleteCardLogic = jest.fn();
export const mockHandleCardImageAssociations = jest.fn(); 