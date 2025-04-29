'use client';

import { useState, useEffect, FormEvent } from 'react';
import { useSession, update } from 'next-auth/react'; // Import update if you want to update session
import { useRouter } from 'next/navigation';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  Text,
  Spinner,
  useToast,
  Flex,
  Alert,
  AlertIcon,
} from '@chakra-ui/react';

// Define a type for the user profile data
interface UserProfile {
  id: string;
  name: string | null;
  email: string | null;
  image: string | null;
  createdAt: string; // Dates are often strings after JSON serialization
}

export default function ProfilePage() {
  const { data: session, status, update: updateSession } = useSession(); // Get session and update function
  const router = useRouter();
  const toast = useToast();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [nameInput, setNameInput] = useState('');
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/api/auth/signin?callbackUrl=/profile');
    } else if (status === 'authenticated') {
      setIsLoadingData(true);
      setError(null);
      fetch('/api/profile')
        .then(async (res) => {
          if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.message || `HTTP error! status: ${res.status}`);
          }
          return res.json();
        })
        .then((data: UserProfile) => {
          setProfile(data);
          setNameInput(data.name || ''); // Initialize input with fetched name
        })
        .catch((err) => {
          console.error('Failed to fetch profile:', err);
          setError('Failed to load profile data. Please try refreshing.');
          toast({
            title: 'Error fetching profile',
            description: err.message || 'Could not load profile data.',
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
        })
        .finally(() => {
          setIsLoadingData(false);
        });
    }
  }, [status, router, toast]);

  const handleSaveChanges = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!profile || nameInput === profile.name) {
      // No changes detected
      toast({ title: 'No changes to save.', status: 'info', duration: 3000 });
      return;
    }
    setIsUpdating(true);
    setError(null);

    try {
      const response = await fetch('/api/profile', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: nameInput }),
      });

      const updatedProfile = await response.json();

      if (response.ok) {
        setProfile(updatedProfile); // Update local profile state
        setNameInput(updatedProfile.name || ''); // Update input field
        toast({
          title: 'Profile updated.',
          status: 'success',
          duration: 5000,
          isClosable: true,
        });

        // Optional: Update the session immediately with the new name
        // This avoids needing a page refresh/re-login to see the name change in the header
        await updateSession({ name: updatedProfile.name });

      } else {
        throw new Error(updatedProfile.message || 'Failed to update profile.');
      }
    } catch (err: any) {
      console.error('Update profile error:', err);
      setError(err.message || 'Could not update profile.');
      toast({
        title: 'Update failed.',
        description: err.message || 'Could not save changes.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsUpdating(false);
    }
  };

  if (status === 'loading' || isLoadingData) {
    return (
      <Flex justify="center" align="center" height="80vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (status === 'unauthenticated') {
    // Should have been redirected, but as a fallback:
    return (
      <Flex justify="center" align="center" height="80vh">
        <Text>Redirecting to sign in...</Text>
      </Flex>
    );
  }

  if (error) {
    return (
       <Alert status="error" borderRadius="md" mt={4} maxW="md" mx="auto">
         <AlertIcon />
         {error}
       </Alert>
    );
  }

  if (!profile) {
    // Should not happen if loading is finished and no error, but good practice
    return <Text>Could not load profile.</Text>;
  }

  return (
    <Box maxW="lg" mx="auto" mt={10} p={8} borderWidth={1} borderRadius="lg" boxShadow="lg">
      <Heading as="h1" size="xl" mb={6} textAlign="center">
        Your Profile
      </Heading>
      <VStack spacing={6} as="form" onSubmit={handleSaveChanges}>
        <FormControl isReadOnly>
          <FormLabel>Email address</FormLabel>
          <Input type="email" value={profile.email || 'Not available'} isDisabled />
        </FormControl>

        <FormControl isRequired>
          <FormLabel>Name</FormLabel>
          <Input
            type="text"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            placeholder="Your Name"
            isDisabled={isUpdating}
          />
        </FormControl>

        <FormControl isReadOnly>
          <FormLabel>Joined On</FormLabel>
          <Input
            type="text"
            value={new Date(profile.createdAt).toLocaleDateString() || '-'}
            isDisabled
          />
        </FormControl>

        <Button
          type="submit"
          colorScheme="blue"
          width="full"
          isLoading={isUpdating}
          disabled={nameInput === profile.name || isUpdating}
        >
          Save Changes
        </Button>
      </VStack>
    </Box>
  );
} 