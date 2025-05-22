import { chromium, FullConfig } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url'; // Import for ES module path resolution

// Get the directory name of the current module
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables from .env file, now using the correctly defined __dirname
dotenv.config({ path: path.resolve(__dirname, '.env') });

async function globalSetup(config: FullConfig) {
  const { baseURL, storageState } = config.projects[0].use;
  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL });

  const testUserEmail = process.env.TEST_USER_EMAIL;
  const testUserPassword = process.env.TEST_USER_PASSWORD;

  if (!testUserEmail || !testUserPassword) {
    throw new Error(
      'TEST_USER_EMAIL and TEST_USER_PASSWORD environment variables must be set.'
    );
  }

  if (!baseURL) {
    throw new Error('baseURL is not defined in playwright.config.ts');
  }

  try {
    // 1. Go to the sign-in page (or any page to ensure cookies can be set for the domain)
    await page.goto('/auth/signin'); // Or your app's sign-in page path

    // 2. Get CSRF token
    // NextAuth.js often makes the CSRF token available via an API endpoint or embedded in the sign-in page.
    // We'll try fetching it from the common /api/auth/csrf endpoint.
    const csrfResponse = await page.request.get('/api/auth/csrf');
    if (!csrfResponse.ok()) {
      console.error('Failed to fetch CSRF token:', await csrfResponse.text());
      throw new Error(
        `Failed to fetch CSRF token: ${csrfResponse.status()} ${csrfResponse.statusText()}`
      );
    }
    const csrfJson = await csrfResponse.json();
    const csrfToken = csrfJson.csrfToken;
    if (!csrfToken) {
      throw new Error('CSRF token not found in response from /api/auth/csrf');
    }

    // 3. Perform sign-in using credentials provider
    const signInResponse = await page.request.post(
      '/api/auth/callback/credentials',
      {
        form: {
          email: testUserEmail,
          password: testUserPassword,
          csrfToken: csrfToken,
          json: 'true', // Often required by NextAuth
          redirect: 'false', // We don't want to follow redirects here
        },
        headers: {
          // Include necessary headers, e.g., content-type if not automatically set correctly by form
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    if (!signInResponse.ok()) {
      const errorBody = await signInResponse.text();
      console.error(
        'Sign-in API request failed:',
        signInResponse.status(),
        errorBody
      );
      // Check for specific error indicators from NextAuth if available
      if (errorBody.includes('CredentialsSignin')) {
        throw new Error(
          `Sign-in failed: Invalid credentials. Status: ${signInResponse.status()}`
        );
      }
      throw new Error(
        `Sign-in API request failed: ${signInResponse.status()} ${signInResponse.statusText()} - ${errorBody}`
      );
    }

    // Verify the response indicates successful login, e.g., by checking the URL or a specific part of the response body
    // NextAuth.js /api/auth/callback/credentials with redirect:false might return a specific JSON or just a 200 OK.
    // If it returns session data, you might want to verify that.
    // For now, a 200 OK is considered a success for this step.

    // 4. Save storage state (cookies, localStorage, etc.) to the file path defined in playwright.config.ts
    await page.context().storageState({ path: storageState as string });
    console.log(`Authentication state saved to ${storageState}`);
  } catch (error) {
    console.error('Error in globalSetup (authentication):', error);
    // Ensure browser is closed in case of an error during setup
    await browser.close();
    throw error; // Re-throw to fail the test run if auth setup fails
  }
  await browser.close();
}

export default globalSetup; 