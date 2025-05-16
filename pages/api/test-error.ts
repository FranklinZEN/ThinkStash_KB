import { NextApiRequest, NextApiResponse } from 'next';
import { reportError } from '../../lib/errorReporting';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    // Simulate an error
    if (req.query.throw === 'true') {
      throw new Error('This is a test error from the Next.js API route! (TypeScript)');
    }
    res.status(200).json({ name: 'Test API without error (TypeScript)' });
  } catch (e: unknown) {
    let errorMessage = 'An unknown error occurred.';
    if (e instanceof Error) {
      errorMessage = e.message;
      reportError(e, { req });
    } else {
      reportError(String(e), { req });
    }

    // Respond to the client
    res.status(500).json({ 
      message: 'An internal server error occurred.',
      error: process.env.NODE_ENV === 'development' ? errorMessage : undefined,
    });
  }
} 