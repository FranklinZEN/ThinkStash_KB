import { add } from './exampleUtil';

describe('exampleUtil', () => {
  it('should add two numbers correctly', () => {
    expect(add(2, 3)).toBe(5);
    expect(add(-1, 1)).toBe(0);
    expect(add(0, 0)).toBe(0);
  });

  // Example placeholder for future async/DB test
  // it('should return user count (placeholder)', async () => {
  //   // Mock prisma client or use test DB setup
  //   // const count = await getUserCount(); 
  //   // expect(count).toBeGreaterThanOrEqual(0);
  // });
}); 