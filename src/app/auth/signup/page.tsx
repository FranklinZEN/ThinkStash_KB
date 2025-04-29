'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation'; // Use next/navigation for App Router
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  useToast,
  Text,
} from '@chakra-ui/react';

export default function SignUpPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const toast = useToast();
  const router = useRouter();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);

    try {
      const response = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password, name }),
      });

      const data = await response.json();

      if (response.ok) {
        toast({
          title: 'Account created.',
          description: "We've created your account for you.",
          status: 'success',
          duration: 5000,
          isClosable: true,
        });
        // Redirect to sign-in page after successful signup
        router.push('/api/auth/signin'); // Redirect using App Router's router
      } else {
        // Handle specific errors returned from the API
        toast({
          title: 'Sign up failed.',
          description: data.message || 'An error occurred during sign up.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error('Sign up fetch error:', error);
      toast({
        title: 'Sign up failed.',
        description: 'An unexpected error occurred. Please try again.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box maxW="md" mx="auto" mt={10} p={8} borderWidth={1} borderRadius="lg" boxShadow="lg">
      <VStack spacing={6} as="form" onSubmit={handleSubmit}>
        <Heading as="h1" size="lg" textAlign="center">
          Create Account
        </Heading>

        <FormControl isRequired>
          <FormLabel>Email address</FormLabel>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            isDisabled={isLoading}
          />
        </FormControl>

        <FormControl isRequired>
          <FormLabel>Password</FormLabel>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="********"
            isDisabled={isLoading}
          />
        </FormControl>

        <FormControl>
          <FormLabel>Name (Optional)</FormLabel>
          <Input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your Name"
            isDisabled={isLoading}
          />
        </FormControl>

        <Button
          type="submit"
          colorScheme="blue"
          width="full"
          isLoading={isLoading}
        >
          Sign Up
        </Button>

        <Text textAlign="center" pt={2}>
          Already have an account?{' '}
          <Button variant="link" colorScheme="blue" onClick={() => router.push('/api/auth/signin')}>
            Sign In
          </Button>
        </Text>
      </VStack>
    </Box>
  );
} 