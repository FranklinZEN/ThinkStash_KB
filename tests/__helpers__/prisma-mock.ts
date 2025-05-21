// tests/__helpers__/prisma-mock.ts
import { vi } from 'vitest';

export const prismaMock = {
  folder: {
    findMany: vi.fn(),
    findUnique: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  knowledgeCard: {
    findUnique: vi.fn(),
    findMany: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    count: vi.fn(),
  },
  imageRecord: {
    findUnique: vi.fn(),
    findFirst: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    updateMany: vi.fn(),
    delete: vi.fn(),
  },
  tag: {
    findUnique: vi.fn(),
    create: vi.fn(),
  },
  $transaction: vi.fn(),
};

export const resetPrismaMock = () => {
  for (const modelKey in prismaMock) {
    const model = (prismaMock as any)[modelKey];
    if (typeof model === 'object' && model !== null) {
      for (const methodKey in model) {
        const method = (model as any)[methodKey];
        if (typeof method?.mockReset === 'function') {
          method.mockReset();
        }
      }
    } else if (typeof model?.mockReset === 'function') { 
      model.mockReset();
    }
  }
}; 