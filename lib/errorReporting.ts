import { ErrorReporting, ErrorReportingOptions, ServiceContext } from '@google-cloud/error-reporting';
import { NextApiRequest, NextApiResponse } from 'next'; // Import Next.js types

// Initialize the client.
// Ensure your GOOGLE_CLOUD_PROJECT environment variable is set,
// or the client will try to determine the project automatically.
// The service account for your Cloud Run service will be used for authentication.
let errorsClient: ErrorReporting | { report: (error: Error | string) => void };

const serviceContext: ServiceContext = {
  service: process.env.K_SERVICE || 'nextjs-backend', // K_SERVICE is automatically set in Cloud Run
  version: process.env.K_REVISION || 'unknown', // K_REVISION is automatically set in Cloud Run
};

if (process.env.NODE_ENV === 'production' || process.env.REPORT_ERRORS_DEV === 'true') {
  const options: ErrorReportingOptions = {
    serviceContext,
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
      // Constructing an httpRequest object helps Error Reporting link errors to requests
      const httpRequest: ErrorReportingHttpRequest = {
        method: context.req.method,
        url: context.req.url,
        userAgent: context.req.headers?.[ 'user-agent'],
        referrer: context.req.headers?.referer,
        remoteIp: context.req.headers?.[ 'x-forwarded-for'] || context.req.connection?.remoteAddress,
        // responseStatusCode: context.res?.statusCode // If you have access to response status
      };
      // The second argument to errorsClient.report can be an Express-like request object.
      // We are providing our structured httpRequest object.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (errorsClient as ErrorReporting).report(error, httpRequest as any); // Kept as any for now as library expects express.Request or similar
    } else {
      (errorsClient as ErrorReporting).report(error);
    }
  } else {
    console.error("Error reporting client not initialized or report method missing. Error:", error);
  }
} 