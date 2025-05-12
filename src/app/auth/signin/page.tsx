'use client';

import { useState, FormEvent, useEffect, Suspense } from 'react';
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
  Flex,
  InputGroup,
  InputRightElement,
  Icon,
} from '@chakra-ui/react';
import { ViewIcon, ViewOffIcon } from '@chakra-ui/icons';

// Renamed original component to SignInForm
function SignInForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
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
        router.push('/');
        router.refresh();
      } else {
        // Enhanced error handling
        let displayErrorMessage =
          'Sign in failed. Please check your credentials.'; // Default message
        if (result?.error) {
          console.error('NextAuth SignIn Error:', result.error); // Log the raw error for debugging
          if (result.error === 'CredentialsSignin') {
            displayErrorMessage =
              'Invalid email or password. Please try again.';
          } else if (
            typeof result.error === 'string' &&
            result.error.length > 0
          ) {
            // Use the error message if it's a non-empty string (could be from authorize callback)
            displayErrorMessage = result.error;
          } else {
            // Fallback for other or non-string errors
            displayErrorMessage =
              'An unexpected error occurred during sign in. Please try again later.';
          }
        }
        setError(displayErrorMessage);
      }
    } catch (err) {
      console.error('Sign in fetch error:', err);
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Flex
      direction="column"
      alignItems="center"
      justifyContent="center"
      minHeight="800px"
      bg="#F5F5F5"
      width="100%"
      py="20px"
    >
      <Flex
        direction="column"
        width={{ base: '100%', md: '1280px' }}
        px={{ base: '20px', md: '160px' }}
        py="20px"
      >
        <form onSubmit={handleSubmit}>
          <VStack
            spacing={{ base: '16px', md: '20px' }}
            width={{ base: '100%', md: '960px' }}
            maxWidth="960px"
            mx="auto"
            bg="#FFFFFF"
            py={{ base: '20px', md: '40px' }}
            px={{ base: '15px', md: '20px' }}
            align="stretch"
            borderRadius="md"
            boxShadow="lg"
          >
            <Flex
              direction="column"
              alignItems="center"
              py={{ base: '16px', md: '24px' }}
              px={{ base: '12px', md: '16px' }}
              mb="10px"
            >
              <Heading
                as="h1"
                fontFamily="'Pacifico', cursive"
                fontWeight="bold"
                fontSize={{ base: '40px', md: '48px' }}
                lineHeight={{ base: '1.2', md: '1.2' }}
                textAlign="center"
                color="#141414"
              >
                Log In
              </Heading>
            </Flex>

            {error && (
              <Flex justifyContent="center" width="100%">
                <Alert
                  status="error"
                  borderRadius="md"
                  mb="10px"
                  maxWidth={{ base: 'calc(100% - 32px)', md: '480px' }}
                  mx="auto"
                >
                  <AlertIcon />
                  {error}
                </Alert>
              </Flex>
            )}

            <Flex justifyContent="center" width="100%">
              <FormControl
                isRequired
                width={{ base: '100%', md: '480px' }}
                maxWidth="480px"
              >
                <FormLabel
                  fontFamily="'Open Sans', sans-serif"
                  fontWeight="500"
                  fontSize="24px"
                  lineHeight="24px"
                  color="#141414"
                  mb="8px"
                >
                  Email
                </FormLabel>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email address"
                  isDisabled={isLoading}
                  height="56px"
                  bg="#F5F5F5"
                  border="1px solid #D9D9D9"
                  borderRadius="8px"
                  paddingX="15px"
                  fontFamily="'Open Sans', sans-serif"
                  fontSize="14px"
                  lineHeight="24px"
                  color="#A1824A"
                  _placeholder={{ color: '#A1824A' }}
                />
              </FormControl>
            </Flex>

            <Flex justifyContent="center" width="100%">
              <FormControl
                isRequired
                width={{ base: '100%', md: '480px' }}
                maxWidth="480px"
              >
                <FormLabel
                  fontFamily="'Open Sans', sans-serif"
                  fontWeight="500"
                  fontSize="24px"
                  lineHeight="24px"
                  color="#141414"
                  mb="8px"
                >
                  Password
                </FormLabel>
                <InputGroup size="md">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    isDisabled={isLoading}
                    height="56px"
                    bg="#F5F5F5"
                    border="1px solid #D9D9D9"
                    borderTopLeftRadius="8px"
                    borderBottomLeftRadius="8px"
                    borderRightWidth={{ base: '1px', md: '0px' }}
                    paddingX="15px"
                    fontFamily="'Open Sans', sans-serif"
                    fontSize="14px"
                    lineHeight="24px"
                    color="#A1824A"
                    _placeholder={{ color: '#A1824A' }}
                  />
                  <InputRightElement
                    width="40px"
                    height="56px"
                    bg="#F5F5F5"
                    border="1px solid #D9D9D9"
                    borderLeftWidth={{ base: '1px', md: '0px' }}
                    borderTopRightRadius="8px"
                    borderBottomRightRadius="8px"
                    onClick={() => setShowPassword(!showPassword)}
                    cursor="pointer"
                  >
                    <Icon
                      as={showPassword ? ViewOffIcon : ViewIcon}
                      color="#707070"
                      w="24px"
                      h="24px"
                    />
                  </InputRightElement>
                </InputGroup>
              </FormControl>
            </Flex>

            {/* Log In Button Container - Centered */}
            <Flex
              justifyContent="center"
              width="100%"
              // padding: 12px 16px; from CSS for container (Depth 4, Frame 3)
              // The VStack spacing and button's own padding/margins should suffice.
              pt="12px" // Adding some top padding as per Depth 4, Frame 3
              pb="12px" // Adding some bottom padding
            >
              <Button
                type="submit"
                bg="#009963" // background: #009963;
                color="#141414" // color: #141414; (for Log In button text)
                fontFamily="'Open Sans', sans-serif" // font-family: 'Inter';
                fontWeight="700"
                fontSize="24px"
                lineHeight="24px"
                borderRadius="8px" // border-radius: 8px;
                height="55px" // height: 55px;
                // width="full" // Will use max-width
                minWidth="84px" // min-width: 84px;
                width={{ base: '100%', md: '464px' }} // width: 464px; (max-width: 480px in CSS for container)
                maxWidth="464px"
                px="20px" // padding: 0px 20px; (for button text itself)
                isLoading={isLoading}
              >
                Log In
              </Button>
            </Flex>

            {/* Don't have an account? Sign Up Link Container (Depth 4, Frame 4)*/}
            <Flex
              direction="column"
              alignItems="center"
              width="100%"
              // padding: 4px 16px 12px; from CSS for its container
              pt="4px"
              pb="12px"
            >
              <Text
                textAlign="center"
                fontFamily="'Open Sans', sans-serif" // font-family: 'Inter';
                fontSize="14px" // font-size: 14px;
                lineHeight="21px" // line-height: 21px;
                color="#707070" // color: #707070;
              >
                Don&apos;t have an account?{' '}
                <Button
                  variant="link"
                  color="#009963" // Making the link part stand out, green like the button
                  fontWeight="700" // Bolder for emphasis
                  fontSize="14px" // Match surrounding text
                  fontFamily="'Open Sans', sans-serif" // Keep font consistent for the link part
                  onClick={() => router.push('/auth/signup')}
                  // textDecoration="underline" // Underline is default for variant="link"
                >
                  Sign Up
                </Button>
              </Text>
            </Flex>
          </VStack>
        </form>
      </Flex>
    </Flex>
  );
}

// New default export SignInPage that wraps SignInForm with Suspense
export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <Box maxW="md" mx="auto" mt={10} p={8} textAlign="center">
          <Text>Loading page...</Text>
        </Box>
      }
    >
      <SignInForm />
    </Suspense>
  );
}
