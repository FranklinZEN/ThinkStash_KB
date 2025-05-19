// jest.polyfills.cjs (CommonJS)
console.log('*********** jest.polyfills.cjs (CJS): EXECUTING ***********');

// Polyfill TextEncoder/TextDecoder first
const { TextEncoder, TextDecoder } = require('util');
globalThis.TextEncoder = globalThis.TextEncoder || TextEncoder;
globalThis.TextDecoder = globalThis.TextDecoder || TextDecoder;
console.log(`jest.polyfills.cjs (CJS): TextEncoder is ${typeof globalThis.TextEncoder}, TextDecoder is ${typeof globalThis.TextDecoder}`);

// Attempt to use undici/register
try {
  require('undici/register'); // CommonJS require for side-effects
  console.log('jest.polyfills.cjs (CJS): Successfully ran undici/register.');
} catch (error) {
  console.error('jest.polyfills.cjs (CJS): Failed to run undici/register, falling back to manual assignment. Error:', error);
  try {
    const undici = require('undici');
    if (!globalThis.fetch) globalThis.fetch = undici.fetch;
    if (!globalThis.Request) globalThis.Request = undici.Request;
    if (!globalThis.Response) globalThis.Response = undici.Response;
    if (!globalThis.Headers) globalThis.Headers = undici.Headers;
    if (!globalThis.FormData) globalThis.FormData = undici.FormData;
    if (undici.ReadableStream && !globalThis.ReadableStream) {
      globalThis.ReadableStream = undici.ReadableStream;
    }
    console.log('jest.polyfills.cjs (CJS): Manually assigned undici globals.');
  } catch (e2) {
    console.error('jest.polyfills.js (CJS): Error during manual undici assignments. Details:', e2); // Typo in original log, keep for now
  }
}

console.log(`jest.polyfills.cjs (CJS): globalThis.Request is now ${typeof globalThis.Request}`);
console.log(`jest.polyfills.cjs (CJS): globalThis.Response is now ${typeof globalThis.Response}`);
console.log(`jest.polyfills.cjs (CJS): globalThis.fetch is now ${typeof globalThis.fetch}`);
console.log('*********** jest.polyfills.cjs (CJS): END OF EXECUTION ***********');