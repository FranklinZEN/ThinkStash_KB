import React from 'react';
import { render, screen } from '@testing-library/react';
import ExampleComponent from '@/components/Example'; // Corrected ALIAS

describe('ExampleComponent', () => {
  // Basic test to check if the component renders
  it('renders example component heading', () => {
    render(<ExampleComponent />); 
    const headingElement = screen.getByRole('heading', { name: /Example Component/i });
    expect(headingElement).toBeInTheDocument();
  });
});