import requests
from trafilatura import fetch_url, extract
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
import os
import re
from urllib.parse import urljoin, urlparse
from typing import Type, Dict, Optional, Any, List, Union, Set
import time # Import time for timing

# --- Configuration Data for Paywall Strategy (from provided file) ---
VERY_STRICT_PAYWALL_DOMAINS: Set[str] = {
    "wsj.com", "ft.com", "thetimes.co.uk", "thesundaytimes.co.uk", "barrons.com",
    "theathletic.com", "statista.com", "digiday.com", "adweek.com", "stratechery.com",
    "sciencedirect.com", "link.springer.com", "onlinelibrary.wiley.com", "tandfonline.com",
    "jamanetwork.com", "nejm.org", "thelancet.com", "cell.com", "nature.com", "science.org",
    "ieeexplore.ieee.org", "jstor.org", "academic.oup.com", "cambridge.org/core"
}

GENERAL_METERED_PAYWALL_DOMAINS: Set[str] = { # Used for context, less for direct blocking
    "nytimes.com", "washingtonpost.com", "economist.com", "bloomberg.com", "hbr.org",
    "wired.com", "technologyreview.com", "medium.com", "asia.nikkei.com", "foreignpolicy.com", 
    "theatlantic.com", "newyorker.com", "vanityfair.com", "forbes.com", "fortune.com", 
    "bostonglobe.com", "chicagotribune.com", "latimes.com", "sfchronicle.com", 
    "theglobeandmail.com", "reuters.com"
}

PAYWALL_KEYWORDS: Set[str] = {
    "subscribe", "log in to continue", "login to continue", "premium content", "unlimited access",
    "member-only", "member exclusive", "free articles remaining", "digital subscription",
    "your free trial", "full access", "create an account to read", "sign in to read",
    "this article is for subscribers", "unlock this article", "join to read"
}

PAYWALL_HTML_SELECTORS: List[str] = [
    ".modal-paywall", "#paywall-dialog", ".fancybox-paywall", ".tp-modal", ".tp-backdrop",
    ".fc-ab-root", "#gatehouse-modal", ".restricted-content", ".overlay-content",
    "[id*=paywall]", "[class*=paywall]", "[id*=modal-restrict]", "[class*=modal-restrict]",
    "[data-testid*='paywall']", "[class*='tp-container']"
]
# --- End of Configuration Data from provided file ---

class HTTPFetchingTool(BaseTool):
    name: str = "HTTP Content Fetcher"
    description: str = (
        "Fetches the raw HTML content from a given URL. "
        "Handles redirects and uses a standard browser user-agent. "
        "Input: 'url' (string: the URL to fetch)."
        "Returns a dictionary with 'summary', 'full_html_content', 'final_url' (string after redirects), "
        "'status_code' (int), and 'error' (string, if any)."
    )

    def _run(self, url: str) -> dict:
        """Fetches HTML content from the URL.

        Args:
            url: The URL to fetch.

        Returns:
            A dictionary containing a summary, the full html_content, final_url, status_code, and error (if any).
        """
        start_time = time.time()
        print(f"HTTPFetchingTool: Starting fetch for {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            response.raise_for_status() 
            html_length = len(response.text)
            result = {
                "summary": f"Successfully fetched HTML from {response.url}. Length: {html_length} chars. Full content available via full_html_content key.",
                "full_html_content": response.text,
                "final_url": response.url,
                "status_code": response.status_code,
                "error": None
            }
        except requests.exceptions.RequestException as e:
            result = {
                "summary": f"Error fetching URL {url}: {e}",
                "full_html_content": None,
                "final_url": url, 
                "status_code": None, 
                "error": f"Error fetching URL {url}: {e}"
            }
        end_time = time.time()
        print(f"HTTPFetchingTool: Finished fetch for {url}. Duration: {end_time - start_time:.2f} seconds.")
        return result

class TrafilaturaContentExtractorTool(BaseTool):
    name: str = "Trafilatura Main Content Extractor"
    description: str = (
        "Extracts the main textual content from an HTML string using the Trafilatura library. "
        "Input: 'html_content' (string: the raw HTML of a web page)."
        "Optional input: 'source_url' (string: the original URL, can sometimes help Trafilatura)."
        "Returns the extracted main text as a string, or None if extraction fails."
    )

    def _run(self, html_content: str, source_url: str = None) -> str | None:
        """Extracts main content from HTML using Trafilatura.

        Args:
            html_content: The raw HTML string.
            source_url: Optional. The original URL of the content.

        Returns:
            The extracted main textual content, or None if extraction fails.
        """
        start_time = time.time()
        print(f"TrafilaturaContentExtractorTool: Starting extraction for URL: {source_url or 'Unknown'}. HTML length: {len(html_content) if html_content else 0}")

        if not isinstance(html_content, str) or not html_content.strip():
            print(f"TrafilaturaContentExtractorTool: Finished. Error: HTML content empty/invalid. Duration: {time.time() - start_time:.2f}s")
            return "Error: HTML content provided is empty or invalid."
        try:
            extracted_text = extract(html_content, url=source_url, include_comments=False, include_tables=True)
            print(f"TrafilaturaContentExtractorTool: Finished extraction for URL: {source_url or 'Unknown'}. Extracted text length: {len(extracted_text) if extracted_text else 0}. Duration: {time.time() - start_time:.2f}s")
            return extracted_text
        except Exception as e:
            print(f"TrafilaturaContentExtractorTool: Finished. Error during Trafilatura extraction: {e}. Duration: {time.time() - start_time:.2f}s")
            return None

class BeautifulSoupImageExtractorTool(BaseTool):
    name: str = "BeautifulSoup Image Extractor"
    description: str = (
        "Extracts image details (source URL, alt text, context) from an HTML string using BeautifulSoup. "
        "Input: 'html_content' (string: raw HTML), 'base_url' (string: for resolving relative image URLs)."
        "Returns a list of dictionaries, each representing an image with 'image_url', 'alt_text', 'extracted_caption', 'context_before_text', 'context_after_text'."
    )

    def _get_text_around_tag(self, tag, words=15, char_limit=150):
        """Helper to get text from siblings around a tag for context."""
        prev_text_parts = []
        count = 0
        for prev_sibling in tag.find_previous_siblings():
            if count >= words : break
            if prev_sibling.name: # Only consider actual tags, not just NavigableStrings directly
                text = prev_sibling.get_text(separator=' ', strip=True)
                if text:
                    prev_text_parts.insert(0,text)
                    count += len(text.split())
            if sum(len(p) for p in prev_text_parts) > char_limit: break
        
        next_text_parts = []
        count = 0
        for next_sibling in tag.find_next_siblings():
            if count >= words : break
            if next_sibling.name:
                text = next_sibling.get_text(separator=' ', strip=True)
                if text:
                    next_text_parts.append(text)
                    count += len(text.split())
            if sum(len(p) for p in next_text_parts) > char_limit: break

        return " ".join(prev_text_parts[-words:]), " ".join(next_text_parts[:words])

    def _run(self, html_content: str, base_url: str) -> list[dict] | str:
        """Extracts image details from HTML.

        Args:
            html_content: Raw HTML string.
            base_url: The base URL to resolve relative image paths.

        Returns:
            A list of image detail dictionaries, or an error string.
        """
        if not isinstance(html_content, str) or not html_content.strip():
            return "Error: HTML content provided is empty or invalid."
        if not isinstance(base_url, str) or not base_url.strip():
            return "Error: Base URL must be provided as a non-empty string."

        images_data = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # Find all <img> tags
            for img_tag in soup.find_all('img'):
                src = img_tag.get('src')
                if not src: # Skip images without a source
                    continue

                # Resolve relative URLs to absolute URLs
                image_url = urljoin(base_url, src)
                alt_text = img_tag.get('alt', '')

                # Try to find a caption (this is heuristic)
                # Look for <figcaption>, or text in a <figure> parent, or nearby paragraphs.
                caption = None
                if img_tag.find_parent('figure'):
                    figcaption = img_tag.find_parent('figure').find('figcaption')
                    if figcaption:
                        caption = figcaption.get_text(strip=True)
                
                # Get context before/after (simplified)
                # This is a basic approach. More sophisticated context might involve analyzing parent elements or specific DOM structures.
                context_before, context_after = self._get_text_around_tag(img_tag.find_parent() or img_tag)

                images_data.append({
                    'image_url': image_url,
                    'alt_text': alt_text,
                    'extracted_caption': caption,
                    'context_before_text': context_before or None,
                    'context_after_text': context_after or None
                })
            return images_data
        except Exception as e:
            return f"Error parsing HTML for images with BeautifulSoup: {e}"

class PaywallDetectionTool(BaseTool):
    name: str = "Paywall Detector"
    description: str = (
        "Detects paywalls based on URL, HTML keywords, and CSS selectors. "
        "Input: 'url' (string), 'html_content' (string, optional but recommended for full checks). "
        "Optional: 'extracted_text_length' (int, length of main text extracted by another tool)."
        "Returns a dictionary with 'status' ('strict_paywall_domain', 'pattern_match_paywall', 'likely_paywall_short_content', 'no_paywall_detected', 'uncertain'), "
        "'details' (string), and 'url' (string)."
    )

    def _get_domain(self, url_str: str) -> Optional[str]:
        try:
            return urlparse(url_str).hostname
        except Exception:
            return None

    def _check_domain_in_set(self, domain: Optional[str], domain_set: Set[str]) -> bool:
        if not domain:
            return False
        domain_lower = domain.lower()
        for item_in_set in domain_set:
            if domain_lower == item_in_set or domain_lower.endswith("." + item_in_set):
                return True
        return False

    def _run(self, url: str, html_content: str = None, extracted_text_length: int = -1) -> dict:
        """Detects paywalls using tiered logic.

        Args:
            url: The URL of the page.
            html_content: Optional HTML content of the page.
            extracted_text_length: Optional length of text extracted by Trafilatura/other tools.
                                   -1 indicates not provided.
        Returns:
            A dictionary with detection status, details, and the original URL.
        """
        final_domain = self._get_domain(url)

        # Tier 1: Strict Paywall Domains (Applied by Orchestrator or can be re-checked here for safety)
        if self._check_domain_in_set(final_domain, VERY_STRICT_PAYWALL_DOMAINS):
            return {
                "status": "strict_paywall_domain",
                "details": f"URL domain ({final_domain}) is on the strict paywall list.",
                "url": url
            }

        # Tier 2: Keyword and Selector Scan (if HTML is available)
        if html_content:
            soup = None # Initialize soup to None
            # Keyword check
            for keyword in PAYWALL_KEYWORDS:
                if keyword in html_content.lower():
                    return {
                        "status": "pattern_match_paywall",
                        "details": f"Paywall suspected based on keyword: '{keyword}' in HTML.",
                        "url": url
                    }
            # Selector check
            try:
                soup = BeautifulSoup(html_content, 'lxml') # Parse only if needed for selectors
                for selector in PAYWALL_HTML_SELECTORS:
                    if soup.select_one(selector):
                        return {
                            "status": "pattern_match_paywall",
                            "details": f"Paywall suspected based on CSS selector: '{selector}' in HTML.",
                            "url": url
                        }
            except Exception as e_bs:
                # Error during soup creation for selectors, can't perform this check
                print(f"PaywallDetectionTool: BeautifulSoup parsing error for selector check on {url}: {e_bs}")
                # Continue, as other checks might still apply
        
        # Tier 3: Short Content Heuristic (if extracted_text_length is provided and meaningful)
        # This tier is more indicative if initial keyword/selector scan also found clues (though we return early on those).
        # If no HTML was provided for Tier 2, this check might be less reliable alone.
        # For simplicity here, if content is very short, and it's a known metered domain, it's a stronger signal.
        if 0 <= extracted_text_length < 300: # Meaningful length provided and it's short
            if self._check_domain_in_set(final_domain, GENERAL_METERED_PAYWALL_DOMAINS):
                 return {
                    "status": "likely_paywall_short_content",
                    "details": f"Content is very short ({extracted_text_length} chars) on a general/metered paywall domain ({final_domain}). Possible paywall or teaser.",
                    "url": url
                }
            # If not a known metered domain, but still very short and HTML was scanned without hits:
            elif html_content: # Implying Tier 2 did not find obvious patterns
                return {
                    "status": "uncertain",
                    "details": f"Content is very short ({extracted_text_length} chars) but no definitive paywall patterns found in HTML. Could be teaser or just a short page.",
                    "url": url
                }
            else: # No HTML to scan, only short text length - less certain
                return {
                    "status": "uncertain",
                    "details": f"Content is very short ({extracted_text_length} chars). HTML not available for pattern scan. Paywall status uncertain.",
                    "url": url
                }

        # If none of the above conditions met
        return {
            "status": "no_paywall_detected", 
            "details": "No definitive paywall indicators found based on available information.",
            "url": url
        }

# Example Usage (for illustration)
if __name__ == '__main__':
    http_tool = HTTPFetchingTool()
    trafilatura_tool = TrafilaturaContentExtractorTool()
    bs_image_tool = BeautifulSoupImageExtractorTool()
    paywall_tool = PaywallDetectionTool()

    test_urls_for_paywall = [
        "https://www.wired.com/story/how-tiktok-became-a-diplomatic-weapon/", # General metered, might pass if not blocked
        "https://www.wsj.com/articles/global-stocks-markets-dow-news-02-23-2024-0210a870", # Strict
        "https://www.nytimes.com/2024/02/23/us/politics/trump-south-carolina-primary.html" # General metered
    ]

    for test_url in test_urls_for_paywall:
        print(f"\n--- Testing Full Web Processing for: {test_url} ---")
        fetch_result = http_tool._run(test_url)
        html_doc = None
        extracted_len = -1

        if fetch_result.startswith("Error"):
            print(fetch_result)
            # Try paywall detection even on fetch error if URL seems like a strict domain
            paywall_status_on_error = paywall_tool._run(url=test_url)
            print(f"Paywall (on fetch error): {paywall_status_on_error}")
            continue
        else:
            print(f"Fetched successfully: {test_url}")
            html_doc = fetch_result
        
        if html_doc:
            main_text = trafilatura_tool._run(html_doc, source_url=test_url)
            if main_text:
                extracted_len = len(main_text)
                print(f"Extracted text length: {extracted_len}")
            else:
                print("Trafilatura could not extract main text.")
        
        paywall_status = paywall_tool._run(url=test_url, html_content=html_doc, extracted_text_length=extracted_len)
        print(f"Paywall Detection: {paywall_status}") 