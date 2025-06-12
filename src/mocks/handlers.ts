import { http, HttpResponse } from 'msw';

export const handlers = [
  // Example: Mock NextAuth session endpoint
  http.get(
    '/api/auth/session',
    (
      {
        /* request */
      },
    ) => {
      // This logic can be enhanced to be controlled by individual tests
      // e.g., by setting a cookie or a global variable that this handler checks
      return HttpResponse.json({
        user: {
          id: 'mock-user-id',
          name: 'Mock User',
          email: 'test@example.com',
        },
        // Add other session properties your app might expect, like accessToken, expires, etc.
      });
    },
  ),

  // Add handlers for GCS if your app makes direct HTTP calls to it (unlikely if using Node.js SDK)
  // http.post('https://storage.googleapis.com/*', () => {
  //   console.log('MSW intercepted GCS call');
  //   return HttpResponse.json({ message: 'Mocked GCS response' });
  // })

  // Add more handlers here for other API endpoints your application calls
  // Example for a generic endpoint:
  // http.get('/api/some-data', () => {
  //   return HttpResponse.json({ key: 'mocked value' });
  // }),
];
