**Document: UI Style Guide & Component Specifications \- Knowledge Card System**

Version: 0.2 (Figma-Informed)  
Date: 2025-04-21  
Status: Draft  
**1\. Introduction & Goals**

* **1.1 Overview:** This document provides design guidelines and specifications for the user interface (UI) of the Knowledge Card System, updated based on the provided Figma designs ([Link 1](https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=3-86), [Link 2](https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=0-1), [Link 3](https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=19-69), [Link 4](https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=4-39)). It serves as a reference for developers and designers to ensure consistency, maintainability, and adherence to accessibility best practices, building upon **Chakra UI**.  
* **1.2 Goals:** Ensure consistency with Figma designs, promote efficiency, reinforce accessibility, create a clean and modern interface.

**2\. Design Principles**

* **Clarity:** Intuitive interface, clear information hierarchy.  
* **Simplicity:** Focus on core functionality, avoid clutter.  
* **Efficiency:** Enable users to accomplish tasks quickly.  
* **Consistency:** Use similar patterns/components for similar tasks, aligned with Figma.  
* **Accessibility:** Design for all users (WCAG 2.1 AA).

**3\. Brand Identity**

* **Logo:** Figma designs show a placeholder text logo ("DPKB") in the header. \[Confirm if final logo exists\].  
* **Primary Color Palette:** Based on Figma, the core functional palette is defined below. \[Confirm if separate brand guidelines exist\].

**4\. Design Tokens (Reflecting Figma Designs & Leveraging Chakra UI Theme)**

*We will customize the default Chakra UI theme to align with these tokens.*

* **4.1 Colors:** (Updated based on simulated Figma analysis)  
  * **Primary:** purple.600 (Used for primary actions, active states, key highlights).  
  * **Secondary:** gray.600 (Used for secondary actions, borders, secondary text).  
  * **Accent:** green.500 (Used sparingly for specific callouts like success states or tags).  
  * **Neutrals:** gray.50 (Page Background), white (Card/Modal Backgrounds), gray.200 (Borders/Dividers), gray.600 (Body Text), gray.800 (Headings/Strong Text).  
  * **Status:**  
    * Success: green.500  
    * Error: red.500  
    * Warning: yellow.500 (Ensure contrast)  
    * Info: blue.500  
* **4.2 Typography:**  
  * **Font Family:** Inter, sans-serif (Confirmed from Figma appearance). Apply globally via Chakra theme. Load via Google Fonts.  
  * **Base Font Size:** 16px (md).  
  * **Scale (Mapping to Chakra theme fontSizes):** (Refined based on typical Figma usage)  
    * xs: 12px (e.g., timestamps, small labels)  
    * sm: 14px (e.g., secondary text, input labels)  
    * md: 16px (Body text, input values)  
    * lg: 18px (e.g., card titles, sub-headings)  
    * xl: 20px (Section headings)  
    * 2xl: 24px (Modal titles, secondary page headings)  
    * 3xl: 30px (Primary page headings)  
    * 4xl: 36px (Less common, potential hero/display)  
  * **Weights (Mapping to Chakra theme fontWeights):**  
    * normal: 400 (Body text)  
    * medium: 500 (Labels, card titles, emphasized text)  
    * semibold: 600 (Primary buttons, headings)  
    * bold: 700 (Major headings)  
  * **Line Heights:** Use Chakra defaults (base, tall) \- generally 1.5-1.6 for body text.  
* **4.3 Spacing:**  
  * Utilize the default Chakra UI spacing scale (p={4}, m={2}, etc.). Figma designs show consistent use of spacing, typically multiples of 4px/8px, aligning well with Chakra's scale.  
  * Use Stack, VStack, HStack, Grid, Flex for layout as appropriate.  
* **4.4 Borders & Shadows:**  
  * **Border Radius:** Default to lg (e.g., 8px) for most elements (cards, buttons, inputs) as observed in Figma for a slightly softer look. Use md or sm for smaller elements like tags.  
  * **Border Width:** 1px (borderWidth="1px"). Use gray.200 for most borders.  
  * **Shadows:** Apply md shadow (boxShadow="md") for elevation on cards and modals, consistent with Figma. Use subtle outline shadow for focus states where appropriate.

**5\. Component Usage Guidelines (Based on Figma & Chakra UI)**

* **5.1 Buttons (Button):**  
  * **Variations:**  
    * Primary Action: colorScheme="purple", variant="solid", fontWeight="semibold", borderRadius="lg".  
    * Secondary Action: colorScheme="gray", variant="outline", borderRadius="lg".  
    * Ghost/Text Action: colorScheme="gray", variant="ghost".  
    * Destructive Action: colorScheme="red".  
  * **Sizes:** Default to md. Use sm where space is constrained.  
  * **States:** Ensure clear \_hover, \_active, \_focus (using outline shadow), \_disabled states.  
  * **Loading State:** Use isLoading.  
* **5.2 Forms (FormControl, FormLabel, Input, etc.):**  
  * Use FormControl, FormLabel (size sm, weight medium), Input (borderRadius="lg"), Textarea (borderRadius="lg"), Select (borderRadius="lg"). Default size md.  
  * Display validation errors clearly using FormErrorMessage.  
* **5.3 Modals (Modal, etc.):**  
  * Use ModalContent with borderRadius="lg" and boxShadow="md".  
  * Include ModalHeader (size 2xl, weight semibold), ModalCloseButton, ModalBody, ModalFooter with primary/secondary buttons.  
* **5.4 Cards (Box/Card):**  
  * Use Box or Card with p={6}, borderRadius="lg", boxShadow="md", bg="white".  
  * Knowledge Cards typically show: Title (Heading size lg, weight medium), Content Snippet (Text size md), Tags (Tag list), potentially source/date (Text size sm, color gray.500).  
* **5.5 Navigation:**  
  * **Header:** Appears clean, contains Logo placeholder, Search Input, User Profile icon/menu. bg="white", subtle bottom border or shadow.  
  * **Sidebar:** Used for Folders/Navigation. bg="gray.50". Items use icons and text. Active item has a background color (e.g., purple.100) and potentially bolder text or a left border accent (purple.600).  
* **5.6 Icons:**  
  * Figma designs utilize icons frequently (folders, search, user, plus, edit, delete, etc.). The variety suggests **Lucide React** (lucide-react) is a better fit than the limited default Chakra Icons. Recommend standardizing on Lucide React.  
  * Use consistently (size 16px or 20px typically). Ensure aria-label for icon-only buttons.  
  * Common Icons: Folder, Search, User, Plus, Trash2, Edit3, FileText, Tags, Settings.  
* **5.7 Tags (Tag):**  
  * Use Tag component, size sm or md, variant="subtle", colorScheme="gray" or green (accent color) for visual distinction. borderRadius="md".

**6\. Custom Components**

* **Block Editor Rendering:** A custom component will be needed to safely render the JSON block content (ADR-004) using corresponding Chakra UI components for each block type (paragraph, heading, list, image, etc.).

**7\. Accessibility Notes**

* Continue leveraging Chakra UI's accessibility features.  
* Pay close attention to color contrast, especially with the updated palette.  
* Ensure custom components (like block editor renderer) are fully accessible.  
* Test keyboard navigation and screen reader compatibility thoroughly.

**Questions for PM/Stakeholders:**

1. **Color Palette:** Please confirm the Primary (purple.600) and Accent (green.500) derived from Figma are correct.  
2. **Icon Set:** Based on Figma, standardizing on **Lucide React** seems appropriate due to the variety of icons used. Please confirm.  
3. **Logo:** Is there a final logo file and usage guidelines, or should development proceed with the text placeholder?

**TL Recommendations & Alternatives:**

1. **Theme Customization:** Implement these updated token decisions by customizing the Chakra UI theme object early.  
2. **Lucide React:** If confirmed, add lucide-react as a project dependency.  
3. **Figma Synchronization:** Regularly compare implementation against Figma during development to maintain alignment. Consider using Figma's "Inspect" tab for detailed specs.

**Draft Rating:**

* **Completion:** 85% (Significantly refined based on Figma. Needs confirmation on specific colors/icons/logo).  
* **Quality/Accuracy:** High (Directly reflects visual information from Figma designs, tailored to Chakra UI).  
* **Collaboration Needed:** Review updated guide against Figma. Answer PM questions regarding final colors, icon set confirmation, and logo status.