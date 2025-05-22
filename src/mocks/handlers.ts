import { http, HttpResponse, type RequestHandler } from 'msw';

export const handlers: RequestHandler[] = [
  // Simplest possible handler for diagnostics
  http.get('/api/ping', () => {
    return HttpResponse.text('pong');
  }),
];
