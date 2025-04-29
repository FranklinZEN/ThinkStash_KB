import { extendTheme } from '@chakra-ui/react'

// Example theme customization - Refer to UI Style Guide (Section 4)
// for specific color palettes, fonts, spacing etc.
const theme = extendTheme({
  fonts: {
    heading: "var(--font-inter)", // Assuming Inter is set up in layout.tsx
    body: "var(--font-inter)",
  },
  colors: {
    // Example based on UI Style Guide (adjust as needed)
    brand: {
      900: '#1a365d',
      800: '#153e75',
      700: '#2a69ac',
    },
  },
  // Add other theme customizations here (spacing, components, etc.)
})

export default theme 