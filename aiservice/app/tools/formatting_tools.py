from typing import List, Dict, Any, Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import re

class KeywordToTagFormatterTool(BaseTool):
    name: str = "Keyword to Tag Formatter"
    description: str = (
        "Formats a list of raw keywords into standardized tags. "
        "Handles common abbreviations, CamelCasing for multi-word tags, and adds a '#' prefix."
    )
    # Predefined dictionary for common abbreviations
    # This could be loaded from a configuration file in a more complex setup
    abbreviations: Dict[str, str] = {
        "artificial intelligence": "AI",
        "machine learning": "ML",
        "large language model": "LLM",
        "generative ai": "GenAI",
        "natural language processing": "NLP",
        "customer relationship management": "CRM",
        "key performance indicator": "KPI",
        "search engine optimization": "SEO",
        "user interface": "UI",
        "user experience": "UX",
        "application programming interface": "API",
        "software as a service": "SaaS",
        "platform as a service": "PaaS",
        "infrastructure as a service": "IaaS",
        "return on investment": "ROI",
        "human resources": "HR"
    }

    def _run(self, list_of_keywords: List[str]) -> List[str]:
        if not isinstance(list_of_keywords, list):
            return ["Error: Input must be a list of keywords."]
        if not list_of_keywords:
            return []

        formatted_tags: List[str] = []
        for keyword in list_of_keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                # Skip empty or non-string keywords, or log a warning
                continue

            processed_keyword = keyword.lower().strip()

            # Check for abbreviation
            if processed_keyword in self.abbreviations:
                tag = self.abbreviations[processed_keyword]
            else:
                # Apply CamelCase for multi-word tags
                # Remove special characters that are not alphanumeric, then capitalize
                # This simple CamelCase works for space-separated words.
                # More complex scenarios might need sophisticated handling.
                
                # Remove most special characters, keep spaces for splitting
                processed_keyword = re.sub(r'[^a-z0-9\s]', '', processed_keyword)
                words = processed_keyword.split()
                if not words: # handles case where keyword was only special characters
                    continue
                
                if len(words) > 1:
                    tag = "".join([words[0].lower()] + [word.capitalize() for word in words[1:]])
                    # A common convention is first word lower, rest upper, or all upper.
                    # For tags, often AllUpperCamelCase is preferred.
                    # Let's use AllUpperCamelCase for multi-word tags that aren't abbreviations.
                    tag = "".join(word.capitalize() for word in words)
                else:
                    tag = words[0].capitalize() # Capitalize single words too for consistency if not abbreviated

            formatted_tags.append(f"#{tag}")
            
        # Remove duplicates while preserving order (for Python 3.7+)
        return list(dict.fromkeys(formatted_tags))

# Example Usage (for testing purposes, not part of the class)
if __name__ == '__main__':
    tool = KeywordToTagFormatterTool()
    
    # Test cases
    test_keywords_1 = ["artificial intelligence", "data scaling", "Gen AI adoption", " natural language processing ", "multi word tag example"]
    print(f"Input: {test_keywords_1}")
    print(f"Output: {tool.run(test_keywords_1)}")
    # Expected: ['#AI', '#DataScaling', '#GenAIAdoption', '#NLP', '#MultiWordTagExample'] (order might vary slightly if duplicates were initially present before fromkeys)

    test_keywords_2 = ["User Experience", "crm", "  ROI  ", "single"]
    print(f"Input: {test_keywords_2}")
    print(f"Output: {tool.run(test_keywords_2)}")
    # Expected: ['#UX', '#CRM', '#ROI', '#Single']
    
    test_keywords_3 = ["", "   ", "special-char! keyword"]
    print(f"Input: {test_keywords_3}")
    print(f"Output: {tool.run(test_keywords_3)}")
    # Expected: ['#SpecialcharKeyword']
    
    test_keywords_4 = ["complex data types", "PYTHON programming", "python"]
    print(f"Input: {test_keywords_4}")
    print(f"Output: {tool.run(test_keywords_4)}")
    # Expected: ['#ComplexDataTypes', '#PYTHONProgramming', '#Python'] -> will be #Python, #Pythonprogramming, #Complexdatatypes (due to .lower())
    # Corrected expected: ['#ComplexDataTypes', '#PythonProgramming', '#Python'] (after ensuring consistent capitalization) 
    # Actually, after re.sub and .lower(), it'd be ['#ComplexDataTypes', '#PythonProgramming', '#Python']

    test_keywords_5 = ["ContentBlock", "Content Block", "content_block"]
    print(f"Input: {test_keywords_5}")
    print(f"Output: {tool.run(test_keywords_5)}")
    # Expected: ['#ContentBlock'] (assuming all variants resolve to the same and are deduplicated)

    test_keywords_6 = []
    print(f"Input: {test_keywords_6}")
    print(f"Output: {tool.run(test_keywords_6)}")
    # Expected: []

    test_keywords_7 = ["machine learning", "Machine Learning"] # Test deduplication with different casing
    print(f"Input: {test_keywords_7}")
    print(f"Output: {tool.run(test_keywords_7)}")
    # Expected: ['#ML']
    
    test_keywords_8 = ["test", "test", "Test"] # Test deduplication
    print(f"Input: {test_keywords_8}")
    print(f"Output: {tool.run(test_keywords_8)}")
    # Expected: ['#Test']
    
    # Test with non-string element (should ideally be handled by Pydantic in CrewAI, but good to be robust)
    # tool.run(["valid", 123]) # This would cause an error if not for Pydantic validation on the agent tool args. 
    # The _run method now checks for list and string types.
    
    # Test keywords that become empty after stripping special characters
    test_keywords_9 = ["!!!", "---", "key word"]
    print(f"Input: {test_keywords_9}")
    print(f"Output: {tool.run(test_keywords_9)}")
    # Expected: ["#KeyWord"] 