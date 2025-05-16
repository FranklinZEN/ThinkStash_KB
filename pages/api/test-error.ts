import { NextApiRequest, NextApiResponse } from 'next';
import { reportError } from '../../lib/errorReporting';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // Temporary debugging for individual DB env vars
  console.log("!!!!!!!!!!!!!!!!! API ROUTE CHECK - DB_USER:", process.env.DB_USER);
  console.log("!!!!!!!!!!!!!!!!! API ROUTE CHECK - DB_PASSWORD:", process.env.DB_PASSWORD ? "Exists (not logging value)" : "MISSING or empty");
  console.log("!!!!!!!!!!!!!!!!! API ROUTE CHECK - DB_NAME:", process.env.DB_NAME);
  console.log("!!!!!!!!!!!!!!!!! API ROUTE CHECK - DB_HOST_PATH:", process.env.DB_HOST_PATH);

  if (req.query.deliberate_error === 'true') {
    console.error('[TEST-ERROR-ROUTE] Intentionally throwing error now...');
    try {
      throw new Error('Deliberate test error from /api/test-error for logging and reporting check');
    } catch (e: unknown) {
      console.error('[TEST-ERROR-ROUTE] Caught deliberate error:', e);
      if (e instanceof Error) {
        reportError(e, { req });
        console.error('[TEST-ERROR-ROUTE] Deliberate error reported via reportError utility.');
        res.status(500).json({ message: 'Deliberate test error occurred', error: e.message });
      } else {
        const errorMsg = String(e);
        reportError(errorMsg, { req });
        console.error('[TEST-ERROR-ROUTE] Deliberate non-Error object reported via reportError utility.');
        res.status(500).json({ message: 'Deliberate test error occurred (non-Error object)', error: errorMsg });
      }
      return; // Important to return after sending response
    }
  }

  // Original test-error functionality (if needed, or can be removed if confusing)
  try {
    if (req.query.throw === 'true') {
      console.error('[TEST-ERROR-ROUTE] Intentionally throwing (original throw=true) error now...');
      throw new Error('This is a test error from the Next.js API route! (TypeScript)');
    }
    res.status(200).json({ name: 'Test API without error (TypeScript)' });
  } catch (e: unknown) {
    console.error('[TEST-ERROR-ROUTE] Caught (original throw=true) error:', e);
    let errorMessage = 'An unknown error occurred.';
    if (e instanceof Error) {
      errorMessage = e.message;
      reportError(e, { req });
      console.error('[TEST-ERROR-ROUTE] (Original throw=true) error reported via reportError utility.');
    } else {
      const errorMsg = String(e);
      reportError(errorMsg, { req });
      console.error('[TEST-ERROR-ROUTE] (Original throw=true) non-Error object reported via reportError utility.');
    }
    res.status(500).json({
      message: 'An internal server error occurred.',
      error: process.env.NODE_ENV === 'development' ? errorMessage : undefined,
    });
  }
} 