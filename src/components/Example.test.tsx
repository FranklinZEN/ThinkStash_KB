import React from 'react';
// import { render, screen } from '@testing-library/react'; // Default render
import { render, screen } from '@/lib/test-utils'; // Use custom render
import ExampleComponent from './Example';

// Basic test to check if the component renders
it('renders example component heading', () => {
  render(<ExampleComponent />); // Now uses the custom render with ChakraProvider
  const headingElement = screen.getByRole('heading', { name: /Example Component/i });
  expect(headingElement).toBeInTheDocument();
}); 