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
  Flex,
  InputGroup,
  InputRightElement,
  Icon,
} from '@chakra-ui/react';
import { ViewIcon, ViewOffIcon } from '@chakra-ui/icons';

export default function SignUpPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [name, setName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formErrorMessage, setFormErrorMessage] = useState<string | null>(null);
  const toast = useToast();
  const router = useRouter();

  const validatePassword = (password: string): boolean => {
    const minLength = 8;
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumber = /[0-9]/.test(password);
    const hasSpecialChar = /[^A-Za-z0-9]/.test(password);
    return (
      password.length >= minLength &&
      hasUpperCase &&
      hasLowerCase &&
      hasNumber &&
      hasSpecialChar
    );
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormErrorMessage(null);

    if (password !== confirmPassword) {
      setFormErrorMessage(
        'Passwords do not match. Please ensure both password fields are identical.',
      );
      return;
    }

    if (!validatePassword(password)) {
      setFormErrorMessage(
        'Password must be at least 8 characters long and include an uppercase letter, a lowercase letter, a number, and a special character.',
      );
      return;
    }

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
        router.push('/api/auth/signin');
      } else {
        const errorMessage =
          data.message || 'An error occurred during sign up.';
        // Check for specific error indicating email already exists
        const emailExistsError =
          typeof errorMessage === 'string' &&
          errorMessage.toLowerCase().includes('email') &&
          (errorMessage.toLowerCase().includes('exist') ||
            errorMessage.toLowerCase().includes('taken') ||
            errorMessage.toLowerCase().includes('in use'));

        if (emailExistsError) {
          setFormErrorMessage('There is an account connected to this email.');
        } else {
          setFormErrorMessage(errorMessage);
        }
      }
    } catch (error) {
      console.error('Sign up fetch error:', error);
      setFormErrorMessage('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = () => {
    setFormErrorMessage(null); // Clear error message when user types
  };

  return (
    <Flex
      direction="column"
      alignItems="center"
      justifyContent="center"
      minHeight="800px"
      bg="gray.100"
      width="100%"
      py="20px"
    >
      <Flex
        direction="column"
        alignItems="flex-start"
        width={{ base: '100%', md: '1280px' }}
        bg="white"
        borderRadius="md"
        boxShadow="lg"
      >
        <form onSubmit={handleSubmit} style={{ width: '100%' }}>
          <VStack
            spacing={{ base: '16px', md: '20px' }}
            width={{ base: '100%', md: '960px' }}
            maxWidth="960px"
            mx="auto"
            py={{ base: '20px', md: '40px' }}
            px={{ base: '15px', md: '20px' }}
            align="stretch"
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
                color="#1C170D"
              >
                Create New Account
              </Heading>
            </Flex>

            {/* Username and Email Address Fields - Arranged in a Flex container for two-column layout on md+ screens */}
            <Flex
              direction={{ base: 'column', md: 'row' }}
              gap={{ base: '16px', md: '32px' }} // gap: 16px from Figma (between items in a row like Username & Email)
              width="100%"
              alignItems={{ base: 'stretch', md: 'flex-end' }} // align-items: flex-end (from Figma for Username container)
            >
              {/* Username Field */}
              <FormControl
                isRequired
                width={{ base: '100%', md: '480px' }} // max-width: 480px
                maxWidth="480px"
              >
                <FormLabel
                  fontFamily="'Open Sans', sans-serif"
                  fontWeight="500"
                  fontSize="24px"
                  lineHeight="24px"
                  color="#1C170D"
                  mb="8px" // padding: 0px 0px 8px (bottom padding for label container)
                >
                  Username:
                </FormLabel>
                <Input
                  type="text" // Changed from email to text for username
                  value={name} // Assuming 'name' state is for username
                  onChange={(e) => {
                    setName(e.target.value);
                    handleInputChange(); // Clear error on change
                  }}
                  placeholder="Choose your username" // Placeholder text from Figma
                  isDisabled={isLoading}
                  height="56px" // height: 56px for input box
                  bg="#FFFFFF" // background: #FFFFFF
                  border="1px solid #E8DECF" // border: 1px solid #E8DECF
                  borderRadius="12px" // border-radius: 12px
                  padding="15px" // padding: 15px
                  fontFamily="'Open Sans', sans-serif"
                  fontSize="16px"
                  lineHeight="24px"
                  color="#A1824A" // Placeholder text color
                  _placeholder={{ color: '#A1824A' }}
                />
              </FormControl>

              {/* Email Address Field */}
              <FormControl
                isRequired
                width={{ base: '100%', md: '480px' }} // max-width: 480px
                maxWidth="480px"
              >
                <FormLabel
                  fontFamily="'Open Sans', sans-serif"
                  fontWeight="500"
                  fontSize="24px"
                  lineHeight="24px"
                  color="#1C170D"
                  mb="8px"
                >
                  Email Address:
                </FormLabel>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    handleInputChange(); // Clear error on change
                  }}
                  placeholder="Enter your email" // Placeholder text from Figma
                  isDisabled={isLoading}
                  height="56px"
                  bg="#FFFFFF"
                  border="1px solid #E8DECF"
                  borderRadius="12px"
                  padding="15px"
                  fontFamily="'Open Sans', sans-serif"
                  fontSize="16px"
                  lineHeight="24px"
                  color="#A1824A"
                  _placeholder={{ color: '#A1824A' }}
                />
              </FormControl>
            </Flex>

            {/* Password and Re-enter Password Fields */}
            <Flex
              direction={{ base: 'column', md: 'row' }}
              gap={{ base: '16px', md: '32px' }}
              width="100%"
              alignItems={{ base: 'stretch', md: 'flex-end' }}
            >
              {/* Password Field */}
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
                  color="#1C170D"
                  mb="8px"
                >
                  Create a Password:
                </FormLabel>
                <InputGroup size="md">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      handleInputChange(); // Clear error on change
                    }}
                    placeholder="Select a strong password"
                    isDisabled={isLoading}
                    height="56px"
                    bg="#FFFFFF"
                    border="1px solid #E8DECF"
                    borderRadius="12px"
                    borderRightRadius={{ base: '12px', md: '0' }}
                    padding="15px"
                    fontFamily="'Open Sans', sans-serif"
                    fontSize="16px"
                    lineHeight="24px"
                    color="#A1824A"
                    _placeholder={{ color: '#A1824A' }}
                  />
                  <InputRightElement
                    width="40px"
                    height="56px"
                    border="1px solid #E8DECF"
                    borderLeftWidth="0px"
                    borderTopRightRadius="12px"
                    borderBottomRightRadius="12px"
                    bg="#FFFFFF"
                    onClick={() => setShowPassword(!showPassword)}
                    cursor="pointer"
                  >
                    <Icon
                      as={showPassword ? ViewOffIcon : ViewIcon}
                      color="#A1824A"
                      w="24px"
                      h="24px"
                    />
                  </InputRightElement>
                </InputGroup>
              </FormControl>

              {/* Re-enter Password Field */}
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
                  color="#1C170D"
                  mb="8px"
                >
                  Re-enter Password:
                </FormLabel>
                <Input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    handleInputChange(); // Clear error on change
                  }}
                  placeholder="Confirm your password"
                  isDisabled={isLoading}
                  height="56px"
                  bg="#FFFFFF"
                  border="1px solid #E8DECF"
                  borderRadius="12px"
                  padding="15px"
                  fontFamily="'Open Sans', sans-serif"
                  fontSize="16px"
                  lineHeight="24px"
                  color="#A1824A"
                  _placeholder={{ color: '#A1824A' }}
                />
              </FormControl>
            </Flex>

            {/* Password Requirement text */}
            <Box width="100%" pt="4px" pb="12px">
              <Text
                fontFamily="'Open Sans', sans-serif"
                fontWeight="400"
                fontSize="14px"
                lineHeight="21px"
                color="#A1824A"
                whiteSpace="pre-line"
              >
                {'At least 8 characters\n' +
                  'One uppercase letter\n' +
                  'One lowercase letter\n' +
                  'One number\n' +
                  'One special character'}
              </Text>
            </Box>

            {/* Display Form Error Message */}
            {formErrorMessage && (
              <Text
                color="red.500"
                textAlign="center"
                mt={2}
                mb={2}
                whiteSpace="pre-line"
              >
                {formErrorMessage}
              </Text>
            )}

            {/* Create Account Button Container */}
            <Flex justifyContent="center" width="100%" py="12px">
              <Button
                type="submit"
                bg="#009963"
                color="#FFFFFF"
                fontFamily="'Open Sans', sans-serif"
                fontWeight="700"
                fontSize="24px"
                lineHeight="24px"
                borderRadius="24px"
                height="48px"
                minWidth="84px"
                maxWidth={{ base: '100%', md: '480px' }}
                width={{ base: '100%', md: 'auto' }}
                flexGrow={{ md: 1 }}
                px="20px"
                isLoading={isLoading}
              >
                Create Account
              </Button>
            </Flex>

            {/* Already have an account? Log In Link Container */}
            <Flex
              direction="column"
              alignItems="center"
              width="100%"
              pt="4px"
              pb="12px"
            >
              <Text
                textAlign="center"
                fontFamily="'Open Sans', sans-serif"
                fontSize="20px"
                lineHeight="21px"
                color="#A1824A"
              >
                Already have an account?{' '}
                <Button
                  variant="link"
                  color="#A1824A"
                  fontWeight="700"
                  fontSize="20px"
                  onClick={() => router.push('/api/auth/signin')}
                  fontFamily="'Open Sans', sans-serif"
                  textDecoration="underline"
                >
                  Log In
                </Button>
              </Text>
            </Flex>
          </VStack>
        </form>
      </Flex>
    </Flex>
  );
}
