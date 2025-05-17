import requests
# from bs4 import BeautifulSoup # No longer primary, but can be a fallback
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Optional, Any # Added Dict, Optional, Any
from newspaper import Article, ArticleException # Import newspaper

class WebPageContentFetcherToolInput(BaseModel):
    """Input schema for WebPageContentFetcherTool."""
    url: str = Field(..., description="The URL of the web page to fetch content from.")

class WebPageContentOutput(BaseModel):
    """Output schema for the WebPageContentFetcherTool."""
    status: str
    text: Optional[str] = None
    url: str
    error: Optional[str] = None
    # We could add title, authors, publish_date from newspaper3k here if needed later
    # title: Optional[str] = None 

class WebPageContentFetcherTool(BaseTool):
    name: str = "Web Page Content Fetcher"
    description: str = ("Fetches, parses, and returns the main textual content from a given web page URL. "
                        "Returns a dictionary with status, text, url, and error fields.")
    args_schema: Type[BaseModel] = WebPageContentFetcherToolInput
    # It can be good practice to define an output schema too, though not strictly enforced by BaseTool for _run return type hint.
    # output_schema: Type[BaseModel] = WebPageContentOutput # Optional, for clarity or future validation

    def _run(self, url: str) -> Dict[str, Any]: # Changed return type hint
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Use newspaper3k to download and parse
            # Newspaper3k prefers to handle the download itself if you give it a URL.
            # However, it can also parse already downloaded HTML.
            # For simplicity and to leverage its request handling, let it download.
            article = Article(url)
            
            # Newspaper3k downloads when you call parse() or download() explicitly
            # We can fetch HTML with requests first if we want more control over headers/timeout for the GET request
            # and then feed HTML to newspaper, or let newspaper handle the download.
            # Let's try letting newspaper3k handle the download directly first.
            # It uses requests underneath but might have its own timeout/header logic.
            # To ensure our timeout and headers: 
            # response = requests.get(url, headers=headers, timeout=20)
            # response.raise_for_status()
            # article.download(input_html=response.content)

            # Simpler approach: let Article download and parse
            article.download() # Downloads the HTML
            article.parse()    # Parses the downloaded HTML to extract content

            # Fallback for 403 errors (often due to bot detection)
            if article.download_state == 2 and not article.text: # 2 often means download error / 403
                 # Try with requests and then pass html to newspaper
                try:
                    # print(f"Newspaper3k download failed for {url}, trying with requests...") # Less noisy for now
                    response = requests.get(url, headers=headers, timeout=20)
                    response.raise_for_status()
                    article = Article(url) # Re-initialize Article with the URL
                    article.download(input_html=response.content)
                    article.parse()
                except Exception as req_e:
                    return {"status": "error_fetch_fallback", "text": None, "url": url, "error": f"Fallback requests fetch also failed. Original newspaper error likely a block/403. Requests error: {str(req_e)}"}

            content = article.text
            # title = article.title # We can also get title, authors, publish_date etc.

            if not content:
                return {"status": "error_no_content", "text": None, "url": url, "error": "Newspaper3k could not extract any main content. The page might be empty, non-article, or heavily JavaScript-reliant."}
            
            # Rudimentary paywall hint (can be kept if still relevant)
            if "subscribe to continue" in content.lower() or "login to read" in content.lower():
                # Return partial content with a paywall hint
                return {"status": "error_paywall", "text": content[:1500] + "...", "url": url, "error": "Content might be behind a paywall or require login."}

            return {"status": "success", "text": content, "url": url, "error": None}

        except ArticleException as e:
            # This can happen if newspaper3k fails to download or parse for various reasons
            return {"status": "error_parse", "text": None, "url": url, "error": f"Newspaper3k failed to process the article. Error: {str(e)}"}
        except requests.exceptions.Timeout:
            return {"status": "error_timeout", "text": None, "url": url, "error": "Request timed out (either by newspaper3k or fallback requests)."}
        except requests.exceptions.HTTPError as e:
            return {"status": "error_http", "text": None, "url": url, "error": f"HTTP error occurred (by fallback requests). Status code: {e.response.status_code}. Message: {e}"}
        except requests.exceptions.RequestException as e:
            return {"status": "error_request_generic", "text": None, "url": url, "error": f"A network error occurred (by fallback requests). Error: {e}"}
        except Exception as e:
            # Catch-all for other unexpected errors
            return {"status": "error_unknown", "text": None, "url": url, "error": f"An unexpected error occurred. Error: {str(e)}"}

# Example Usage (for testing the tool directly):
if __name__ == '__main__':
    import json # For pretty printing the dict
    tool = WebPageContentFetcherTool()
    
    test_urls = [ # Had 404 before, let's see now
        "https://www.deeplearning.ai/the-batch/issue-301/",
        "https://www.example.com",
        "https://www.wsj.com/tech/ai/mit-says-it-no-longer-stands-behind-students-ai-research-paper-11434092?mod=hp_lead_pos11",
        "https://www.figma.com/blog/engineering/",
        "https://mail.google.com/mail/u/0/#inbox/FMfcgzQbfLSVzNwTfXGDWSTTpGrXfHhL",
        "https://www.youtube.com/watch?v=uRInI9rnDNE",
        "https://airbnb.tech/uncategorized/accelerating-large-scale-test-migration-with-llms/"
    ]

    for t_url in test_urls:
        print(f"Fetching content from: {t_url}")
        result = tool.run(url=t_url) 
        print("--- Result --- ")
        print(json.dumps(result, indent=2)) # Pretty print the dictionary
        if result['status'] == 'success' and result['text']:
            print("--- Sample Text ---")
            print(result['text'][:500] + "...")
        print("\n-----------------------------\n") 