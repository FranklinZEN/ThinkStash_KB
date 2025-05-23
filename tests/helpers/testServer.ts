import next from 'next';
import { createServer, Server } from 'http';
import { AddressInfo } from 'net';
import path from 'path';

// Helper function to make it easier to get a free port
// Not strictly necessary if server.listen(0) works reliably, but can be useful.
// async function getFreePort(): Promise<number> {
//   return new Promise((res) => {
//     const srv = createServer();
//     srv.listen(0, () => {
//       const port = (srv.address() as AddressInfo).port;
//       srv.close(() => res(port));
//     });
//   });
// }

export interface TestServer {
  server: Server;
  url: string;
  app: ReturnType<typeof next>; // Expose Next.js app instance if needed
  close: () => Promise<void>;
}

export async function makeTestServer(): Promise<TestServer> {
  // Ensure APP_ENV is set for the Next.js instance we are about to create
  // This should ideally be picked up from the environment running the test (e.g., from .env.test or cross-env)
  // If Next.js app relies on process.env.APP_ENV, ensure it's set when tests run.
  // The 'conf' option can also be used to pass runtime config.
  const app = next({ 
    dev: true, // Changed from false to true
    dir: path.resolve(process.cwd()), // Assumes tests are run from project root, or adjust as needed (e.g., path.resolve(__dirname, '../..'))
    // quiet: true, // Suppress Next.js logs if desired
    conf: {
      // Runtime config passed to next.config.js
      // We need to ensure APP_ENV is seen by the Next app instance
      env: {
        ...process.env, // Pass existing env vars
        APP_ENV: 'test', // Explicitly set for this app instance
        NODE_ENV: 'development', // Next.js typically expects dev/prod for `next({ dev: ... })`
                               // but APP_ENV='test' is our custom flag.
                               // `dev: false` makes it behave more like production for builds.
      }
    }
  });

  await app.prepare();
  const handle = app.getRequestHandler();

  const httpServer = createServer((req, res) => {
    // You can add custom logic here before passing to Next.js if needed
    // For example, parsing URL differently or adding headers for all test requests
    return handle(req, res);
  });

  await new Promise<void>((resolve) => httpServer.listen(0, 'localhost', resolve)); // Listen on port 0 for a random available port

  const { port } = httpServer.address() as AddressInfo;
  const url = `http://localhost:${port}`;
  
  // console.log(`[makeTestServer] Test server listening on ${url}`); // Commented out for cleaner test output

  const close = async (): Promise<void> => {
    await new Promise<void>((resolve, reject) => {
      httpServer.close((err) => {
        if (err) {
          // console.error('[makeTestServer] Error closing server:', err); // Keep if errors are common
          return reject(err);
        }
        // console.log('[makeTestServer] Test server closed.');
        resolve();
      });
    });
  };

  return { server: httpServer, url, app, close };
} 