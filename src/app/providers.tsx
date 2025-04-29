'use client'

import { ChakraProvider } from '@chakra-ui/react'
import theme from '@/styles/theme'; // Import the custom theme
import { SessionProvider } from 'next-auth/react'; // Import SessionProvider

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    // Wrap with SessionProvider
    <SessionProvider>
      <ChakraProvider theme={theme}> {/* Pass the theme here */} 
        {children}
      </ChakraProvider>
    </SessionProvider>
  );
} 