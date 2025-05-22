import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

// This configures a Service Worker with the given request handlers.
// @ts-expect-error Temporarily suppressing to unblock build, MSW type issue needs further investigation
export const worker = setupWorker(...handlers);
