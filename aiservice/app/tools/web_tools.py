# File: aiservice/app/tools/web_content_fetcher_tool.py
"""Tool to fetch and perform initial processing of content from a URL."""

import requests
from bs4 import BeautifulSoup
import trafilatura
from urllib.parse import urljoin, urlparse
import re
import os
import time # Added time for processing_duration, though not explicitly in WebContent model, useful for OptimizedWebExtractionResult style output if desired

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, HttpUrl
from typing import Type, Dict, Optional, Any, List, Union, Set

# --- Configuration Data for Initial URL Filtering (Non-Paywall) ---
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
class FetchedWebImage(BaseModel):
    """Represents an image reference extracted from a web page."""
    url: HttpUrl
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    source_scope: Optional[str] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None

class WebContent(BaseModel):
    """Structured output for content fetched from a web URL."""
    status: str
    original_url: HttpUrl # Changed to HttpUrl for consistency, was str in provided reference
    final_url: Optional[HttpUrl] = None
    page_title: Optional[str] = None
    extracted_text: Optional[str] = None
    images: Optional[List[FetchedWebImage]] = None
    pdf_bytes: Optional[bytes] = None
    error_message: Optional[str] = None
    processing_duration_seconds: Optional[float] = None # Added this field for consistency with previous OptimizedTool


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
    Output is a WebContent Pydantic model, returned as a dictionary via .model_dump().
    """
    name: str = "Web Content Fetcher Tool"
    description: str = (
        "Fetches and processes content from a web URL, including text, image references, and PDF handling. "
        "Applies URL filtering and paywall detection strategies. "
        "Returns a dictionary representing a WebContent object."
    )
    args_schema: Type[BaseModel] = WebContentFetcherToolInput

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

    def _get_contextual_text(self, element, direction="before", max_length=300) -> Optional[str]:
        if not element:
            return None
        context_snippets = []
        start_node = element
        max_parent_ascents = 2 if direction == "before" else 0
        ascents = 0
        effective_max_snippets = 2 if direction == "before" else 1
        while len(context_snippets) < effective_max_snippets and start_node and start_node.name not in ['body', 'html'] and ascents <= max_parent_ascents:
            current_search_node = start_node
            for _ in range(effective_max_snippets - len(context_snippets)):
                sibling = None
                if direction == "before":
                    sibling = current_search_node.find_previous_sibling()
                else:
                    sibling = current_search_node.find_next_sibling()
                if not sibling:
                    break 
                current_search_node = sibling 
                if sibling.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td'] or \
                   (sibling.name == 'div' and sibling.get_text(strip=True)):
                    if sibling.name == 'div' and len(context_snippets) > 0 and len(sibling.get_text(strip=True)) > (max_length * 2):
                        continue
                    text = sibling.get_text(separator=' ', strip=True)
                    if text and len(text) > 5:
                        if direction == "before":
                            context_snippets.insert(0, text)
                        else:
                            context_snippets.append(text)
                        if len(context_snippets) >= effective_max_snippets:
                            break 
            if len(context_snippets) >= effective_max_snippets:
                break 
            if start_node.parent and ascents < max_parent_ascents:
                start_node = start_node.parent
                ascents += 1
            else:
                break 
        if not context_snippets:
            return None
        full_context = " ".join(context_snippets).strip()
        if len(full_context) > max_length:
            if direction == "before":
                return "... " + full_context[-(max_length - 4):] 
            else:
                return full_context[:(max_length - 4)] + " ..."
        return full_context.strip() or None

    def _run(self, url: str) -> Dict[str, Any]: # Changed return type to Dict for .model_dump()
        start_time = time.time() # Start timing
        try:
            original_url_pydantic: HttpUrl = HttpUrl(url)
        except ValueError as ve:
            duration = time.time() - start_time
            # original_url needs to be a HttpUrl for WebContent, but input `url` might be invalid string
            # For this specific error case, we pass the raw string if HttpUrl fails for original_url itself.
            # However, the Pydantic model expects HttpUrl. This is tricky.
            # Safest is to attempt HttpUrl, and if it fails, we can't construct WebContent as per its strict type.
            # Fallback: return a dict that resembles WebContent but original_url as string.
            # This is not ideal but handles very malformed URLs passed to the tool.
            return {
                "status": "fetch_error", 
                "original_url": url, # Pass as string if HttpUrl(url) fails
                "error_message": f"Invalid URL format: {ve}",
                "processing_duration_seconds": duration
            }            

        original_url_str = str(original_url_pydantic)
        current_url_obj = urlparse(original_url_str)
        current_domain = current_url_obj.hostname
        current_path = current_url_obj.path

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
                        error_message="URL points to an unsupported page type (e.g., social media feed, video platform homepage).",
                        processing_duration_seconds = time.time() - start_time
                    ).model_dump()
        
        if self._check_domain_in_set(current_domain, VERY_STRICT_PAYWALL_DOMAINS):
            return WebContent(
                status="strict_paywall_domain",
                original_url=original_url_pydantic,
                final_url=original_url_pydantic,
                error_message="Site (from initial URL) is known to have a strict paywall; fetching not attempted.",
                processing_duration_seconds = time.time() - start_time
            ).model_dump()

        session = requests.Session()
        session.headers.update({
            "User-Agent": "ThinkStashBot/1.0 (compatible; Mozilla/5.0; +http://thinkstash.com/bot)" 
        })
        response: Optional[requests.Response] = None
        final_url_pydantic: Optional[HttpUrl] = original_url_pydantic # Initialize with original
        html_content: Optional[str] = None

        try:
            response = session.get(original_url_str, timeout=(15, 20), allow_redirects=True)
            response.raise_for_status()
            final_url_str = str(response.url)
            final_url_pydantic = HttpUrl(final_url_str)
        except requests.exceptions.Timeout as e:
            return WebContent(status="fetch_error", original_url=original_url_pydantic, error_message=f"Request timed out: {str(e)}", processing_duration_seconds = time.time() - start_time).model_dump()
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
                                return WebContent(status="suspected_paywall_patterns", original_url=original_url_pydantic, final_url=final_url_on_error, page_title=page_title_on_error, extracted_text=error_page_preview, error_message=f"Paywall suspected (keywords) on {e.response.status_code} error page.", processing_duration_seconds = time.time() - start_time).model_dump()
                        for selector in PAYWALL_HTML_SELECTORS:
                            if soup_on_error.select_one(selector):
                                return WebContent(status="suspected_paywall_patterns", original_url=original_url_pydantic, final_url=final_url_on_error, page_title=page_title_on_error, extracted_text=error_page_preview, error_message=f"Paywall suspected (CSS) on {e.response.status_code} error page.", processing_duration_seconds = time.time() - start_time).model_dump()
                except Exception:
                    pass
            return WebContent(status="fetch_error", original_url=original_url_pydantic, final_url=final_url_on_error if final_url_on_error != original_url_pydantic else None, page_title=page_title_on_error, extracted_text=error_page_preview, error_message=f"HTTP error: {e.response.status_code if e.response else 'Unknown'} - {str(e)}", processing_duration_seconds = time.time() - start_time).model_dump()
        except requests.exceptions.RequestException as e:
            return WebContent(status="fetch_error", original_url=original_url_pydantic, error_message=f"Network fetch error: {str(e)}", processing_duration_seconds = time.time() - start_time).model_dump()
        except Exception as e:
            return WebContent(status="fetch_error", original_url=original_url_pydantic, error_message=f"Unexpected error during URL fetching: {str(e)}", processing_duration_seconds = time.time() - start_time).model_dump()

        final_domain_after_redirect = self._get_domain(str(final_url_pydantic))
        if final_domain_after_redirect and final_domain_after_redirect != current_domain:
            if self._check_domain_in_set(final_domain_after_redirect, VERY_STRICT_PAYWALL_DOMAINS):
                return WebContent(status="strict_paywall_domain", original_url=original_url_pydantic, final_url=final_url_pydantic, error_message="Redirected to a site known for a strict paywall.", processing_duration_seconds = time.time() - start_time).model_dump()
        
        content_type_header = response.headers.get('Content-Type', '').lower()
        html_content = response.text

        if 'application/pdf' in content_type_header or str(final_url_pydantic).lower().endswith('.pdf'):
            pdf_title = None
            content_disposition = response.headers.get('Content-Disposition')
            if content_disposition:
                match = re.search(r"filename\*?=['\"]?([^'\"]+)['\"]?", content_disposition, re.IGNORECASE)
                if match: pdf_title = match.group(1)
            if not pdf_title:
                pdf_title = os.path.basename(urlparse(str(final_url_pydantic)).path)
            return WebContent(status="pdf_content_downloaded", original_url=original_url_pydantic, final_url=final_url_pydantic, page_title=pdf_title, pdf_bytes=response.content, processing_duration_seconds = time.time() - start_time).model_dump()

        if not ('text/html' in content_type_header or 'application/xhtml+xml' in content_type_header):
            return WebContent(status="unsupported_content_type", original_url=original_url_pydantic, final_url=final_url_pydantic, error_message=f"Content type '{content_type_header}' is not HTML or PDF.", processing_duration_seconds = time.time() - start_time).model_dump()

        soup = BeautifulSoup(html_content, 'lxml')
        page_title_text = soup.find('title').string.strip() if soup.find('title') else None

        initial_paywall_clues_found = False
        paywall_clue_message = ""
        if html_content:
            for keyword in PAYWALL_KEYWORDS:
                if keyword in html_content.lower():
                    initial_paywall_clues_found = True
                    paywall_clue_message = f"Initial paywall suspected based on keyword: '{keyword}'."
                    break
            if not initial_paywall_clues_found:
                for selector in PAYWALL_HTML_SELECTORS:
                    if soup.select_one(selector):
                        initial_paywall_clues_found = True
                        paywall_clue_message = f"Initial paywall suspected based on CSS selector: '{selector}'."
                        break
        
        main_content_html_segment = None
        extracted_article_text: Optional[str] = None
        image_search_soup = soup

        # Attempt 1: Trafilatura with favor_recall=True, output_format='txt' (more aggressive text grabbing)
        print(f"WebContentFetcherTool: Before Attempt 1 (favor_recall), extracted_article_text is: {'None' if extracted_article_text is None else 'Populated'}")
        try:
            extracted_article_text = trafilatura.extract(
                html_content, 
                url=str(final_url_pydantic), 
                include_comments=False, 
                include_tables=True, 
                favor_recall=True, # Try to get more content
                output_format='txt'
            )
            if extracted_article_text and len(extracted_article_text.strip()) > 100: # Basic check for meaningful content
                print("WebContentFetcherTool: Extracted text with favor_recall=True, output_format='txt'")
            else:
                extracted_article_text = None # Discard if too short or empty
        except Exception as e_recall_txt:
            print(f"WebContentFetcherTool: Error during trafilatura (favor_recall, txt): {e_recall_txt}")
            extracted_article_text = None
        print(f"WebContentFetcherTool: After Attempt 1 (favor_recall), extracted_article_text is: {'None' if extracted_article_text is None else 'Populated'}, Length: {len(extracted_article_text.strip()) if extracted_article_text else 0}")

        # Attempt 2 (Original Pass 1): Trafilatura with favor_precision=True, output_format='html'
        if not extracted_article_text and html_content:
            print(f"WebContentFetcherTool: Before Attempt 2 (precision_html), extracted_article_text is: {'None' if extracted_article_text is None else 'Populated'}")
            try:
                main_content_html_segment = trafilatura.extract(
                    html_content, 
                    url=str(final_url_pydantic), 
                    include_comments=False, 
                    include_tables=True, 
                    output_format='html', 
                    favor_precision=True
                )
                if main_content_html_segment:
                    main_content_soup = BeautifulSoup(main_content_html_segment, 'lxml')
                    temp_extracted_text = main_content_soup.get_text(separator='\n', strip=True)
                    if temp_extracted_text and len(temp_extracted_text.strip()) > 100:
                        extracted_article_text = temp_extracted_text
                        image_search_soup = main_content_soup
                        print("WebContentFetcherTool: Extracted text with favor_precision=True, output_format='html'")
                    else:
                        extracted_article_text = None # Reset if main content segment gave too little text
                        main_content_html_segment = None # Don't use this segment for images if text was poor
            except Exception as e_precision_html:
                print(f"WebContentFetcherTool: Error during trafilatura (favor_precision, html): {e_precision_html}")
                extracted_article_text = None
                main_content_html_segment = None
            print(f"WebContentFetcherTool: After Attempt 2 (precision_html), extracted_article_text is: {'None' if extracted_article_text is None else 'Populated'}, Length: {len(extracted_article_text.strip()) if extracted_article_text else 0}")

        # Attempt 3 (Original Pass 2 - Fallback): Trafilatura with default settings (often txt), if still no text
        if not extracted_article_text and html_content:
            print(f"WebContentFetcherTool: Before Attempt 3 (fallback_txt), extracted_article_text is: {'None' if extracted_article_text is None else 'Populated'}")
            try:
                # This is the original fallback, try with include_tables=True explicitly
                fallback_text = trafilatura.extract(
                    html_content, 
                    url=str(final_url_pydantic), 
                    include_comments=False, 
                    include_tables=True, # Explicitly ensure tables are considered here
                    output_format='txt' # Be explicit for the fallback text attempt
                )
                if fallback_text and len(fallback_text.strip()) > 100:
                    extracted_article_text = fallback_text
                    print("WebContentFetcherTool: Extracted text with fallback trafilatura (txt output)")
                # If this fallback also results in very short text, it might be better to leave extracted_article_text as None
                # so that paywall logic (which checks for short text + keywords) can trigger correctly.
                # No need to set image_search_soup here as it defaults to full soup if main_content_html_segment wasn't successful.
            except Exception as e_fallback_txt:
                print(f"WebContentFetcherTool: Error during fallback trafilatura (txt): {e_fallback_txt}")
                # extracted_article_text remains None or its previous value
            print(f"WebContentFetcherTool: After Attempt 3 (fallback_txt), extracted_article_text is: {'None' if extracted_article_text is None else 'Populated'}, Length: {len(extracted_article_text.strip()) if extracted_article_text else 0}")

        final_paywall_verdict = False
        final_paywall_message = paywall_clue_message
        if initial_paywall_clues_found and not extracted_article_text:
            final_paywall_verdict = True
            final_paywall_message = final_paywall_message or "Initial paywall clues present, and no main content extracted."
        is_short_content = extracted_article_text and len(extracted_article_text) < 300
        if is_short_content:
            keywords_in_short_text = False
            if extracted_article_text: # Ensure extracted_article_text is not None
                for keyword in PAYWALL_KEYWORDS:
                    if keyword in extracted_article_text.lower():
                        keywords_in_short_text = True
                        final_paywall_message = final_paywall_message or f"Paywall keyword '{keyword}' found in short extracted content."
                        break
            if initial_paywall_clues_found or keywords_in_short_text:
                final_paywall_verdict = True
        
        if final_paywall_verdict:
            preview_text = extracted_article_text if extracted_article_text and len(extracted_article_text) > 50 else (html_content[:1000] if html_content else None)
            return WebContent(status="error_paywall", original_url=original_url_pydantic, final_url=final_url_pydantic, page_title=page_title_text, extracted_text=preview_text, error_message=f"Paywall confirmed or strongly suspected. Details: {final_paywall_message}", processing_duration_seconds = time.time() - start_time).model_dump()

        images_found: List[FetchedWebImage] = []
        processed_image_urls: Set[str] = set()

        def process_image_tag(img_tag_local, is_in_main_content_scope: bool) -> Optional[FetchedWebImage]:
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
                for parent_tag in img_tag_local.parents:
                    if parent_tag.name in ['header', 'footer', 'nav', 'aside', 'sidebar', 'menu']:
                        return None
                    if parent_tag.name == 'body': break # Stop at body
            alt_text_val = img_tag_local.get('alt', '').strip() or None
            title_attr_text_val = img_tag_local.get('title', '').strip() or None
            caption_text_val: Optional[str] = None
            parent_figure = img_tag_local.find_parent('figure')
            figure_context_element = parent_figure if parent_figure else (img_tag_local.parent if img_tag_local.parent and img_tag_local.parent.name != 'a' else img_tag_local)
            if parent_figure:
                figcaption = parent_figure.find('figcaption')
                if figcaption: caption_text_val = figcaption.get_text(strip=True)
            
            context_before_text = self._get_contextual_text(figure_context_element, direction="before")
            context_after_text = self._get_contextual_text(figure_context_element, direction="after")

            if not caption_text_val:
                # Simplified caption logic for brevity, assuming original intent
                current_element_for_caption = img_tag_local.parent if img_tag_local.parent and img_tag_local.parent.name != 'a' else img_tag_local
                if current_element_for_caption:
                    next_sibling_p = current_element_for_caption.find_next_sibling('p')
                    if next_sibling_p and any(cls in next_sibling_p.get('class', []) for cls in ['caption', 'wp-caption-text']):
                        caption_text_val = next_sibling_p.get_text(strip=True)
            if not caption_text_val and title_attr_text_val: caption_text_val = title_attr_text_val
            elif not caption_text_val and alt_text_val and len(alt_text_val.split()) > 3 and len(alt_text_val) > 20: caption_text_val = alt_text_val
            
            processed_image_urls.add(str(validated_img_url))
            return FetchedWebImage(
                url=validated_img_url, 
                alt_text=alt_text_val, 
                caption=caption_text_val, 
                source_scope = "main_content" if is_in_main_content_scope else "full_page_heuristic",
                context_before=context_before_text,
                context_after=context_after_text
            )

        if image_search_soup: # Check if image_search_soup is not None
            scope_is_main = (image_search_soup != soup) # True if image_search_soup is main_content_soup
            for img_tag in image_search_soup.find_all('img'):
                fetched_image = process_image_tag(img_tag, is_in_main_content_scope=scope_is_main)
                if fetched_image: images_found.append(fetched_image)
            # If we searched only main_content_soup and found few/no images, consider a second pass on full soup
            if scope_is_main and len(images_found) < 3 : # Arbitrary threshold
                 for img_tag in soup.find_all('img'): # Search full soup
                    fetched_image = process_image_tag(img_tag, is_in_main_content_scope=False)
                    if fetched_image: images_found.append(fetched_image)

        if not extracted_article_text and not images_found:
             print(f"WebContentFetcherTool: Returning parse_error. extracted_article_text is {'None' if extracted_article_text is None else 'Populated'}. images_found: {len(images_found)}")
             return WebContent(status="parse_error", original_url=original_url_pydantic, final_url=final_url_pydantic, page_title=page_title_text, error_message="Trafilatura and BeautifulSoup could not extract significant text or images.", processing_duration_seconds = time.time() - start_time).model_dump()

        print(f"WebContentFetcherTool: Returning success. extracted_article_text is {'None' if extracted_article_text is None else 'Populated'}. Length: {len(extracted_article_text.strip()) if extracted_article_text else 0}")
        return WebContent(
            status="success", original_url=original_url_pydantic, final_url=final_url_pydantic, 
            page_title=page_title_text, extracted_text=extracted_article_text, 
            images=images_found if images_found else None,
            processing_duration_seconds = time.time() - start_time
        ).model_dump()

# Example Usage (for direct tool testing)
if __name__ == '__main__':
    tool = WebContentFetcherTool()
    test_urls = [
        "https://www.deeplearning.ai/the-batch/issue-301/",
        "https://www.wsj.com/articles/some-article", # Strict paywall
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ", # Unsupported type
        "https://www.nytimes.com/2023/10/26/business/media/new-york-times-earnings.html", # Metered paywall (might get some content)
        "https://www.example.com/nonexistentpage123.html", # Fetch error (404)
        "http://example.com/document.pdf" # Test PDF
    ]
    for test_url in test_urls:
        print(f"\n--- Testing WebContentFetcherTool for: {test_url} ---")
        result = tool._run(url=test_url)
        import json
        print(json.dumps(result, indent=2, default=str)) # Use default=str for HttpUrl, bytes, etc.
        if result.get("status") == "success":
            if result.get("extracted_text"):
                print(f"  Extracted Text Snippet: {result['extracted_text'][:200]}...")
            if result.get("images"):
                print(f"  Found {len(result['images'])} images. First one: {result['images'][0] if result['images'] else 'N/A'}")
        elif result.get("status") == "pdf_content_downloaded":
            print(f"  PDF content downloaded, bytes length: {len(result.get('pdf_bytes', b''))}") 