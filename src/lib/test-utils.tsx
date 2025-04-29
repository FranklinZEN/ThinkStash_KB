import React, { ReactElement } from 'react';
import { render, RenderOptions, RenderResult } from '@testing-library/react';
import { ChakraProvider } from '@chakra-ui/react';
import theme from '@/styles/theme'; // Import your custom theme

// Define the AllTheProviders component
const AllTheProviders: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <ChakraProvider theme={theme}>
      {children}
    </ChakraProvider>
  );
};

// Create a custom render function
const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
): RenderResult => render(ui, { wrapper: AllTheProviders, ...options });

// Re-export everything from React Testing Library
export * from '@testing-library/react';

// Override the render method with our custom render
export { customRender as render }; 