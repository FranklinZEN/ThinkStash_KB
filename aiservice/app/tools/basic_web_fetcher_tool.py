import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Optional, Any

# We can reuse the same input schema
class WebPageContentFetcherToolInput(BaseModel):
    """Input schema for BasicWebPageContentFetcherTool."""
    url: str = Field(..., description="The URL of the web page to fetch content from.")

class BasicWebPageContentFetcherTool(BaseTool):
    name: str = "Basic Web Page Content Fetcher (Requests+BS4)"
    description: str = ("Fetches and parses the main textual content from a given web page URL using only Requests and BeautifulSoup. "
                        "Returns a dictionary with status, text, url, and error fields.")
    args_schema: Type[BaseModel] = WebPageContentFetcherToolInput

    def _run(self, url: str) -> Dict[str, Any]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

            soup = BeautifulSoup(response.content, 'html.parser')

            # Attempt to remove common non-content elements
            for element_type in ['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'button']:
                for element in soup.find_all(element_type):
                    element.decompose()
            
            text_parts = []
            # Try to get content from common main content tags first
            main_content_tags = soup.find_all(['article', 'main', '.main', '#main', '.content', '#content', '.post-content', '#post-content'])
            if main_content_tags:
                for tag in main_content_tags:
                    text_parts.append(tag.get_text(separator=' ', strip=True))
            else:
                # Fallback to common text-bearing tags if specific main content tags are not found
                for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'div']):
                    # Avoid div if it only contains other block elements already processed or is too generic without text
                    if element.name == 'div' and not element.find(text=True, recursive=False).strip():
                        continue
                    text_parts.append(element.get_text(separator=' ', strip=True))
            
            content = "\n".join(filter(None, text_parts))

            if not content.strip(): # Check if content is just whitespace
                # Final fallback: get all text from body, then try to clean it a bit more aggressively
                body = soup.find('body')
                if body:
                    content = body.get_text(separator=' ', strip=True)
                    # Simple cleaning for very noisy body text (can be expanded)
                    lines = (line.strip() for line in content.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    content = '\n'.join(chunk for chunk in chunks if chunk and len(chunk) > 10) # Keep somewhat meaningful lines
                else:
                    return {"status": "error_no_content", "text": None, "url": url, "error": "Could not find body content."}

            if not content.strip():
                return {"status": "error_no_content", "text": None, "url": url, "error": "BeautifulSoup could not extract any meaningful content."}
            
            # Rudimentary paywall hint
            if "subscribe to continue" in content.lower() or "login to read" in content.lower():
                return {"status": "error_paywall", "text": content[:1500] + "...", "url": url, "error": "Content might be behind a paywall or require login."}

            return {"status": "success", "text": content, "url": url, "error": None}

        except requests.exceptions.Timeout:
            return {"status": "error_timeout", "text": None, "url": url, "error": "Request timed out."}
        except requests.exceptions.HTTPError as e:
            return {"status": "error_http", "text": None, "url": url, "error": f"HTTP error occurred. Status code: {e.response.status_code}. Message: {e}"}
        except requests.exceptions.RequestException as e:
            return {"status": "error_request_generic", "text": None, "url": url, "error": f"A network error occurred. Error: {e}"}
        except Exception as e:
            return {"status": "error_unknown_parse", "text": None, "url": url, "error": f"An unexpected error occurred during parsing/processing. Error: {str(e)}"}

# Example Usage (for testing the tool directly):
if __name__ == '__main__':
    import json
    tool = BasicWebPageContentFetcherTool()
    
    # Use the same test URLs you provided
    test_urls = [
        "https://www.deeplearning.ai/the-batch/issue-301/",
        "https://www.example.com",
        "https://www.wsj.com/tech/ai/mit-says-it-no-longer-stands-behind-students-ai-research-paper-11434092?mod=hp_lead_pos11",
        "https://www.figma.com/blog/engineering/",
        "https://mail.google.com/mail/u/0/#inbox/FMfcgzQbfLSVzNwTfXGDWSTTpGrXfHhL",
        "https://www.youtube.com/watch?v=uRInI9rnDNE",
        "https://airbnb.tech/uncategorized/accelerating-large-scale-test-migration-with-llms/"
    ]

    for t_url in test_urls:
        print(f"Fetching content from: {t_url} (using Basic Requests+BS4 Tool)")
        result = tool.run(url=t_url) 
        print("--- Result --- ")
        print(json.dumps(result, indent=2))
        if result['status'] == 'success' and result['text']:
            print("--- Sample Text (Basic Requests+BS4) ---")
            print(result['text'][:500] + "...")
        print("\n-----------------------------\n") 