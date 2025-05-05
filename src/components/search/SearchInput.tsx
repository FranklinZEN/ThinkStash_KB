import React, { useState } from 'react';
import {
  Input,
  InputGroup,
  InputLeftElement,
  InputRightElement,
  Button,
  Kbd,
} from '@chakra-ui/react';
import { SearchIcon } from '@chakra-ui/icons';

interface SearchInputProps {
  onSearchSubmit: (query: string) => void;
  placeholder?: string;
}

const SearchInput: React.FC<SearchInputProps> = ({ onSearchSubmit, placeholder = "Search cards..." }) => {
  const [searchTerm, setSearchTerm] = useState('');

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  };

  const handleSearch = () => {
    onSearchSubmit(searchTerm.trim());
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <InputGroup size="md" width={{ base: '100%', md: '350px' }}>
      <InputLeftElement pointerEvents="none">
        <SearchIcon color="gray.300" />
      </InputLeftElement>
      <Input
        type="text"
        placeholder={placeholder}
        value={searchTerm}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        borderRadius="md"
        pr="4.5rem"
      />
      <InputRightElement width="4.5rem">
        <Button h="1.75rem" size="sm" onClick={handleSearch} isDisabled={!searchTerm.trim()}>
          Search
        </Button>
      </InputRightElement>
    </InputGroup>
  );
};

export default SearchInput; 