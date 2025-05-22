import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // The global setup should handle login. We just need to navigate to the relevant page.
  await page.goto('/'); // Or the specific page where users create cards
});

test('should allow user to create card, upload image, save, and see it persist', async ({ page }) => {
  await page.getByRole('button', { name: /New Card/i }).click(); // Adjust selector
  await page.getByRole('textbox', { name: /^Title$/i }).fill('My Card with Image'); // Changed selector

  // Wait for the BlockNote editor to finish loading
  await expect(page.getByText('Loading Editor...')).not.toBeVisible({ timeout: 20000 });

  // Focus the BlockNote editor - this selector might need adjustment
  // Common class for BlockNote's content editable area is often inside .bn-editor
  const editorLocator = page.locator('div[contenteditable="true"]'); 
  await editorLocator.click(); // Click to focus

  // Type slash command to open menu
  await editorLocator.type('/');

  // Wait for slash menu and click the "Image" item
  // Adjust the role and name if BlockNote renders it differently
  await page.getByRole('option', { name: /^Image/i }).click(); // Changed to target 'option' starting with 'Image'

  // After selecting "Image" from slash command, BlockNote shows an "Upload image" button.
  // We need to click that button to trigger the file chooser.
  const uploadImageButton = page.getByRole('button', { name: 'Upload image' });
  await expect(uploadImageButton).toBeVisible(); // Ensure the button is visible

  // Start waiting for the filechooser BEFORE clicking the button that opens it.
  const fileChooserPromise = page.waitForEvent('filechooser');
  
  // Click the "Upload image" button within the image block placeholder.
  await uploadImageButton.click();

  // Now complete the file selection.
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles('e2e/test-image.png'); // Ensure test image is available at this path

  // Wait for image to appear in editor and verify its src attribute indicates it has been processed by the upload handler.
  await expect(page.getByRole('img', { name: /test-image\.png/i })).toHaveAttribute('src', /^\/api\/images\/serve\/.+/, { timeout: 15000 });

  await page.getByRole('button', { name: /Create Card/i }).click(); // Match button text from snapshot
  
  // Instead of a generic success message, check if the card title is visible on the new page
  await expect(page.getByRole('heading', { name: 'My Card with Image' })).toBeVisible(); 

  // Reload or navigate to verify persistence
  await page.reload({ waitUntil: 'domcontentloaded' }); // Changed to domcontentloaded

  // Wait for the main content (the persisted image) to be visible after reload.
  // This implicitly means loading of the card details (including the image) should be complete.
  await expect(page.getByRole('img', { name: 'BlockNote image' })).toBeVisible({ timeout: 30000 }); // Increased timeout for content

  // As a secondary check, ensure the explicit loading message is also gone.
  await expect(page.getByText('Loading card details...')).not.toBeVisible({ timeout: 5000 }); // Shorter timeout, should be quick if image is loaded

  // Add more specific assertions if possible
  // For example, check image dimensions, alt text, or other attributes if they are set and important.
}); 