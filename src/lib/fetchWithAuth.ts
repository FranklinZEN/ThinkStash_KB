import { getSession } from 'next-auth/react';

/**
 * A wrapper around the native fetch function that automatically adds
 * the Authorization header with the JWT access token if a session exists.
 *
 * @param url The URL to fetch.
 * @param options Optional fetch options (method, headers, body, etc.).
 * @returns A Promise resolving to the Response object.
 */
export async function fetchWithAuth(url: string | URL | Request, options: RequestInit = {}): Promise<Response> {
  const session = await getSession(); // Use getSession on the client-side

  const headers = new Headers(options.headers);

  // Add Authorization header if session and accessToken exist
  // Note: Adjust 'accessToken' if your session object uses a different property name
  if (session?.accessToken) {
    headers.set('Authorization', `Bearer ${session.accessToken}`);
  }

  // Ensure Content-Type is set for methods that typically have a body
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const mergedOptions: RequestInit = {
    ...options,
    headers,
  };

  return fetch(url, mergedOptions);
} 