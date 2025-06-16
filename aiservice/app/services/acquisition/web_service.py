import asyncio
import hashlib
import time
import aiohttp
from bs4 import BeautifulSoup, Tag, Comment
import trafilatura
from urllib.parse import urljoin, urlparse
import re
import os
import uuid
from typing import Type, Dict, Optional, Any, List, Union, Set, Tuple
import functools
import json
from datetime import datetime
import tempfile # Added for temporary file handling
import logging # Added logging
import httpx
from trafilatura.settings import use_config as use_trafilatura_config
from playwright.async_api import async_playwright # Added Playwright

from pydantic import BaseModel, Field, HttpUrl

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput
from aiservice.app.config.settings import Settings, WebServiceSpecificSettings
from aiservice.app.config.logging_config import get_logger

# --- Pydantic Models for WebAcquisitionService ---

class WebAcquisitionServiceInput(BaseModel):
    url: str = Field(..., description="The URL to fetch and process.")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images. 'full_content' enables image extraction.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking or unique ID generation.")
    user_id: Optional[str] = None # Added user_id

# --- Configuration Data (adapted from WebContentFetcherTool) ---
UNSUPPORTED_URL_TYPE_DOMAINS: Set[str] = {
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com", "twitch.tv",
    "bitchute.com", "rumble.com",
    "facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com", "tiktok.com",
    "reddit.com"
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
    r"reddit.com/r/(?:[^/]+)/comments/(?:[^/]+)/",
    r"facebook.com/(?:[^/]+)/posts/(?:[^/]+)", r"facebook.com/notes/(?:[^/]+)/(?:[^/]+)/(?:[^/]+)"
]
VERY_STRICT_PAYWALL_DOMAINS: Set[str] = {
    "wsj.com", "ft.com", "thetimes.co.uk", "thesundaytimes.co.uk", "barrons.com",
    "theathletic.com", "statista.com", "digiday.com", "adweek.com", "stratechery.com",
    "sciencedirect.com", "link.springer.com", "onlinelibrary.wiley.com", "tandfonline.com",
    "jamanetwork.com", "nejm.org", "thelancet.com", "cell.com", "nature.com", "science.org",
    "ieeexplore.ieee.org", "jstor.org", "academic.oup.com", "cambridge.org/core"
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

BOILERPLATE_SELECTORS: List[str] = [
    "nav", "footer", "header", "aside",
    "[role='navigation']", "[role='banner']", "[role='complementary']", "[role='contentinfo']",
    ".cookie", "#cookie", "[class*='cookie']", "[id*='cookie']",
    ".sidebar", "#sidebar", "[class*='sidebar']", "[id*='sidebar']",
    ".menu", "#menu", "[class*='menu']", "[id*='menu']",
    ".nav", "#nav", "[class*='nav']", "[id*='nav']",
    ".advertisement", ".ad", "[class*='advertisement']", "[class*='ad-']", "[id*='ad-']",
    ".modal", "#modal", "[class*='modal']", "[id*='modal']", # Common for pop-ups
    ".comments", "#comments",
    ".related-posts", ".related-articles",
    ".social-links", ".share-buttons",
    "form[action*='subscribe']",
    # Added for more specific boilerplate removal based on user feedback
    ".site-header", # Common class for main site headers
    ".site-footer", # Common class for main site footers
    "[class*='language-selector']", # For language selection elements
    "[class*='social-share']", # For social media sharing bars/widgets
    "[class*='signup-prompt']", # For newsletter/account signup prompts
    "[class*='cookie-banner']", # More specific targeting for cookie consent banners
    ".nav-primary", # Often used for primary navigation menus
    ".nav-secondary", # Often used for secondary or utility navigation
    ".global-header", # Common pattern for site-wide headers
    ".global-footer",  # Common pattern for site-wide footers
    # More additions based on specific user feedback for Uber blog
    "a[data-baseweb='button'][href*='m.uber.com/looking']", # Specific 'Request a ride' buttons
    "div.bd.ed.n0.bu.bv.iy.n1.fs.fr.n2", # Specific class for author/meta block on Uber blog
    "[class*='author-bio']", # Generic author bio sections
    "[class*='post-meta']",  # Generic post metadata sections (often includes date, author, cats)
    "[class*='entry-meta']", # Another common pattern for entry metadata
    "[class*='byline']",     # For author bylines
    # Speculative additions for top banners
    "div[role='banner']",
    "div[data-testid='banner']",
    "div[class*='site-banner']",
    "div[class*='top-banner']",
    "div[id*='banner']"
]

# PDF processing library (PyMuPDF) - fitz import is no longer needed here if _parse_pdf_content_to_preliminary_blocks is removed
# import fitz # PyMuPDF # This can be removed if not used elsewhere in this file.

logger = logging.getLogger(__name__)

# Define default headers including a common User-Agent
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
    # "Accept-Encoding": "gzip, deflate, br", # httpx handles this by default
}

class WebAcquisitionService(BaseService):
    """
    Asynchronous service to fetch, parse, and extract content from web URLs.
    Outputs PreliminaryBlock, DocumentMetadata, and RawImageInput.
    """

    # Define selectors for main content identification
    MAIN_CONTENT_SELECTORS: List[str] = [
        "article", "main", "[role='main']", # Standard tags
        "#main", "#content", "#body", # Common IDs
        ".main-content", ".post", ".article", # Common classes
        "#article-body", ".article-body",
        ".post-content", ".entry-content",
        ".blog-post", # Common class
        ".text" # Sometimes used for main text container
    ]

    def __init__(self, settings: Optional[Settings] = None):
        super().__init__(settings)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        if settings and settings.web_service:
            self.service_settings: WebServiceSpecificSettings = settings.web_service
        else:
            self.service_settings: WebServiceSpecificSettings = WebServiceSpecificSettings()

        self.headers = {
            "User-Agent": self.service_settings.default_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1", 
            "Upgrade-Insecure-Requests": "1"
        }
        request_timeout_seconds = self.settings.default_request_timeout_seconds if self.settings else 30
        self.httpx_timeout = httpx.Timeout(request_timeout_seconds)
        
        self.TEXT_CONTAINER_TAGS = {'p', 'div', 'span', 'td', 'th', 'li', 'caption', 'article', 'section', 'main', 'blockquote', 'details', 'summary', 'aside', 'figure', 'figcaption'}
        self.HEADING_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
        self.LIST_TAGS = {'ul', 'ol'}
        self.TABLE_TAGS = {'table', 'tbody', 'thead', 'tfoot', 'tr'}
        self.CODE_TAGS = {'pre', 'code'} 
        self.STRUCTURE_BREAK_TAGS = {'hr', 'br'}

        self.processed_image_urls: Set[str] = set()
        self.stop_headings: Set[str] = {h.lower().strip() for h in self.service_settings.stop_processing_heading_texts}
        self.logger.debug(f"Loaded stop_processing_heading_texts: {self.stop_headings}")

        self.html_cache: Dict[str, Tuple[str, float]] = {}
        if settings and hasattr(settings, 'web_html_cache_ttl_seconds'):
             self.cache_ttl_seconds: int = settings.web_html_cache_ttl_seconds
        elif hasattr(self.service_settings, 'web_html_cache_ttl_seconds'):
             self.cache_ttl_seconds: int = self.service_settings.web_html_cache_ttl_seconds
        else:
            self.cache_ttl_seconds: int = 3600

        self.trafilatura_config = use_trafilatura_config()
        self.trafilatura_config.set("DEFAULT", "EXTRACTION_TIMEOUT", str(settings.default_request_timeout_seconds // 2 if settings and settings.default_request_timeout_seconds > 4 else 2))

    def _get_domain(self, url_str: str) -> Optional[str]:
        try:
            return urlparse(url_str).hostname
        except Exception:
            return None

    def _check_domain_in_set(self, domain: Optional[str], domain_set: Set[str]) -> bool:
        if not domain: return False
        domain_lower = domain.lower()
        for item_in_set in domain_set:
            if domain_lower == item_in_set or domain_lower.endswith("." + item_in_set):
                return True
        return False

    def _check_image_keyword_filters(self, img_abs_url: str, alt_text: Optional[str]) -> bool:
        alt_text_lower = (alt_text or "").lower()
        if alt_text_lower:
            if alt_text_lower in self.settings.img_filter_irrelevant_alt_text_exact:
                self.logger.info(f"FILTERED (Alt Text Exact): '{alt_text}' for {img_abs_url}")
                return False
            if any(sub in alt_text_lower for sub in self.settings.img_filter_irrelevant_alt_text_substrings):
                self.logger.info(f"FILTERED (Alt Text Substring): '{alt_text}' for {img_abs_url}")
                return False
        
        abs_img_url_lower = img_abs_url.lower()
        if any(segment in abs_img_url_lower for segment in self.settings.img_filter_irrelevant_filename_url_segments):
            self.logger.info(f"FILTERED (URL Segment): {img_abs_url}")
            return False
        return True

    async def _get_playwright_image_details(self, url: str, base_url_for_resolution: str) -> Dict[str, Dict[str, Any]]:
        """
        Uses Playwright to load a page and extract details for all images found.
        Returns a map of absolute image URLs to their details (dimensions, alt, visibility).
        """
        image_details_map: Dict[str, Dict[str, Any]] = {}
        self.logger.debug(f"Playwright: Starting to fetch image details for URL: {url}")
        try:
            # This outer try-except is to catch potential startup issues with Playwright itself (e.g., NotImplementedError on Windows)
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    page = await browser.new_page()
                    
                    try:
                        await page.goto(url, timeout=self.service_settings.playwright_page_load_timeout_ms)
                        await page.wait_for_load_state('networkidle', timeout=self.service_settings.playwright_network_idle_timeout_ms)
                        self.logger.debug(f"Playwright: Page loaded for {url}")
                    except Exception as e_nav:
                        self.logger.warning(f"Playwright: Navigation or load state wait failed for {url} (timeouts: load={self.service_settings.playwright_page_load_timeout_ms}ms, idle={self.service_settings.playwright_network_idle_timeout_ms}ms): {e_nav}. Attempting to extract images anyway.")
                    
                    images_on_page = await page.query_selector_all('img')
                    self.logger.debug(f"Playwright: Found {len(images_on_page)} <img> tags on {url}")
                    
                    for img_element in images_on_page:
                        try:
                            src = await img_element.get_attribute('src')
                            if not src: continue

                            abs_src = urljoin(base_url_for_resolution, src.strip()) # Resolve against the page's base URL
                            if not abs_src: continue

                            # Get rendered dimensions and visibility
                            bounding_box = await img_element.bounding_box()
                            width = int(bounding_box['width']) if bounding_box else 0
                            height = int(bounding_box['height']) if bounding_box else 0
                            is_visible = await img_element.is_visible()
                            alt = await img_element.get_attribute('alt') or ""

                            image_details_map[abs_src] = {
                                'width': width,
                                'height': height,
                                'visible': is_visible,
                                'alt': alt,
                                'source_method': 'playwright'
                            }
                            self.logger.debug(f"Playwright: Got details for {abs_src}: w={width}, h={height}, vis={is_visible}, alt='{alt[:30]}'")
                        except Exception as e_img_detail:
                            self.logger.warning(f"Playwright: Error getting details for an image on {url}: {e_img_detail}")
                    
                    await browser.close()
            except NotImplementedError as e_ni:
                self.logger.warning(f"Playwright: Could not initialize due to NotImplementedError (often on Windows without appropriate asyncio policy): {e_ni}. Proceeding without Playwright image details.")
                # image_details_map will remain empty, which is the desired fallback.
            except Exception as e_pw_general: # Catch other general Playwright startup/operational errors
                self.logger.error(f"Playwright: General error during Playwright execution for {url}:\n{e_pw_general}", exc_info=True)
                # image_details_map will remain empty, which is the desired fallback.
        except Exception as e_outer_unexpected: # Catch any truly unexpected error in this function's setup
            self.logger.error(f"Playwright: Unexpected outer error in _get_playwright_image_details for {url}:\n{e_outer_unexpected}", exc_info=True)
            # Ensure image_details_map is empty on any such failure
            image_details_map = {} # Explicitly ensure it's empty

        self.logger.debug(f"Playwright: Finished fetching image details for {url}. Found details for {len(image_details_map)} images.")
        return image_details_map

    async def _process_html_element(
        self,
        element: Union[Tag, str],
        blocks: List[PreliminaryBlock],
        base_url: str, # For resolving relative URLs from element's content
        job_id: str,
        user_id: Optional[str],
        # New parameters for integrated image processing
        all_raw_images: List[RawImageInput], 
        img_idx_counter: List[int], # Use a list to pass by reference for mutable int
        playwright_image_details_map: Optional[Dict[str, Dict[str, Any]]],
        original_request_url: str, # For GCS path in RawImageInput
        first_heading_encountered: List[bool] # ADDED: Flag for pre-heading image filtering
    ) -> bool: # Returns True if processing of subsequent siblings should stop
        """
        Recursively processes HTML elements (Tags or strings) to extract content
        into PreliminaryBlock objects.
        Integrated image discovery, filtering, RawImageInput creation, and stop-heading logic.
        Returns True if a stop condition (like a stop heading) is met, signaling the caller
        to halt processing of further sibling elements.
        """
        element_type = type(element).__name__
        element_details = ""
        if isinstance(element, str):
            element_details = f"String content (len {len(element)}): '{element[:100].strip().replace(chr(10), ' ')}...'"
        elif hasattr(element, 'name') and element.name:
            element_details = f"Tag: <{element.name}>, Attrs: {element.attrs if hasattr(element, 'attrs') else '{}'}"
        elif isinstance(element, Comment):
            element_details = f"Comment: '{str(element)[:100].strip().replace(chr(10), ' ')}...'"
        else:
            element_details = f"Other element: {str(element)[:100].strip().replace(chr(10), ' ')}..."

        self.logger.debug(f"WebService _process_html_element: Processing {element_type} - {element_details}")

        if isinstance(element, Comment):
            return False

        if isinstance(element, str): # NavigableString
            text_content_stripped = element.strip()
            if not text_content_stripped:
                self.logger.debug("WebService _process_html_element: Text node is empty after strip, skipping.")
                return False

            self.logger.debug(f"WebService _process_html_element: Found text node: '{text_content_stripped[:100].replace(chr(10), ' ')}...'")
            current_order = len(blocks)
            if blocks and blocks[-1].type == "text":
                current_text_from_last_block = getattr(blocks[-1], 'text_content', None)
                if current_text_from_last_block:
                    blocks[-1].text_content = current_text_from_last_block + " " + text_content_stripped
                else:
                    blocks[-1].text_content = text_content_stripped
            else:
                block_id = f"pb_{job_id}_{current_order}"
                new_block = PreliminaryBlock(
                    block_id=block_id, type="text", text_content=text_content_stripped,
                    order=current_order, 
                    custom_attributes={'source_url': original_request_url, 'tag_name': None}
                )
                blocks.append(new_block)
                self.logger.info(f"CREATED PreliminaryBlock (Text) ID: {block_id} - Content: '{text_content_stripped[:100].replace(chr(10), ' ')}...')")
            return False

        tag_name = element.name.lower() if element.name else ""
        self.logger.debug(f"WebService _process_html_element: Handling tag: <{tag_name}>")

        if tag_name in ['script', 'style']:
            self.logger.debug(f"Skipping <{tag_name}> tag and its contents.")
            return False

        if tag_name in self.HEADING_TAGS or \
           (tag_name == "head" and element.attrs.get("rend", "").lower().startswith("h")):
            heading_text_content = element.get_text(separator=" ", strip=True)
            self.logger.debug(f"WebService _process_html_element: Initial get_text() for <{element.name}>: '{heading_text_content[:100]}...'")
            normalized_heading_text = heading_text_content.lower().strip()

            if normalized_heading_text in self.stop_headings:
                self.logger.info(f"FILTERED (Stop Heading): Encountered stop heading '{heading_text_content}'. Halting processing of further siblings.")
                return True 
            
            if not heading_text_content and tag_name == "head":
                if hasattr(element, 'contents') and element.contents:
                    child_texts = []
                    for child_node in element.contents:
                        child_text_segment = ""
                        if hasattr(child_node, 'get_text'): child_text_segment = child_node.get_text(separator=" ", strip=True)
                        elif isinstance(child_node, str): child_text_segment = str(child_node).strip()
                        if child_text_segment: child_texts.append(child_text_segment)
                    if child_texts: heading_text_content = " ".join(child_texts)
                    self.logger.debug(f"Reconstructed text for <{element.name}>: '{heading_text_content[:100]}...'")

            if heading_text_content:
                level = 0
                if tag_name.startswith("h") and len(tag_name) == 2 and tag_name[1].isdigit():
                    level = int(tag_name[1])
                elif tag_name == "head" and element.attrs.get("rend","").lower().startswith("h"):
                    rend_level_match = re.match(r"h(\\d)", element.attrs.get("rend","").lower())
                    if rend_level_match: level = int(rend_level_match.group(1))
                level = max(1, min(level if level > 0 else 1, 6))
                
                current_order = len(blocks)
                block_id = f"pb_{job_id}_{current_order}"
                blocks.append(PreliminaryBlock(
                    block_id=block_id, type="heading", text_content=heading_text_content,
                    order=current_order, 
                    custom_attributes={'source_url': original_request_url, 'tag_name': tag_name, 'attributes': {'level': level}}
                ))
                self.logger.info(f"CREATED PreliminaryBlock (Heading L{level}) ID: {block_id} - Content: '{heading_text_content[:100]}...')")
                first_heading_encountered[0] = True
            else:
                self.logger.warning(f"Skipping empty heading <{tag_name}>.")
            return False

        elif tag_name == 'pre':
            code_tag = element.find('code')
            text_content = (code_tag or element).get_text(strip=False)
            language = None
            if code_tag:
                language_class = code_tag.get('class', [])
                language = next((cls.replace('language-', '') for cls in language_class if cls.startswith('language-')), None)
            
            if text_content.strip():
                current_order = len(blocks)
                block_id = f"pb_{job_id}_{current_order}"
                blocks.append(PreliminaryBlock(
                    block_id=block_id, type="code", text_content=text_content,
                    order=current_order, 
                    custom_attributes={'source_url': original_request_url, 'tag_name': tag_name, 'attributes': {'language': language}}
                ))
                self.logger.info(f"CREATED PreliminaryBlock (Code) ID: {block_id} - Lang: {language}")
            return False

        elif tag_name == "img" or tag_name == "graphic":
            img_src = element.attrs.get("src")
            if not img_src or img_src.startswith("data:image") or not img_src.strip():
                self.logger.debug(f"Primary 'src' attribute is missing, data URI, or empty for <{tag_name}>. Checking srcset, data-src, data-original.")
                srcset = element.attrs.get("srcset")
                data_src = element.attrs.get("data-src")
                data_original = element.attrs.get("data-original")

                if srcset:
                    img_src = srcset.strip().split(',')[0].strip().split(' ')[0]
                    self.logger.debug(f"Using first URL from srcset for <{tag_name}>: '{img_src}'")
                elif data_src:
                    img_src = data_src
                    self.logger.debug(f"Using data-src for <{tag_name}>: '{img_src}'")
                elif data_original:
                    img_src = data_original
                    self.logger.debug(f"Using data-original for <{tag_name}>: '{img_src}'")
                else:
                    parent_picture = element.find_parent('picture')
                    if parent_picture:
                        source_tag = parent_picture.find('source', srcset=True)
                        if source_tag and source_tag.attrs.get("srcset"):
                            img_src = source_tag.attrs["srcset"].strip().split(',')[0].strip().split(' ')[0]
                            self.logger.debug(f"Using first URL from <picture><source srcset> for <{tag_name}>: '{img_src}'")
            
            alt_text = element.attrs.get("alt", "")

            if not img_src or img_src.startswith("data:image") or not img_src.strip():
                self.logger.debug(f"<{tag_name}> has no valid src, data URI, or empty src even after fallbacks: '{img_src}'. Skipping direct processing.")
            else:
                img_abs_url = urljoin(base_url, img_src.strip())

                if not first_heading_encountered[0]:
                    self.logger.info(f"FILTERED (Pre-Heading Image): Image {img_abs_url} appeared before the first heading.")
                    self.processed_image_urls.add(img_abs_url) 
                    return False

                if img_abs_url in self.processed_image_urls:
                    self.logger.info(f"FILTERED (Duplicate URL): Image already processed: {img_abs_url}")
                    return False 

                if not self._check_image_keyword_filters(img_abs_url, alt_text):
                    return False

                final_alt_text = alt_text
                pw_rendered_width, pw_rendered_height = None, None

                perform_playwright_filtering = self.service_settings.use_playwright_for_image_filtering and playwright_image_details_map is not None and bool(playwright_image_details_map)

                if perform_playwright_filtering:
                    if img_abs_url in playwright_image_details_map:
                        details = playwright_image_details_map[img_abs_url]
                        pw_rendered_width = details.get("width", 0)
                        pw_rendered_height = details.get("height", 0)
                        is_visible = details.get("visible", False)
                        pw_alt = details.get("alt", "")
                        if pw_alt: final_alt_text = pw_alt

                        self.logger.info(f"PLAYWRIGHT_PRE_FILTER_DETAILS for <{tag_name}> {img_abs_url}: "
                                         f"Reported Vis:{is_visible}, "
                                         f"Reported W:{pw_rendered_width}, H:{pw_rendered_height}. "
                                         f"Effective Alt:'{final_alt_text}'.")

                        if not is_visible: 
                            self.logger.info(f"FILTERED (Playwright <{tag_name}> Invisible): {img_abs_url}"); return False
                        if pw_rendered_width < self.service_settings.min_image_width: 
                            self.logger.info(f"FILTERED (Playwright <{tag_name}> Width {pw_rendered_width} < {self.service_settings.min_image_width}): {img_abs_url}"); return False
                        if pw_rendered_height < self.service_settings.min_image_height: 
                            self.logger.info(f"FILTERED (Playwright <{tag_name}> Height {pw_rendered_height} < {self.service_settings.min_image_height}): {img_abs_url}"); return False
                        if (pw_rendered_width * pw_rendered_height) < self.service_settings.min_image_area: 
                            self.logger.info(f"FILTERED (Playwright <{tag_name}> Area {pw_rendered_width*pw_rendered_height} < {self.service_settings.min_image_area}): {img_abs_url}"); return False
                    else:
                        self.logger.warning(f"Playwright run, but no details found for <{tag_name}>: {img_abs_url}. Skipping this image as Playwright data is authoritative when present.")
                        return False 
                
                img_id_ref = f"web_{job_id}_img{img_idx_counter[0]}"
                img_idx_counter[0] += 1
                caption_text = None
                if tag_name == 'img' and element.parent and element.parent.name == 'figure':
                    figcaption_tag = element.parent.find('figcaption')
                    if figcaption_tag: caption_text = figcaption_tag.get_text(separator=" ", strip=True)
                
                current_raw_image_input = RawImageInput(
                    image_id=img_id_ref, source_url=img_abs_url, alt_text=final_alt_text, caption=caption_text,
                    source_document_id=job_id, original_source_identifier_for_gcs_path=original_request_url,
                    source_type_for_gcs_path="web", job_id_for_gcs_path=job_id,
                    width=pw_rendered_width, height=pw_rendered_height
                )
                all_raw_images.append(current_raw_image_input)
                self.logger.critical(f"RAW_IMG_CREATED: ID '{img_id_ref}' for URL '{img_abs_url}'")
                self.processed_image_urls.add(img_abs_url)
                self.logger.info(f"CREATED RawImageInput ID: {img_id_ref} for <{tag_name}> URL: {img_abs_url}")
                
                current_order = len(blocks)
                block_id = f"pb_{job_id}_{current_order}"
                image_custom_attrs = {'source_url': original_request_url, 'tag_name': tag_name, 'attributes': {}}
                if caption_text:
                    image_custom_attrs['attributes']['caption'] = caption_text
                blocks.append(PreliminaryBlock(
                    block_id=block_id, type="image_placeholder", image_id_ref=img_id_ref,
                    order=current_order, text_content=final_alt_text or "Image",
                    custom_attributes=image_custom_attrs
                ))
                self.logger.info(f"CREATED PreliminaryBlock (ImagePlaceholder) ID: {block_id} for {img_id_ref}")
            
            if img_src and not img_src.startswith("data:image"):
                 return False

        if hasattr(element, 'contents') and element.contents:
            self.logger.debug(f"Element <{tag_name if tag_name else 'string_wrapper'}> is a container or unhandled, recursing into {len(element.contents)} children...")
            for child_element in element.contents:
                if await self._process_html_element(child_element, blocks, base_url, job_id, user_id, all_raw_images, img_idx_counter, playwright_image_details_map, original_request_url, first_heading_encountered):
                    return True 
            self.logger.debug(f"Finished recursing for children of <{tag_name if tag_name else 'string_wrapper'}>.")
        
        return False

    async def _parse_and_structure_html(
        self,
        html_content: str,
        base_url: str, # URL associated with the html_content
        original_request_url: str, # The very first URL user provided (for GCS path in RawImageInput & PW)
        job_id: str,
        user_id: Optional[str],
        playwright_image_details_map: Optional[Dict[str, Dict[str, Any]]] # Details from Playwright
    ) -> Tuple[List[PreliminaryBlock], List[RawImageInput]]:
        
        preliminary_blocks: List[PreliminaryBlock] = []
        all_raw_images: List[RawImageInput] = [] # To be populated by _process_html_element
        img_idx_counter: List[int] = [0] # Mutable int passed by reference
        first_heading_encountered: List[bool] = [False] # ADDED: Flag for pre-heading image filtering

        self.logger.debug(f"WebService _parse_and_structure_html: Input html_content snippet (first 500 chars):\n{html_content[:500] if html_content else 'None'}")
        soup = BeautifulSoup(html_content, 'html.parser')
        
        if soup.contents:
            self.logger.debug(f"WebService _parse_and_structure_html: soup.contents length: {len(soup.contents)}")
            self.logger.debug(f"WebService _parse_and_structure_html: type(soup.contents[0]): {type(soup.contents[0])}")
            self.logger.debug(f"WebService _parse_and_structure_html: soup.contents[0] snippet (first 100 chars):\n{str(soup.contents[0])[:100] if soup.contents[0] else 'None'}")
        else:
            self.logger.debug("WebService _parse_and_structure_html: soup.contents is empty.")

        # Determine the main content container to process.
        # If html_content is from Trafilatura, it's likely already focused.
        # Otherwise, find common main content tags or fall back to body.
        # Note: Trafilatura's output might not have a single <article> or <main> if it combines sections.
        # It often produces a sequence of <p>, <head level="h2">, <graphic>, etc.
        # So, using soup (which is the Trafilatura output if available) directly might be best.
        
        # The root for processing will be the entire soup object derived from main_content_html_to_parse
        # In _process_html_element, we'll iterate its children.
        # Children of the root 'soup' object are usually the top-level tags of the parsed document fragment.
        
        for child_element in soup.contents: # Iterate over top-level elements in the parsed HTML
            await self._process_html_element(
                child_element, 
                preliminary_blocks, 
                base_url, # base_url is where html_content came from
                job_id, 
                user_id,
                all_raw_images,
                img_idx_counter,
                playwright_image_details_map,
                original_request_url,
                first_heading_encountered
            )
        
        # Post-processing: Consolidate adjacent text blocks if necessary
        # (This logic can be enhanced or moved to ContentStructuringService)
        consolidated_blocks: List[PreliminaryBlock] = []
        if preliminary_blocks:
            current_block = preliminary_blocks[0]
            for next_block in preliminary_blocks[1:]:
                current_text_val = getattr(current_block, 'text_content', None)
                next_text_val = getattr(next_block, 'text_content', None)

                if current_block.type == "text" and next_block.type == "text" and \
                   current_text_val and next_text_val: 
                    self.logger.debug(f"Consolidating text block {next_block.block_id} into {current_block.block_id}")
                    current_block.text_content = current_text_val + " " + next_text_val
                else:
                    consolidated_blocks.append(current_block)
                    current_block = next_block
            consolidated_blocks.append(current_block) 
        
        if len(consolidated_blocks) != len(preliminary_blocks) and consolidated_blocks:
            self.logger.debug(f"Re-assigning order to {len(consolidated_blocks)} consolidated blocks.")
            for i, block in enumerate(consolidated_blocks):
                block.order = i
        
        final_blocks = [b for b in consolidated_blocks if not (b.type == "text" and not getattr(b, 'text_content', "").strip())] # Remove empty text blocks


        self.logger.info(f"WebService _parse_and_structure_html: Blocks: {len(final_blocks)}, Final Raw Images: {len(all_raw_images)}")
        return final_blocks, all_raw_images

    async def _is_content_behind_paywall(self, extracted_html_content: Optional[str], domain: Optional[str]) -> bool:
        """Checks if the extracted content is likely behind a paywall."""
        if not extracted_html_content:
            # If Trafilatura returned nothing, it could be a sign of a hard paywall or empty page.
            # For very strict domains, this might be enough to classify as paywalled.
            if self._check_domain_in_set(domain, VERY_STRICT_PAYWALL_DOMAINS):
                self.logger.info(f"PAYWALL_CHECK: Empty content from Trafilatura for very strict domain '{domain}'. Flagging as paywalled.")
                return True
            return False # For other domains, empty content isn't definitively a paywall by itself.

        extracted_html_lower = extracted_html_content.lower()
        
        # Ensure PAYWALL_KEYWORDS are lowercase for matching
        # Assuming PAYWALL_KEYWORDS is a set of strings defined at the module/class level
        # For safety, ensure it's available and lowercase it if not already.
        # paywall_keywords_lower = {k.lower() for k in PAYWALL_KEYWORDS} 
        # PAYWALL_KEYWORDS should already be lowercase based on its definition style

        keywords_found = any(keyword in extracted_html_lower for keyword in PAYWALL_KEYWORDS)
        
        content_length = len(extracted_html_content)
        is_minimal_content = content_length < self.service_settings.minimal_content_length_threshold

        is_very_strict_domain = self._check_domain_in_set(domain, VERY_STRICT_PAYWALL_DOMAINS)

        log_msg_parts = [
            f"PAYWALL_CHECK for domain '{domain}':",
            f"StrictDomain={is_very_strict_domain}",
            f"MinimalContent={is_minimal_content} (len:{content_length} < thr:{self.service_settings.minimal_content_length_threshold})",
            f"KeywordsFound={keywords_found}"
        ]

        if is_very_strict_domain:
            if is_minimal_content or keywords_found:
                self.logger.info(f"{', '.join(log_msg_parts)}. DECISION: Paywalled (Strict domain rules).")
                return True
        else:
            if is_minimal_content and keywords_found:
                self.logger.info(f"{', '.join(log_msg_parts)}. DECISION: Paywalled (Minimal content with keywords).")
                return True
        
        self.logger.info(f"{', '.join(log_msg_parts)}. DECISION: Not paywalled.")
        return False

    async def execute(self, web_input: WebAcquisitionServiceInput) -> ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]:
        job_id_for_run = web_input.job_id or str(uuid.uuid4())
        user_id_for_run = web_input.user_id
        self.logger.info(f"WebService starting for URL: {web_input.url}, Job ID: {job_id_for_run}")
        start_time = time.time() # Initialize start_time

        # Initialize DocumentMetadata early
        doc_metadata = DocumentMetadata(
            document_id=job_id_for_run,
            user_id=user_id_for_run or "anonymous_web_acq", # Ensure user_id is set
            source_identifier=web_input.url, # Initial identifier
            source_type='url', # Initial assumption
            extracted_at=datetime.utcnow()
        )

        # Check URL support and paywalls (simplified check here, more detail in original tool)
        parsed_url = urlparse(web_input.url)
        domain = parsed_url.hostname

        # ... (URL validation logic like _is_url_supported, _check_paywall can be called here if they are part of this class)

        fetched_content: Optional[str] = None
        raw_content_bytes: Optional[bytes] = None
        content_type: Optional[str] = None
        final_url_after_redirects: str = web_input.url # Initialize with original URL
        
        # Use a single client for the session if multiple requests are needed for this URL
        try:
            # Apply DEFAULT_HEADERS to the client used for fetching the main URL
            async with httpx.AsyncClient(timeout=self.httpx_timeout, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
                self.logger.info(f"Fetching URL: {web_input.url} with headers: {client.headers}")
                start_fetch_time = time.time()
                response = await client.get(web_input.url)
                fetch_duration = time.time() - start_fetch_time
                self.logger.info(f"Fetched {web_input.url} in {fetch_duration:.2f}s, Status: {response.status_code}")
                
                final_url_after_redirects = str(response.url) # Capture final URL after redirects
                doc_metadata.final_url = final_url_after_redirects # Update metadata
                doc_metadata.source_identifier = final_url_after_redirects # Update to final URL as primary identifier

                response.raise_for_status() # Raise an exception for 4XX/5XX errors

                content_type = response.headers.get('content-type', '').lower()
                raw_content_bytes = await response.aread()
                # ... (rest of the execute method, including content decoding, parsing, etc.)

            # Try to decode content, falling back if needed
            try:
                fetched_content = raw_content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    # Attempt with a more lenient encoding, common for web content
                    fetched_content = raw_content_bytes.decode('latin-1')
                    self.logger.warning(f"Decoded with latin-1 for {final_url_after_redirects} after UTF-8 failed.")
                except UnicodeDecodeError as e_decode:
                    self.logger.error(f"Failed to decode content for {final_url_after_redirects} with UTF-8 and latin-1: {e_decode}")
                    doc_metadata.content_summary = f"Failed to decode content: {e_decode}"
                    # Include doc_metadata in the failure result if it has been partially populated.
                    return ServiceResult.failure(
                        error_message=f"Failed to decode content from {final_url_after_redirects}",
                        error_details={"original_data": ([], doc_metadata, [])} 
                    )

            if not fetched_content:
                 doc_metadata.content_summary = "No content fetched."
                 return ServiceResult.failure(
                    error_message=f"No content fetched from {final_url_after_redirects}",
                    error_details={"original_data": ([], doc_metadata, [])}
                )

            # Step 2: (Optional) Get image details using Playwright from the ORIGINAL URL
            playwright_image_details_map = None
            if self.service_settings.use_playwright_for_image_filtering:
                self.logger.debug(f"Playwright enabled. Fetching image details for original URL: {final_url_after_redirects}")
                # Pass final_url_after_redirects as base_url_for_resolution as well, since PW loads this directly.
                playwright_image_details_map = await self._get_playwright_image_details(final_url_after_redirects, final_url_after_redirects)
            
            # Step 3: Extract main content using Trafilatura
            # Trafilatura should operate on the full fetched_content from final_url_after_redirects
            main_content_html_trafilatura = trafilatura.extract(
                fetched_content, 
                url=final_url_after_redirects, # Tell Trafilatura the base URL of this content
                output_format='xml',  # Explicitly request XML output
                include_links=True,
                include_images=True, # Important for getting <graphic> tags
                include_comments=self.service_settings.trafilatura_include_comments,
                include_tables=self.service_settings.trafilatura_include_tables,
                favor_recall=self.service_settings.trafilatura_favor_recall,
                deduplicate=self.service_settings.trafilatura_deduplicate,
                config=self.trafilatura_config
            )

            # Update domain based on final URL for paywall check
            final_domain = self._get_domain(final_url_after_redirects)

            # NEW Paywall Check Logic (after Trafilatura extraction)
            if await self._is_content_behind_paywall(main_content_html_trafilatura, final_domain):
                self.logger.info(f"Content from {final_url_after_redirects} (domain: {final_domain}) identified as paywalled after Trafilatura extraction.")
                doc_metadata.is_paywalled = True
                doc_metadata.content_summary = "Content identified as likely behind a paywall after extraction."
                # Return success, but with empty blocks and metadata indicating paywall
                return ServiceResult.success(data=([], doc_metadata, []))

            if main_content_html_trafilatura:
                self.logger.debug(f"WebService execute: Trafilatura output type: {type(main_content_html_trafilatura)}, Length: {len(main_content_html_trafilatura)}")
                # ADDED: Log snippet of Trafilatura's output for debugging image issues
                self.logger.warning(f"TRAFILATURA_OUTPUT_SNIPPET (first 2000 chars) for {final_url_after_redirects}:\n{main_content_html_trafilatura[:2000]}")
            else:
                self.logger.debug("WebService execute: Trafilatura output is None or empty.")

            # Determine what HTML to parse: Trafilatura's output if available, else full page
            main_content_html_to_parse = main_content_html_trafilatura if main_content_html_trafilatura else fetched_content
            if not main_content_html_trafilatura:
                 self.logger.warning(f"Trafilatura extracted no main content from {final_url_after_redirects}. Using full fetched_content as fallback for parsing.")
            else:
                self.logger.debug(f"Trafilatura extracted main content. Length: {len(main_content_html_trafilatura)}") # Original log, good for comparison

            # Step 4: Extract metadata (e.g., title) from the FULL original page
            soup_full_page = BeautifulSoup(fetched_content, 'html.parser')
            title_tag = soup_full_page.find('title')
            page_title = title_tag.string.strip() if title_tag and title_tag.string else None

            if not page_title and main_content_html_trafilatura: # Try title from Trafilatura's main content if full page lacks it
                soup_trafilatura_content = BeautifulSoup(main_content_html_trafilatura, 'html.parser')
                # Trafilatura often puts title in <head><title> or as first <head level="h1">
                # Let's check for h1 in Trafilatura output as a common pattern.
                h1_tag_traf = soup_trafilatura_content.find('h1') # General h1
                if not h1_tag_traf: # Trafilatura also uses <head type="title"> or <head level="h1">
                    head_tag_traf = soup_trafilatura_content.find('head', {'level': ['h1', 'title']})
                    if head_tag_traf: page_title = head_tag_traf.get_text(strip=True)
                elif h1_tag_traf:
                     page_title = h1_tag_traf.get_text(strip=True)


            if not page_title: # Fallback title
                 page_title = os.path.basename(urlparse(final_url_after_redirects).path) or "Untitled Webpage"

            doc_metadata.title = page_title
            
            # Step 5: Parse the chosen HTML content and structure it, integrating Playwright details
            # First pass: Parse Trafilatura's output (if any)
            parsed_blocks_pass1, raw_images_pass1 = await self._parse_and_structure_html(
                html_content=main_content_html_to_parse, 
                base_url=final_url_after_redirects,    
                original_request_url=final_url_after_redirects, 
                job_id=job_id_for_run,
                user_id=user_id_for_run,
                playwright_image_details_map=playwright_image_details_map
            )

            preliminary_blocks = parsed_blocks_pass1
            raw_images = raw_images_pass1

            duration = time.time() - start_time
            self.logger.info(f"WebService execution for {final_url_after_redirects} completed in {duration:.2f}s. Blocks: {len(preliminary_blocks)}, Images: {len(raw_images)}")
            
            if not preliminary_blocks and not raw_images:
                self.logger.warning(f"No content blocks or images were extracted for {final_url_after_redirects}. Trafilatura output length: {len(main_content_html_trafilatura or '')}. Full page length: {len(fetched_content)}.")
                # Consider if this should be a failure or an empty success
                # For now, let it proceed as success with empty content, Orchestrator might flag it.

            return ServiceResult.success(data=(preliminary_blocks, doc_metadata, raw_images))

        except Exception as e_main:
            duration = time.time() - start_time
            self.logger.error(f"WebService failed for {final_url_after_redirects} in {duration:.2f}s: {e_main}", exc_info=True)
            return ServiceResult.failure(
                error_message=f"Failed to process URL {final_url_after_redirects}: {str(e_main)}",
                error_details={"url": final_url_after_redirects, "duration_seconds": duration}
            )