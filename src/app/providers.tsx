'use client'

import { ChakraProvider } from '@chakra-ui/react'
import { MantineProvider } from '@mantine/core'; // Import MantineProvider
import theme from '@/styles/theme'; // Import the custom theme
import { SessionProvider } from 'next-auth/react'; // Import SessionProvider

// Optional: Create a basic Mantine theme or leave default
// import { createTheme as createMantineTheme } from '@mantine/core';
// const mantineTheme = createMantineTheme({});

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      {/* Swap order: ChakraProvider outside MantineProvider */}
      <ChakraProvider theme={theme}>
        <MantineProvider /* theme={mantineTheme} */ defaultColorScheme="light">
          {children}
        </MantineProvider>
      </ChakraProvider>
    </SessionProvider>
  );
} 