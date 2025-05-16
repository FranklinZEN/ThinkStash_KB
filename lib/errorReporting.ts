import { ErrorReporting } from '@google-cloud/error-reporting';
import { NextApiRequest, NextApiResponse } from 'next'; // Import Next.js types

// Initialize the client.
// Ensure your GOOGLE_CLOUD_PROJECT environment variable is set,
// or the client will try to determine the project automatically.
// The service account for your Cloud Run service will be used for authentication.
let errorsClient: ErrorReporting | { report: (error: Error | string) => void };

// Define the structure for serviceContext with known properties
const serviceContext: { service: string; version: string } = {
  service: process.env.K_SERVICE || 'nextjs-backend',
  version: process.env.K_REVISION || 'unknown',
};

if (process.env.NODE_ENV === 'production' || process.env.REPORT_ERRORS_DEV === 'true') {
  // Type of options will be inferred by the ErrorReporting constructor
  const options = {
    serviceContext,
    // reportUncaughtExceptions: true, // This is usually true by default
    // reportMode: 'always', // Can be useful during setup/testing even in dev
  };
  errorsClient = new ErrorReporting(options);
} else {
  // Fallback for local development if you don't want to report errors
  errorsClient = {
    report: (error: Error | string) => { // Type the error parameter
      console.error("Mock ErrorReport: ", error);
    }
  };
}

// This interface defines the structure expected by @google-cloud/error-reporting for the httpRequest context.
// It's a simplified version. The library can also accept an Express Request object.
interface ErrorReportingHttpRequest {
  method?: string;
  url?: string;
  userAgent?: string;
  referrer?: string;
  remoteIp?: string;
  responseStatusCode?: number;
}

interface ReportContext {
  req?: NextApiRequest; // Use NextApiRequest type
  res?: NextApiResponse; // Use NextApiResponse type
}

/**
 * Reports an error to Google Cloud Error Reporting.
 * @param {Error | string} error The error object or message to report.
 * @param {ReportContext} [context] Optional context, like httpRequest for associating with a request.
 */
export function reportError(error: Error | string, context?: ReportContext) {
  if (errorsClient && typeof (errorsClient as ErrorReporting).report === 'function') {
    if (context && context.req) {
      let clientIp: string | undefined;
      const xForwardedFor = context.req.headers?.[ 'x-forwarded-for'];
      if (Array.isArray(xForwardedFor)) {
        clientIp = xForwardedFor[0]; // Take the first IP if it's an array
      } else if (typeof xForwardedFor === 'string') {
        clientIp = xForwardedFor;
      }

      // Fallback to connection.remoteAddress if clientIp is still undefined
      if (!clientIp) {
        clientIp = context.req.connection?.remoteAddress;
      }

      const httpRequest: ErrorReportingHttpRequest = {
        method: context.req.method,
        url: context.req.url,
        userAgent: context.req.headers?.[ 'user-agent'],
        referrer: context.req.headers?.referer, // referrer header is often a single string
        remoteIp: clientIp,
      };
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (errorsClient as ErrorReporting).report(error, httpRequest as any); // Kept as any for now as library expects express.Request or similar
    } else {
      (errorsClient as ErrorReporting).report(error);
    }
  } else {
    console.error("Error reporting client not initialized or report method missing. Error:", error);
  }
} 