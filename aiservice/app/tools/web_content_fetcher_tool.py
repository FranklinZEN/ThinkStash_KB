# File: aiservice/app/tools/web_content_fetcher_tool.py
"""Tool to fetch and perform initial processing of content from a URL."""

import requests
from bs4 import BeautifulSoup
import trafilatura
from urllib.parse import urljoin, urlparse
import re
import os

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, HttpUrl
from typing import Type, Dict, Optional, Any, List, Union, Set

# --- Configuration Data for Initial URL Filtering (Non-Paywall) ---
# As per TS-AI-4 & TS-AI-4.5 Development Plan - V1.2, TS-AI-4.1, Step 2.b (implicitly, as it's part of the tool's responsibility)
# and matching similar previous definitions.
UNSUPPORTED_URL_TYPE_DOMAINS: Set[str] = {
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com", "twitch.tv", 
    "bitchute.com", "rumble.com", # Video platforms
    "facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com", "tiktok.com", # Social media platforms
    "reddit.com" # Community/Social platform
}

UNSUPPORTED_URL_PATH_PATTERNS: List[str] = [
    r"^/feed/?(.*)?$", r"^/home/?(.*)?$", r"^/explore/?(.*)?$",
    r"^/notifications/?(.*)?$", r"^/messages/?(.*)?$",
    r"^/i/flow/login/?(.*)?$", r"^/intent/tweet/?(.*)?$",
    r"^/r/[^/]+/?$", r"^/user/[^/]+/?$" 
]

ALLOWED_SOCIAL_MEDIA_POST_PATTERNS: List[str] = [
    r"linkedin.com/pulse/", r"linkedin.com/posts/", 
    r"linkedin.com/feed/update/urn:li:activity:", r"linkedin.com/news/story/",
    r"x.com/(?:[^/]+)/status/", r"twitter.com/(?:[^/]+)/status/",
    r"reddit.com/r/(?:[^/]+)/comments/(?:[^/]+)/", # Covers posts with or without title in path
    r"facebook.com/(?:[^/]+)/posts/(?:[^/]+)", r"facebook.com/notes/(?:[^/]+)/(?:[^/]+)/(?:[^/]+)"
]

# --- Configuration Data for Paywall Strategy ---
# As per TS-AI-4 & TS-AI-4.5 Development Plan - V1.2, TS-AI-4.1, Step 2.d
VERY_STRICT_PAYWALL_DOMAINS: Set[str] = {
    "wsj.com", "ft.com", "thetimes.co.uk", "thesundaytimes.co.uk", "barrons.com",
    "theathletic.com", "statista.com", "digiday.com", "adweek.com", "stratechery.com",
    "sciencedirect.com", "link.springer.com", "onlinelibrary.wiley.com", "tandfonline.com",
    "jamanetwork.com", "nejm.org", "thelancet.com", "cell.com", "nature.com", "science.org",
    "ieeexplore.ieee.org", "jstor.org", "academic.oup.com", "cambridge.org/core"
}

GENERAL_METERED_PAYWALL_DOMAINS: Set[str] = { # Currently used implicitly by not being in strict list + keyword/selector scan
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


# --- Pydantic Models for WebContentFetcherTool Output ---
# As per TS-AI-4 & TS-AI-4.5 Development Plan - V1.2, TS-AI-4.1 (Tool Output)
class FetchedWebImage(BaseModel):
    """Represents an image reference extracted from a web page."""
    url: HttpUrl
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    source_scope: Optional[str] = None # New: e.g., "main_content", "full_page_heuristic"
    # New fields for contextual snippets around the image
    context_before: Optional[str] = None # Text immediately preceding the image block
    context_after: Optional[str] = None  # Text immediately following the image block

class WebContent(BaseModel):
    """Structured output for content fetched from a web URL."""
    # Status values based on V1.2 plan for the tool's direct output
    status: str  # Expected: "success", "unsupported_url_type", "strict_paywall_domain", "suspected_paywall_patterns", "error_paywall", "unsupported_content_type", "pdf_content_downloaded", "fetch_error", "parse_error"
    original_url: HttpUrl
    final_url: Optional[HttpUrl] = None
    page_title: Optional[str] = None
    extracted_text: Optional[str] = None
    images: Optional[List[FetchedWebImage]] = None
    pdf_bytes: Optional[bytes] = None
    error_message: Optional[str] = None


# --- Tool Input Schema ---
class WebContentFetcherToolInput(BaseModel):
    """Input schema for the WebContentFetcherTool."""
    url: str = Field(..., description="The URL of the web page to fetch content from.")


# --- WebContentFetcherTool Implementation ---
class WebContentFetcherTool(BaseTool):
    """
    A tool to fetch, parse, and perform initial processing of content from a web URL.
    It implements URL type filtering, tiered paywall detection, PDF handling,
    and extracts text, images (references), and captions.
    Output is a WebContent Pydantic model.
    """
    name: str = "Web Content Fetcher Tool"
    description: str = (
        "Fetches and processes content from a web URL, including text, image references, and PDF handling. "
        "Applies URL filtering and paywall detection strategies."
    )
    args_schema: Type[BaseModel] = WebContentFetcherToolInput

    # Helper method to get domain from URL
    def _get_domain(self, url_str: str) -> Optional[str]:
        try:
            return urlparse(url_str).hostname
        except Exception:
            return None

    # Helper method to check domain against a set (handles subdomains)
    def _check_domain_in_set(self, domain: Optional[str], domain_set: Set[str]) -> bool:
        if not domain:
            return False
        domain_lower = domain.lower()
        for item_in_set in domain_set:
            if domain_lower == item_in_set or domain_lower.endswith("." + item_in_set):
                return True
        return False

    def _get_contextual_text(self, element, direction="before", max_length=300) -> Optional[str]:
        """Refined helper to get text primarily from the single closest preceding or succeeding text block."""
        if not element:
            return None

        context_snippets = []
        
        start_node = element
        max_parent_ascents = 2 if direction == "before" else 0 # More ascent for 'before', minimal for 'after'
        ascents = 0
        
        # For 'before', we aim for 1-2 good preceding snippets.
        # For 'after', we primarily want the single immediately succeeding snippet.
        effective_max_snippets = 2 if direction == "before" else 1

        while len(context_snippets) < effective_max_snippets and start_node and start_node.name not in ['body', 'html'] and ascents <= max_parent_ascents:
            current_search_node = start_node
            sibling_found_this_level = False

            # Try to collect up to effective_max_snippets at the current DOM level (and its siblings)
            for _ in range(effective_max_snippets - len(context_snippets)):
                sibling = None
                if direction == "before":
                    sibling = current_search_node.find_previous_sibling()
                else: # "after"
                    sibling = current_search_node.find_next_sibling()

                if not sibling:
                    break 
                
                current_search_node = sibling 

                if sibling.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td'] or \
                   (sibling.name == 'div' and sibling.get_text(strip=True)):
                    # Basic heuristic to avoid overly long, likely irrelevant divs unless they are the only option
                    if sibling.name == 'div' and len(context_snippets) > 0 and len(sibling.get_text(strip=True)) > (max_length * 2):
                        continue # Skip very long div if we already have some context

                    text = sibling.get_text(separator=' ', strip=True)
                    if text and len(text) > 5: # Filter for slightly more meaningful text snippets
                        if direction == "before":
                            context_snippets.insert(0, text)
                        else:
                            context_snippets.append(text)
                        sibling_found_this_level = True
                        if len(context_snippets) >= effective_max_snippets:
                            break 
            
            if len(context_snippets) >= effective_max_snippets:
                break 

            if start_node.parent and ascents < max_parent_ascents: # Check ascents before using parent
                start_node = start_node.parent
                ascents += 1
            else:
                break 
        
        if not context_snippets:
            return None

        full_context = " ".join(context_snippets).strip()
        
        # Truncation and Ellipses
        if len(full_context) > max_length:
            if direction == "before":
                return "... " + full_context[-(max_length - 4):] 
            else:
                return full_context[:(max_length - 4)] + " ..."
        
        return full_context.strip() or None

    def _run(self, url: str) -> WebContent:
        """The main execution method for the tool."""
        
        # Scheme prepending is now handled by the ContentAcquisitionAgent before calling this tool.
        # The input `url` is expected to be a valid URL string with a scheme.

        # Validate input URL with Pydantic early (HttpUrl handles basic validation)
        try:
            original_url_pydantic: HttpUrl = HttpUrl(url)
            original_url_str = str(original_url_pydantic)
        except ValueError as ve:
            # This validation is still useful as a safeguard within the tool itself,
            # though the agent should have caught most issues.
            return WebContent(status="fetch_error", original_url=url, error_message=f"Invalid URL format received by tool: {ve}")

        current_url_obj = urlparse(original_url_str)
        current_domain = current_url_obj.hostname
        current_path = current_url_obj.path

        # 1. Initial URL Type Filtering (before HTTP request)
        if self._check_domain_in_set(current_domain, UNSUPPORTED_URL_TYPE_DOMAINS):
            is_allowed_social_post = False
            for pattern in ALLOWED_SOCIAL_MEDIA_POST_PATTERNS:
                if re.search(pattern, original_url_str, re.IGNORECASE):
                    is_allowed_social_post = True
                    break
            if not is_allowed_social_post:
                is_unsupported_path = False
                for pattern in UNSUPPORTED_URL_PATH_PATTERNS:
                    if re.search(pattern, current_path, re.IGNORECASE):
                        is_unsupported_path = True
                        break
                if is_unsupported_path or not is_allowed_social_post:
                    return WebContent(
                        status="unsupported_url_type",
                        original_url=original_url_pydantic,
                        error_message="URL points to an unsupported page type (e.g., social media feed, video platform homepage)."
                    )
        
        # 2. Tier 1 Paywall Check (Strict Domains - Pre-Request)
        if self._check_domain_in_set(current_domain, VERY_STRICT_PAYWALL_DOMAINS):
            return WebContent(
                status="strict_paywall_domain",
                original_url=original_url_pydantic,
                final_url=original_url_pydantic, 
                error_message="Site (from initial URL) is known to have a strict paywall; fetching not attempted."
            )

        # 3. HTTP Request Handling
        session = requests.Session()
        session.headers.update({
            "User-Agent": "ThinkStashBot/1.0 (compatible; Mozilla/5.0; +http://thinkstash.com/bot)" 
        })
        response: Optional[requests.Response] = None
        final_url_pydantic: Optional[HttpUrl] = None
        html_content: Optional[str] = None

        try:
            response = session.get(original_url_str, timeout=(15, 20), allow_redirects=True)
            response.raise_for_status()
            final_url_str = str(response.url)
            final_url_pydantic = HttpUrl(final_url_str)

        except requests.exceptions.Timeout as e:
            return WebContent(status="fetch_error", original_url=original_url_pydantic, error_message=f"Request timed out: {str(e)}")
        except requests.exceptions.HTTPError as e:
            page_title_on_error = None
            error_page_preview = None
            final_url_on_error = HttpUrl(str(e.response.url)) if e.response and e.response.url else original_url_pydantic
            if e.response is not None and e.response.text:
                error_page_preview = e.response.text[:2500]
                try:
                    soup_on_error = BeautifulSoup(e.response.text, 'lxml')
                    title_tag_on_error = soup_on_error.find('title')
                    if title_tag_on_error: page_title_on_error = title_tag_on_error.string.strip()
                    if e.response.status_code in [401, 403, 451]:
                        for keyword in PAYWALL_KEYWORDS:
                            if keyword in e.response.text.lower():
                                return WebContent(status="suspected_paywall_patterns", original_url=original_url_pydantic, final_url=final_url_on_error, page_title=page_title_on_error, extracted_text=error_page_preview, error_message=f"Paywall suspected (keywords) on {e.response.status_code} error page.")
                        for selector in PAYWALL_HTML_SELECTORS:
                            if soup_on_error.select_one(selector):
                                return WebContent(status="suspected_paywall_patterns", original_url=original_url_pydantic, final_url=final_url_on_error, page_title=page_title_on_error, extracted_text=error_page_preview, error_message=f"Paywall suspected (CSS) on {e.response.status_code} error page.")
                except Exception: # BeautifulSoup parsing error on error page
                    pass # Continue to return generic fetch_error
            return WebContent(status="fetch_error", original_url=original_url_pydantic, final_url=final_url_on_error if final_url_on_error != original_url_pydantic else None, page_title=page_title_on_error, extracted_text=error_page_preview, error_message=f"HTTP error: {e.response.status_code if e.response else 'Unknown'} - {str(e)}")
        except requests.exceptions.RequestException as e:
            return WebContent(status="fetch_error", original_url=original_url_pydantic, error_message=f"Network fetch error: {str(e)}")
        except Exception as e:
            return WebContent(status="fetch_error", original_url=original_url_pydantic, error_message=f"Unexpected error during URL fetching: {str(e)}")

        # --- Post-Request Processing ---
        final_domain = self._get_domain(str(final_url_pydantic))
        if final_domain and final_domain != current_domain: # Re-check Tier 1 if redirected
            if self._check_domain_in_set(final_domain, VERY_STRICT_PAYWALL_DOMAINS):
                return WebContent(status="strict_paywall_domain", original_url=original_url_pydantic, final_url=final_url_pydantic, error_message="Redirected to a site known for a strict paywall.")
        
        content_type_header = response.headers.get('Content-Type', '').lower()
        html_content = response.text

        # 4. Content-Type & PDF Detection
        if 'application/pdf' in content_type_header or str(final_url_pydantic).lower().endswith('.pdf'):
            pdf_title = None
            content_disposition = response.headers.get('Content-Disposition')
            if content_disposition:
                match = re.search(r"filename\*?=['\"]?([^'\"]+)['\"]?", content_disposition, re.IGNORECASE)
                if match: pdf_title = match.group(1)
            if not pdf_title:
                pdf_title = os.path.basename(urlparse(str(final_url_pydantic)).path)
            return WebContent(status="pdf_content_downloaded", original_url=original_url_pydantic, final_url=final_url_pydantic, page_title=pdf_title, pdf_bytes=response.content)

        if not ('text/html' in content_type_header or 'application/xhtml+xml' in content_type_header):
            return WebContent(status="unsupported_content_type", original_url=original_url_pydantic, final_url=final_url_pydantic, error_message=f"Content type '{content_type_header}' is not HTML or PDF.")

        # --- HTML Processing Starts Here (after PDF and non-HTML content type checks) ---
        soup = BeautifulSoup(html_content, 'lxml')
        page_title_text = soup.find('title').string.strip() if soup.find('title') else None

        # Tier 2 Paywall Scan (Keywords & Selectors on fetched HTML) - Gathers initial clues
        initial_paywall_clues_found = False
        paywall_clue_message = ""
        # Only scan if html_content is not None (it should be if we reached here)
        if html_content:
            for keyword in PAYWALL_KEYWORDS:
                if keyword in html_content.lower():
                    initial_paywall_clues_found = True
                    paywall_clue_message = f"Initial paywall suspected based on keyword: '{keyword}'."
                    break
            if not initial_paywall_clues_found:
                for selector in PAYWALL_HTML_SELECTORS:
                    if soup.select_one(selector): # soup is the full page soup
                        initial_paywall_clues_found = True
                        paywall_clue_message = f"Initial paywall suspected based on CSS selector: '{selector}'."
                        break
        
        # Always proceed to Trafilatura if not caught by Tier 0 (URL type) or Tier 1 (Strict Paywall)
        # The initial_paywall_clues_found will inform the Tier 3 decision.

        # 6. Main Article Text Extraction (Trafilatura)
        main_content_html_segment = trafilatura.extract(html_content, url=str(final_url_pydantic), include_comments=False, include_tables=True, output_format='html', favor_precision=True)
        
        extracted_article_text: Optional[str] = None
        image_search_soup = soup # Default to full page soup for images for now

        if main_content_html_segment:
            main_content_soup = BeautifulSoup(main_content_html_segment, 'lxml')
            temp_extracted_text = main_content_soup.get_text(separator='\n', strip=True)
            if temp_extracted_text:
                extracted_article_text = temp_extracted_text
                image_search_soup = main_content_soup # Prefer images from main content if text is extracted from it
        
        if not extracted_article_text and html_content: # Fallback to text from full HTML if main segment yielded no text
            extracted_article_text = trafilatura.extract(html_content, url=str(final_url_pydantic), include_comments=False, include_tables=True, output_format='text')
            # image_search_soup remains full page soup here

        # 7. Tier 3 Paywall Decision (Post-Extraction - informed by initial clues and extracted content quality)
        final_paywall_verdict = False
        final_paywall_message = paywall_clue_message # Carry over initial clue message

        # Condition 1: Initial clues were found, AND Trafilatura got no text at all.
        if initial_paywall_clues_found and not extracted_article_text:
            final_paywall_verdict = True
            final_paywall_message = final_paywall_message or "Initial paywall clues present, and no main content extracted."
        
        # Condition 2: Extracted text is very short AND (initial clues were found OR keywords are in the short extracted text itself)
        is_short_content = extracted_article_text and len(extracted_article_text) < 300 # Threshold for "short"
        if is_short_content:
            keywords_in_short_text = False
            for keyword in PAYWALL_KEYWORDS:
                if extracted_article_text and keyword in extracted_article_text.lower():
                    keywords_in_short_text = True
                    final_paywall_message = final_paywall_message or f"Paywall keyword '{keyword}' found in short extracted content."
                    break
            if initial_paywall_clues_found or keywords_in_short_text:
                final_paywall_verdict = True
        
        if final_paywall_verdict:
            # Provide some of html_content as preview if extracted_article_text is None or too short
            preview_text = extracted_article_text if extracted_article_text and len(extracted_article_text) > 50 else (html_content[:1000] if html_content else None)
            return WebContent(status="error_paywall", 
                              original_url=original_url_pydantic, 
                              final_url=final_url_pydantic, 
                              page_title=page_title_text, 
                              extracted_text=preview_text, 
                              error_message=f"Paywall confirmed or strongly suspected. Details: {final_paywall_message}")

        # 8. Hybrid Image & Caption Extraction
        images_found: List[FetchedWebImage] = []
        processed_image_urls: Set[str] = set()

        def process_image_tag(img_tag_local, is_in_main_content_scope: bool) -> Optional[FetchedWebImage]:
            # ... (src, data-src, data-original logic) ...
            # ... (URL validation, duplicate check) ...
            # ... (Filtering logic based on min_dimension, which uses is_in_main_content_scope) ...
            # ... (Parent tag check for non-main content scope) ...
            # ... (Alt text, caption extraction logic) ...
            
            # Determine source_scope string
            scope_str = "main_content" if is_in_main_content_scope else "full_page_heuristic"
            
            # Ensure all variables for FetchedWebImage are defined here before returning
            # src, validated_img_url, alt_text, caption_text
            # ... (full existing logic from process_image_tag) ...
            src = img_tag_local.get('src')
            if not src: src = img_tag_local.get('data-src')
            if not src: src = img_tag_local.get('data-original')
            if not src or src.startswith('data:image'): return None
            try:
                img_url_absolute = urljoin(str(final_url_pydantic), src.strip())
                validated_img_url = HttpUrl(img_url_absolute)
                if str(validated_img_url) in processed_image_urls: return None
            except ValueError: return None
            min_dimension = 50 if is_in_main_content_scope else 75
            img_width_attr = img_tag_local.get('width'); img_height_attr = img_tag_local.get('height')
            try:
                if img_width_attr and img_width_attr.isdigit() and int(img_width_attr) < min_dimension: return None
                if img_height_attr and img_height_attr.isdigit() and int(img_height_attr) < min_dimension: return None
                style = img_tag_local.get('style', '')
                if 'width:' in style and 'px' in style:
                    w_match = re.search(r'width:\s*(\d+)px', style)
                    if w_match and int(w_match.group(1)) < min_dimension: return None
                if 'height:' in style and 'px' in style:
                    h_match = re.search(r'height:\s*(\d+)px', style)
                    if h_match and int(h_match.group(1)) < min_dimension: return None
            except ValueError: pass
            if '.gif' in str(validated_img_url).lower() and ('spacer' in str(validated_img_url).lower() or 'pixel' in str(validated_img_url).lower()): return None
            if 'wp-content/uploads/sites/' in str(validated_img_url) and ('-1x1-' in str(validated_img_url) or '-20x20-' in str(validated_img_url)): return None
            if ('gravatar.com/avatar/' in str(validated_img_url) or '/profile_images/' in str(validated_img_url)) and any(s_param in str(validated_img_url) for s_param in ['s=20', 's=32', 's=40', 's=50']): return None
            if not is_in_main_content_scope:
                for parent in img_tag_local.parents:
                    if parent.name in ['header', 'footer', 'nav', 'aside', 'sidebar', 'menu']:
                        return None
                    if parent.name == 'body': break
            alt_text_val = img_tag_local.get('alt', '').strip() or None # Renamed to avoid conflict
            title_attr_text_val = img_tag_local.get('title', '').strip() or None # Renamed
            caption_text_val: Optional[str] = None # Renamed
            parent_figure = img_tag_local.find_parent('figure')
            if parent_figure:
                figcaption = parent_figure.find('figcaption')
                if figcaption: caption_text_val = figcaption.get_text(strip=True)
                # Context for figure images: text within the figure, excluding figcaption itself
                figure_context_element = parent_figure
            else:
                # Context for non-figure images: typically parent element if it's a block, or img_tag_local itself
                figure_context_element = img_tag_local.parent if img_tag_local.parent and img_tag_local.parent.name != 'a' else img_tag_local
            
            # Get contextual text snippets
            context_before_text = self._get_contextual_text(figure_context_element, direction="before")
            context_after_text = self._get_contextual_text(figure_context_element, direction="after")

            # (Caption logic - slightly simplified here for brevity, assuming it populates caption_text_val)
            if not caption_text_val:
                for el in [img_tag_local.parent, img_tag_local]: # ... (full caption logic) ...
                    if el:
                        next_s = el.find_next_sibling()
                        if next_s and next_s.name == 'p':
                            p_classes = next_s.get('class', [])
                            common_cap_classes = {'caption', 'wp-caption-text', 'image-caption', 'text-caption'}
                            if any(c_class in p_classes for c_class in common_cap_classes):
                                caption_text_val = next_s.get_text(strip=True); break
                        if el.parent and el.parent.name not in ['body', 'html']:
                            next_s_of_parent = el.parent.find_next_sibling()
                            if next_s_of_parent and next_s_of_parent.name == 'p':
                                p_classes_parent_s = next_s_of_parent.get('class', [])
                                if any(c_class in p_classes_parent_s for c_class in common_cap_classes):
                                    caption_text_val = next_s_of_parent.get_text(strip=True); break
                    if caption_text_val: break
            if not caption_text_val and title_attr_text_val: caption_text_val = title_attr_text_val
            elif not caption_text_val and alt_text_val and len(alt_text_val.split()) > 3 and len(alt_text_val) > 20: caption_text_val = alt_text_val
            
            processed_image_urls.add(str(validated_img_url))
            return FetchedWebImage(
                url=validated_img_url, 
                alt_text=alt_text_val, 
                caption=caption_text_val, 
                source_scope=scope_str,
                context_before=context_before_text,
                context_after=context_after_text
            )

        if main_content_soup:
            for img_tag_main in main_content_soup.find_all('img'):
                fetched_image = process_image_tag(img_tag_main, is_in_main_content_scope=True)
                if fetched_image: images_found.append(fetched_image)
        
        for img_tag_full in soup.find_all('img'):
            fetched_image = process_image_tag(img_tag_full, is_in_main_content_scope=False)
            if fetched_image: images_found.append(fetched_image)

        if not extracted_article_text and not images_found:
             return WebContent(status="parse_error", original_url=original_url_pydantic, final_url=final_url_pydantic, page_title=page_title_text, error_message="Trafilatura and BeautifulSoup could not extract significant text or images.")

        return WebContent(
            status="success", original_url=original_url_pydantic, final_url=final_url_pydantic, 
            page_title=page_title_text, extracted_text=extracted_article_text, 
            images=images_found if images_found else None
        )

# Note: __main__ block for testing would go here. It's omitted for brevity in this step,
# but should be added based on previous versions for direct tool testing. 