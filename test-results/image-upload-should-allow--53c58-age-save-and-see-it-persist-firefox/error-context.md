# Test info

- Name: should allow user to create card, upload image, save, and see it persist
- Location: E:\ThinkStash\e2e\image-upload.spec.ts:8:1

# Error details

```
Error: Timed out 5000ms waiting for expect(locator).toBeVisible()

Locator: getByRole('heading', { name: 'My Card with Image' })
Expected: visible
Received: <element(s) not found>
Call log:
  - expect.toBeVisible with timeout 5000ms
  - waiting for getByRole('heading', { name: 'My Card with Image' })

    at E:\ThinkStash\e2e\image-upload.spec.ts:48:75
```

# Page snapshot

```yaml
- banner:
  - link "ThinkStash":
    - /url: /
  - link "Welcome, Test PlayWright":
    - /url: /profile
    - paragraph: Welcome, Test PlayWright
  - button "Sign Out"
- complementary:
  - heading "Folders" [level=2]
  - button "Add Folder"
  - img
  - textbox "Search folders..."
  - button "Create new folder": Create Folder
  - paragraph: No folders created yet.
  - status
- heading "Create New Knowledge Card" [level=1]
- group:
  - text: Title
  - textbox "Title": My Card with Image
- group:
  - text: Key Words (Optional)
  - textbox "Key Words (Optional)"
- group:
  - text: Content
  - img "test-image.png"
  - paragraph: Enter text or type '/' for commands
- button "Create Card"
- status
- alert
- button "Open Next.js Dev Tools":
  - img
- region "Notifications-top"
- region "Notifications-top-left"
- region "Notifications-top-right"
- region "Notifications-bottom-left"
- region "Notifications-bottom":
  - status:
    - img
    - text: Card created successfully!
    - button "Close"
- region "Notifications-bottom-right"
```

# Test source

```ts
   1 | import { test, expect } from '@playwright/test';
   2 |
   3 | test.beforeEach(async ({ page }) => {
   4 |   // The global setup should handle login. We just need to navigate to the relevant page.
   5 |   await page.goto('/'); // Or the specific page where users create cards
   6 | });
   7 |
   8 | test('should allow user to create card, upload image, save, and see it persist', async ({ page }) => {
   9 |   await page.getByRole('button', { name: /New Card/i }).click(); // Adjust selector
  10 |   await page.getByRole('textbox', { name: /^Title$/i }).fill('My Card with Image'); // Changed selector
  11 |
  12 |   // Wait for the BlockNote editor to finish loading
  13 |   await expect(page.getByText('Loading Editor...')).not.toBeVisible({ timeout: 20000 });
  14 |
  15 |   // Focus the BlockNote editor - this selector might need adjustment
  16 |   // Common class for BlockNote's content editable area is often inside .bn-editor
  17 |   const editorLocator = page.locator('div[contenteditable="true"]'); 
  18 |   await editorLocator.click(); // Click to focus
  19 |
  20 |   // Type slash command to open menu
  21 |   await editorLocator.type('/');
  22 |
  23 |   // Wait for slash menu and click the "Image" item
  24 |   // Adjust the role and name if BlockNote renders it differently
  25 |   await page.getByRole('option', { name: /^Image/i }).click(); // Changed to target 'option' starting with 'Image'
  26 |
  27 |   // After selecting "Image" from slash command, BlockNote shows an "Upload image" button.
  28 |   // We need to click that button to trigger the file chooser.
  29 |   const uploadImageButton = page.getByRole('button', { name: 'Upload image' });
  30 |   await expect(uploadImageButton).toBeVisible(); // Ensure the button is visible
  31 |
  32 |   // Start waiting for the filechooser BEFORE clicking the button that opens it.
  33 |   const fileChooserPromise = page.waitForEvent('filechooser');
  34 |   
  35 |   // Click the "Upload image" button within the image block placeholder.
  36 |   await uploadImageButton.click();
  37 |
  38 |   // Now complete the file selection.
  39 |   const fileChooser = await fileChooserPromise;
  40 |   await fileChooser.setFiles('e2e/test-image.png'); // Ensure test image is available at this path
  41 |
  42 |   // Wait for image to appear in editor and verify its src attribute indicates it has been processed by the upload handler.
  43 |   await expect(page.getByRole('img', { name: /test-image\.png/i })).toHaveAttribute('src', /^\/api\/images\/serve\/.+/, { timeout: 15000 });
  44 |
  45 |   await page.getByRole('button', { name: /Create Card/i }).click(); // Match button text from snapshot
  46 |   
  47 |   // Instead of a generic success message, check if the card title is visible on the new page
> 48 |   await expect(page.getByRole('heading', { name: 'My Card with Image' })).toBeVisible(); 
     |                                                                           ^ Error: Timed out 5000ms waiting for expect(locator).toBeVisible()
  49 |
  50 |   // Reload or navigate to verify persistence
  51 |   await page.reload({ waitUntil: 'domcontentloaded' }); // Changed to domcontentloaded
  52 |
  53 |   // Wait for the main content (the persisted image) to be visible after reload.
  54 |   // This implicitly means loading of the card details (including the image) should be complete.
  55 |   await expect(page.getByRole('img', { name: 'BlockNote image' })).toBeVisible({ timeout: 30000 }); // Increased timeout for content
  56 |
  57 |   // As a secondary check, ensure the explicit loading message is also gone.
  58 |   await expect(page.getByText('Loading card details...')).not.toBeVisible({ timeout: 5000 }); // Shorter timeout, should be quick if image is loaded
  59 |
  60 |   // Add more specific assertions if possible
  61 |   // For example, check image dimensions, alt text, or other attributes if they are set and important.
  62 | }); 
```