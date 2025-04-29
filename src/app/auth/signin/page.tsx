'use client';

import { useState, FormEvent, useEffect } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter, useSearchParams } from 'next/navigation'; // Use next/navigation for App Router
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
  Alert,
  AlertIcon,
} from '@chakra-ui/react';

export default function SignInPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    // Check for error query parameter passed by NextAuth default error page
    const authError = searchParams?.get('error');
    if (authError) {
      // Map common NextAuth errors to user-friendly messages
      switch (authError) {
        case 'CredentialsSignin':
          setError('Invalid email or password. Please try again.');
          break;
        default:
          setError('An unexpected error occurred during sign in.');
          break;
      }
      // Clear the error query parameter from the URL without reloading
      router.replace('/auth/signin', { scroll: false });
    }
  }, [searchParams, router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setError(null); // Clear previous errors

    try {
      const result = await signIn('credentials', {
        redirect: false, // Handle redirect manually
        email: email,
        password: password,
      });

      if (result?.ok) {
        toast({
          title: 'Sign in successful.',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        // Redirect to dashboard or home page after successful sign in
        router.push('/'); // Redirect to home page
        router.refresh(); // Refresh server components
      } else {
        // Handle errors returned by the signIn function (e.g., from authorize callback)
        let errorMessage = 'Sign in failed. Please check your credentials.';
        if (result?.error) {
          // You might want to map specific error codes if your authorize function returns them
          console.error('SignIn Error Code:', result.error);
          // Use the error from URL params if available, otherwise generic message
          errorMessage = error || 'Invalid email or password.';
        }
        setError(errorMessage);
      }
    } catch (err) {
      console.error('Sign in fetch error:', err);
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box maxW="md" mx="auto" mt={10} p={8} borderWidth={1} borderRadius="lg" boxShadow="lg">
      <VStack spacing={6} as="form" onSubmit={handleSubmit}>
        <Heading as="h1" size="lg" textAlign="center">
          Sign In
        </Heading>

        {error && (
          <Alert status="error" borderRadius="md">
            <AlertIcon />
            {error}
          </Alert>
        )}

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

        <Button
          type="submit"
          colorScheme="blue"
          width="full"
          isLoading={isLoading}
        >
          Sign In
        </Button>

        <Text textAlign="center" pt={2}>
          Don't have an account?{' '}
          <Button variant="link" colorScheme="blue" onClick={() => router.push('/auth/signup')}>
            Sign Up
          </Button>
        </Text>
      </VStack>
    </Box>
  );
} 