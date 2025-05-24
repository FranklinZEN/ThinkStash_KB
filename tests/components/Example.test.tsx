import React from 'react';
import { render, screen } from '@/lib/test-utils'; // Alias should still work
import ExampleComponent from '@/src/components/Example'; // ALIAS for component

// Basic test to check if the component renders
it('renders example component heading', () => {
  render(<ExampleComponent />); 
  const headingElement = screen.getByRole('heading', { name: /Example Component/i });
  expect(headingElement).toBeInTheDocument();
}); 