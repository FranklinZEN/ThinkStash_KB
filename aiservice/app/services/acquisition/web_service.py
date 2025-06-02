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
# Import PDFAcquisitionService and its input model
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput
from aiservice.app.config.settings import Settings # CORRECTED IMPORT

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
        self.logger.setLevel(logging.DEBUG)
        self.logger.warning("WebService logger is TEMPORARILY FORCED to DEBUG level.")
        
        if settings and settings.web_service:
            self.service_settings = settings.web_service
        else:
            from aiservice.app.config.settings import WebServiceSpecificSettings
            self.logger.error("Main 'Settings' object or 'settings.web_service' was not provided to WebAcquisitionService. Using direct default WebServiceSpecificSettings.")
            self.service_settings = WebServiceSpecificSettings()

        # Define common HTML tags
        self.TEXT_CONTAINER_TAGS = {'p', 'div', 'span', 'td', 'th', 'li', 'caption', 'article', 'section', 'main', 'blockquote', 'details', 'summary', 'aside'}
        self.HEADING_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
        self.LIST_TAGS = {'ul', 'ol'}
        self.TABLE_TAGS = {'table', 'tbody', 'thead', 'tfoot', 'tr'}
        self.CODE_TAGS = {'pre', 'code'}
        self.FIGURE_TAGS = {'figure', 'figcaption'}
        self.BOILERPLATE_TAGS = {"nav", "footer", "header", "aside", "script", "style", "form", "iframe", "noscript", "svg"}

        self.html_cache: Dict[str, Tuple[str, float]] = {}
        if settings and hasattr(settings, 'web_html_cache_ttl_seconds'):
             self.cache_ttl_seconds: int = settings.web_html_cache_ttl_seconds
        elif hasattr(self.service_settings, 'web_html_cache_ttl_seconds'):
             self.cache_ttl_seconds: int = self.service_settings.web_html_cache_ttl_seconds
        else:
            self.cache_ttl_seconds: int = 3600

        self.trafilatura_config = use_trafilatura_config()
        self.trafilatura_config.set("DEFAULT", "EXTRACTION_TIMEOUT", str(settings.default_request_timeout_seconds // 2 if settings and settings.default_request_timeout_seconds > 4 else 2))
        
        self.headers = {
            "User-Agent": self.service_settings.default_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5", # Optional: be a good internet citizen
            "Accept-Encoding": "gzip, deflate, br" # Optional: httpx handles this, but doesn't hurt to specify
        }
        self.httpx_timeout = httpx.Timeout(settings.default_request_timeout_seconds if settings else 30)

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

    async def _get_playwright_image_details(self, url: str, base_url_for_resolution: str) -> Dict[str, Dict[str, Any]]:
        """
        Uses Playwright to load a page and extract details for all images found.
        Returns a map of absolute image URLs to their details (dimensions, alt, visibility).
        """
        image_details_map: Dict[str, Dict[str, Any]] = {}
        self.logger.debug(f"Playwright: Starting to fetch image details for URL: {url}")
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
                        if not src or src.startswith("data:image"): 
                            continue

                        abs_src = urljoin(base_url_for_resolution, src.strip())
                        
                        bounding_box = await img_element.bounding_box()
                        width = int(bounding_box['width']) if bounding_box else 0
                        height = int(bounding_box['height']) if bounding_box else 0
                        
                        is_visible = await img_element.is_visible()
                        alt_text_pw = await img_element.get_attribute('alt') or ""
                        
                        if abs_src not in image_details_map:
                            image_details_map[abs_src] = {
                                "rendered_width": width,
                                "rendered_height": height,
                                "alt_text": alt_text_pw.strip(),
                                "is_visible": is_visible,
                                "from_playwright": True
                            }
                            self.logger.debug(f"Playwright: Got details for {abs_src} - W:{width}, H:{height}, Vis:{is_visible}, Alt:'{alt_text_pw[:30]}...'")
                    except Exception as e_img_detail:
                        self.logger.debug(f"Playwright: Error processing an image element on {url}: {e_img_detail}")
                await browser.close()
        except Exception as e_pw_general:
            # Catching playwright.helper.Error if playwright install hasn't been run.
            if "playwright install" in str(e_pw_general).lower():
                 self.logger.error(f"Playwright: Browsers not installed. Please run 'playwright install' or 'playwright install chromium'. Error: {e_pw_general}")
            else:
                self.logger.error(f"Playwright: General error during Playwright execution for {url}: {e_pw_general}", exc_info=True)
        
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
        original_request_url: str # For GCS path in RawImageInput
    ) -> None:
        """
        Recursively processes HTML elements (Tags or strings) to extract content
        into PreliminaryBlock objects.
        Integrated image discovery, filtering, and RawImageInput creation.
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
            self.logger.debug(f"WebService _process_html_element: Skipping comment: {str(element)[:100]}")
            return # Skip comments

        if isinstance(element, str):
            text_content_stripped = element.strip()
            if not text_content_stripped:
                self.logger.debug("WebService _process_html_element: Text node is empty after strip, skipping.")
                return

            self.logger.debug(f"WebService _process_html_element: Found text node: '{text_content_stripped[:100].replace(chr(10), ' ')}...'")

            if blocks and blocks[-1].type == "text":
                current_text_from_last_block = getattr(blocks[-1], 'text_content', None)

                if current_text_from_last_block: # Check if it's a non-empty string
                    self.logger.debug(f"WebService _process_html_element: Appending to existing text block (ID: {blocks[-1].block_id}): '{text_content_stripped[:100].replace(chr(10), ' ')}...'")
                    combined_text = current_text_from_last_block + " " + text_content_stripped
                    blocks[-1].text_content = combined_text # Use text_content
                else:
                    # The last block was 'text' type but its text_content was None or empty.
                    self.logger.debug(f"WebService _process_html_element: Setting text for existing text block (ID: {blocks[-1].block_id}) as it was None or empty: '{text_content_stripped[:100].replace(chr(10), ' ')}...'")
                    blocks[-1].text_content = text_content_stripped # Use text_content
            else:
                # Create a new text block
                new_block_id = f"pb_{job_id}_{len(blocks)}"
                self.logger.debug(f"WebService _process_html_element: Created new text block (ID: {new_block_id}): '{text_content_stripped[:100].replace(chr(10), ' ')}...'")
                blocks.append(PreliminaryBlock(
                    block_id=new_block_id,
                    type="text",
                    text_content=text_content_stripped, # Use text_content
                    order=len(blocks), 
                    page_number=None, 
                    bbox=None 
                ))
            return # Return after processing the string node

        # --- Handling specific HTML tags ---
        tag_name = element.name.lower() if element.name else ""
        self.logger.debug(f"WebService _process_html_element: Handling tag: <{tag_name}>")

        # Handle Trafilatura's <graphic> tags for images
        if tag_name == 'graphic':
            self.logger.debug(f"WebService _process_html_element: Encountered <graphic> tag.")
            img_src = element.get('url') or element.get('src')
            if img_src and not img_src.startswith("data:image"):
                abs_img_url = urljoin(base_url, img_src.strip())
                alt_text_from_tag = element.get('alt', '').strip()
                self.logger.debug(f"WebService _process_html_element: <graphic> src='{abs_img_url}', alt='{alt_text_from_tag}'")

                rendered_width = 0
                rendered_height = 0
                is_visible_on_page = True # Default to visible if not using Playwright or not found
                final_alt_text = alt_text_from_tag
                passed_playwright_filter = False

                if self.service_settings.use_playwright_for_image_filtering and playwright_image_details_map:
                    self.logger.debug(f"WebService _process_html_element: Playwright filtering is ON for <graphic> {abs_img_url}")
                    if abs_img_url in playwright_image_details_map:
                        details = playwright_image_details_map[abs_img_url]
                        rendered_width = details.get("rendered_width", 0)
                        rendered_height = details.get("rendered_height", 0)
                        is_visible_on_page = details.get("is_visible", False)
                        if details.get("alt_text") or not final_alt_text: 
                            final_alt_text = details.get("alt_text", "")
                        
                        self.logger.debug(f"Playwright Filtering Check for Trafilatura graphic {abs_img_url}: W:{rendered_width}, H:{rendered_height}, Vis:{is_visible_on_page}, Area:{rendered_width * rendered_height}")
                        
                        if not is_visible_on_page:
                            self.logger.debug(f"Filtered out (not visible via Playwright): {abs_img_url}")
                        elif rendered_width < self.service_settings.min_image_width:
                            self.logger.debug(f"Filtered out (width < {self.service_settings.min_image_width}): {abs_img_url} (width: {rendered_width})")
                        elif rendered_height < self.service_settings.min_image_height:
                            self.logger.debug(f"Filtered out (height < {self.service_settings.min_image_height}): {abs_img_url} (height: {rendered_height})")
                        elif (rendered_width * rendered_height) < self.service_settings.min_image_area:
                            self.logger.debug(f"Filtered out (area < {self.service_settings.min_image_area}): {abs_img_url} (area: {rendered_width * rendered_height})")
                        else:
                            self.logger.debug(f"PASSED Playwright filter: {abs_img_url}")
                            passed_playwright_filter = True
                    else:
                        self.logger.debug(f"Image {abs_img_url} (from Trafilatura graphic) not found in Playwright details map. Keys: {list(playwright_image_details_map.keys())[:5]}...")
                        if self.service_settings.playwright_filter_strict_if_enabled:
                             self.logger.debug(f"Strict Playwright filtering: {abs_img_url} not found in PW details, skipping.")
                        else:
                            passed_playwright_filter = True # Allow if not strict
                            self.logger.debug(f"Non-strict Playwright: Allowing {abs_img_url} despite not being in PW map.")

                elif not self.service_settings.use_playwright_for_image_filtering:
                    passed_playwright_filter = True # Playwright filtering is disabled, so it passes
                    self.logger.debug(f"WebService _process_html_element: Playwright filtering is OFF. <graphic> {abs_img_url} passes by default.")
                
                if passed_playwright_filter:
                    image_id = f"web_{job_id}_img{img_idx_counter[0]}"
                    img_idx_counter[0] += 1
                    
                    raw_image = RawImageInput(
                        image_id=image_id,
                        source_url=abs_img_url,
                        alt_text=final_alt_text,
                        caption=None,
                        source_document_id=job_id,
                        original_source_identifier_for_gcs_path=original_request_url,
                        source_type_for_gcs_path="web",
                        job_id_for_gcs_path=job_id,
                        width=rendered_width if self.service_settings.use_playwright_for_image_filtering and (abs_img_url in (playwright_image_details_map or {})) else None,
                        height=rendered_height if self.service_settings.use_playwright_for_image_filtering and (abs_img_url in (playwright_image_details_map or {})) else None,
                    )
                    all_raw_images.append(raw_image)
                    
                    new_block_id = f"pb_{job_id}_{len(blocks)}"
                    blocks.append(PreliminaryBlock(
                        block_id=new_block_id,
                        type="image_placeholder",
                        image_id_ref=image_id,
                        order=len(blocks),
                        text=final_alt_text or "Image", 
                    ))
                    self.logger.info(f"WebService _process_html_element: CREATED RawImageInput & Placeholder for <graphic>: ID {image_id}, URL {abs_img_url}, BlockID {new_block_id}")
                else:
                    self.logger.info(f"WebService _process_html_element: SKIPPED <graphic> due to Playwright filter: {abs_img_url}")

            else:
                self.logger.debug(f"WebService _process_html_element: <graphic> has no valid src or is data URI: '{img_src}'")
            return

        # Handle <img> tags
        elif tag_name == 'img':
            self.logger.debug(f"WebService _process_html_element: Encountered <img> tag.")
            img_src = element.get('src') or element.get('data-src')
            if img_src and not img_src.startswith("data:image"):
                abs_img_url = urljoin(base_url, img_src.strip())
                alt_text_from_tag = element.get('alt', '').strip()
                self.logger.debug(f"WebService _process_html_element: <img> src='{abs_img_url}', alt='{alt_text_from_tag}'")
                
                rendered_width = 0
                rendered_height = 0
                is_visible_on_page = True
                final_alt_text = alt_text_from_tag
                passed_playwright_filter = False

                if self.service_settings.use_playwright_for_image_filtering and playwright_image_details_map:
                    self.logger.debug(f"WebService _process_html_element: Playwright filtering is ON for <img> {abs_img_url}")
                    if abs_img_url in playwright_image_details_map:
                        details = playwright_image_details_map[abs_img_url]
                        rendered_width = details.get("rendered_width", 0)
                        rendered_height = details.get("rendered_height", 0)
                        is_visible_on_page = details.get("is_visible", False)
                        if details.get("alt_text") or not final_alt_text:
                            final_alt_text = details.get("alt_text", "")

                        self.logger.debug(f"Playwright Filtering Check for <img> {abs_img_url}: W:{rendered_width}, H:{rendered_height}, Vis:{is_visible_on_page}, Area:{rendered_width * rendered_height}")
                        if not is_visible_on_page:
                            self.logger.debug(f"Filtered out <img> (not visible via Playwright): {abs_img_url}")
                        elif rendered_width < self.service_settings.min_image_width:
                            self.logger.debug(f"Filtered out <img> (width < {self.service_settings.min_image_width}): {abs_img_url} (width: {rendered_width})")
                        elif rendered_height < self.service_settings.min_image_height:
                            self.logger.debug(f"Filtered out <img> (height < {self.service_settings.min_image_height}): {abs_img_url} (height: {rendered_height})")
                        elif (rendered_width * rendered_height) < self.service_settings.min_image_area:
                            self.logger.debug(f"Filtered out <img> (area < {self.service_settings.min_image_area}): {abs_img_url} (area: {rendered_width * rendered_height})")
                        else:
                            passed_playwright_filter = True
                            self.logger.debug(f"PASSED Playwright filter for <img>: {abs_img_url}")
                    else:
                        self.logger.debug(f"Image {abs_img_url} (from <img>) not found in Playwright details map. Keys: {list(playwright_image_details_map.keys())[:5]}...")
                        if self.service_settings.playwright_filter_strict_if_enabled:
                             self.logger.debug(f"Strict Playwright filtering: <img> {abs_img_url} not found in PW details, skipping.")
                        else:
                            passed_playwright_filter = True
                            self.logger.debug(f"Non-strict Playwright: Allowing <img> {abs_img_url} despite not being in PW map.")

                elif not self.service_settings.use_playwright_for_image_filtering:
                    passed_playwright_filter = True
                    self.logger.debug(f"WebService _process_html_element: Playwright filtering is OFF. <img> {abs_img_url} passes by default.")

                if passed_playwright_filter:
                    image_id = f"web_{job_id}_img{img_idx_counter[0]}"
                    img_idx_counter[0] += 1
                    raw_image = RawImageInput(
                        image_id=image_id,
                        source_url=abs_img_url,
                        alt_text=final_alt_text,
                        caption=None,
                        source_document_id=job_id,
                        original_source_identifier_for_gcs_path=original_request_url,
                        source_type_for_gcs_path="web",
                        job_id_for_gcs_path=job_id,
                        width=rendered_width if self.service_settings.use_playwright_for_image_filtering and (abs_img_url in (playwright_image_details_map or {})) else None,
                        height=rendered_height if self.service_settings.use_playwright_for_image_filtering and (abs_img_url in (playwright_image_details_map or {})) else None,
                    )
                    all_raw_images.append(raw_image)
                    
                    new_block_id = f"pb_{job_id}_{len(blocks)}"
                    blocks.append(PreliminaryBlock(
                        block_id=new_block_id,
                        type="image_placeholder",
                        image_id_ref=image_id,
                        order=len(blocks),
                        text=final_alt_text or "Image",
                    ))
                    self.logger.info(f"WebService _process_html_element: CREATED RawImageInput & Placeholder for <img>: ID {image_id}, URL {abs_img_url}, BlockID {new_block_id}")
                else:
                    self.logger.info(f"WebService _process_html_element: SKIPPED <img> due to Playwright filter: {abs_img_url}")

            else:
                self.logger.debug(f"WebService _process_html_element: <img> has no valid src or is data URI: '{img_src}'")
            return

        # --- Boilerplate Removal ---
        if tag_name in {"nav", "footer", "header", "aside", "script", "style", "form", "iframe", "noscript", "svg"}:
            self.logger.debug(f"WebService _process_html_element: Skipping boilerplate element by tag: <{tag_name}>")
            return

        # --- Content Extraction from common block-level elements ---
        block_type: Optional[str] = None
        text_content = ""

        if tag_name in {'p', 'div', 'span', 'td', 'th', 'li', 'caption', 'article', 'section', 'main', 'blockquote', 'details', 'summary', 'aside'}:
            self.logger.debug(f"WebService _process_html_element: Tag <{tag_name}> is a text container, will recurse for children.")
            pass 

        # Heading tags (h1-h6 and Trafilatura's <head rend="hX">)
        elif tag_name in self.HEADING_TAGS or \
             (tag_name == "head" and element.attrs.get("rend", "").lower().startswith("h")):
            self.logger.debug(f"WebService _process_html_element: Handling tag: <{element.name}> as heading with attrs {element.attrs}.")
            
            heading_text_content = element.get_text(separator=" ", strip=True)
            self.logger.debug(f"WebService _process_html_element: Initial get_text() for <{element.name}>: '{heading_text_content[:100]}...'")

            if not heading_text_content and tag_name == "head":
                # Workaround for Trafilatura <head> tags if get_text() fails but children exist
                if hasattr(element, 'contents') and element.contents:
                    self.logger.debug(f"WebService _process_html_element: <{element.name}> get_text() was empty. Trying to build from children.")
                    child_texts = []
                    for child_node in element.contents:
                        # Recursively get text from all children, similar to what get_text() does
                        child_text_segment = ""
                        if hasattr(child_node, 'get_text'):
                            child_text_segment = child_node.get_text(separator=" ", strip=True)
                        elif isinstance(child_node, NavigableString): # NavigableString is a subclass of str
                            child_text_segment = str(child_node).strip()
                        
                        if child_text_segment:
                            child_texts.append(child_text_segment)
                    
                    if child_texts:
                        heading_text_content = " ".join(child_texts)
                        self.logger.debug(f"WebService _process_html_element: Reconstructed text for <{element.name}> from children: '{heading_text_content[:100]}...'")
            
            if heading_text_content:
                # Determine heading level
                level = 0
                if element.name.startswith("h") and len(element.name) == 2 and element.name[1].isdigit():
                    level = int(element.name[1])
                elif element.name == "head" and element.attrs.get("rend","").lower().startswith("h"):
                    rend_level_match = re.match(r"h(\d)", element.attrs.get("rend","").lower())
                    if rend_level_match:
                        level = int(rend_level_match.group(1))
                
                level = max(1, min(level if level > 0 else 1, 6)) # Ensure level 1-6, default to 1 if not parsable or 0

                block_id = f"pb_{job_id}_{len(blocks)}"
                heading_block = PreliminaryBlock(
                    block_id=block_id,
                    type="heading",
                    text=heading_text_content,
                    order=len(blocks),
                    page_number=None,
                    bbox=None
                )
                blocks.append(heading_block)
                self.logger.info(f"CREATED PreliminaryBlock (Heading L{level}) ID: {block_id} - Content: '{heading_text_content[:100]}...'")
                return # Processed, do not recurse further as text is captured.
            else:
                self.logger.warning(f"WebService _process_html_element: Heading tag <{element.name}> (attrs: {element.attrs}) resulted in no text content. Skipping block creation, will recurse for children if any.")
                # Fall through to general child recursion logic.
                # This path should ideally not be hit for valid headings.

        elif tag_name == 'pre':
            code_tag = element.find('code')
            language = None
            if code_tag:
                text_content = code_tag.get_text(strip=False) 
                language_class = code_tag.get('class', [])
                language = next((cls.replace('language-', '') for cls in language_class if cls.startswith('language-')), None)
                self.logger.debug(f"WebService _process_html_element: Extracted <code> block (lang: {language}): '{text_content[:100]}...'")
            else:
                text_content = element.get_text(strip=False)
                self.logger.debug(f"WebService _process_html_element: Extracted <pre> block (no lang): '{text_content[:100]}...'")
            
            if text_content.strip():
                new_block_id = f"pb_{job_id}_{len(blocks)}"
                blocks.append(PreliminaryBlock(
                    block_id=new_block_id,
                    type="code",
                    text=text_content, 
                    language=language,
                    order=len(blocks)
                ))
                self.logger.debug(f"WebService _process_html_element: Created code block (ID: {new_block_id}).")
            else:
                self.logger.debug(f"WebService _process_html_element: <pre> or <code> content is empty after strip, skipping block creation.")
            return 

        elif tag_name == 'figure':
            self.logger.debug(f"WebService _process_html_element: Encountered <figure>, will recurse for children (e.g., figcaption, images).")
            pass

        elif tag_name == 'table':
            self.logger.debug(f"WebService _process_html_element: Encountered <table>, will recurse for children (td, th, caption).")
            pass
        
        elif tag_name == 'ul' or tag_name == 'ol':
            self.logger.debug(f"WebService _process_html_element: Encountered <{tag_name}> list, will recurse for <li> children.")
            pass
        

        if block_type and text_content.strip():
            new_block_id = f"pb_{job_id}_{len(blocks)}"
            blocks.append(PreliminaryBlock(
                block_id=new_block_id,
                type=block_type,
                text=text_content.strip(),
                order=len(blocks)
            ))
            self.logger.debug(f"WebService _process_html_element: Created {block_type} block (ID: {new_block_id}).")
            return 
        
        # --- Recursive processing for children ---
        if hasattr(element, 'contents') and element.contents:
            self.logger.debug(f"WebService _process_html_element: Element <{tag_name}> has {len(element.contents)} children. Recursing...")
            for i, child_element in enumerate(element.contents):
                child_type = type(child_element).__name__
                child_details_preview = ""
                if isinstance(child_element, str):
                    child_details_preview = f"'{child_element[:50].strip().replace(chr(10), ' ')}...'"
                elif hasattr(child_element, 'name') and child_element.name:
                    child_details_preview = f"<{child_element.name}>"
                else:
                     child_details_preview = f"Other: {str(child_element)[:50].strip().replace(chr(10), ' ')}..."
                self.logger.debug(f"WebService _process_html_element: Recursing for child {i+1}/{len(element.contents)} of <{tag_name}> (Type: {child_type}, Preview: {child_details_preview})")
                await self._process_html_element(
                    child_element, 
                    blocks, 
                    base_url, 
                    job_id, 
                    user_id, 
                    all_raw_images, 
                    img_idx_counter, 
                    playwright_image_details_map,
                    original_request_url
                )
            self.logger.debug(f"WebService _process_html_element: Finished recursing for children of <{tag_name}>.")
        else:
            self.logger.debug(f"WebService _process_html_element: Element <{tag_name}> has no children to recurse into or 'contents' attribute missing.")

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

        self.logger.debug(f"WebService _parse_and_structure_html: Input html_content snippet (first 500 chars):\\n{html_content[:500] if html_content else 'None'}")
        soup = BeautifulSoup(html_content, 'html.parser')
        
        if soup.contents:
            self.logger.debug(f"WebService _parse_and_structure_html: soup.contents length: {len(soup.contents)}")
            self.logger.debug(f"WebService _parse_and_structure_html: type(soup.contents[0]): {type(soup.contents[0])}")
            self.logger.debug(f"WebService _parse_and_structure_html: soup.contents[0] snippet (first 100 chars):\\n{str(soup.contents[0])[:100] if soup.contents[0] else 'None'}")
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
                original_request_url
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

    async def execute(self, web_input: WebAcquisitionServiceInput) -> ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]:
        start_time = time.time()
        job_id = web_input.job_id or uuid.uuid4().hex[:12]
        user_id = web_input.user_id
        original_request_url = str(web_input.url) # Keep the original requested URL separate

        self.logger.info(f"WebService starting for URL: {original_request_url}, Job ID: {job_id}")

        fetched_content: Optional[str] = None
        final_url_after_redirects = original_request_url # Initialize with original, update after fetch
        playwright_image_details_map: Optional[Dict[str, Dict[str, Any]]] = None

        try:
            # Step 1: Fetch initial HTML content using httpx
            async with httpx.AsyncClient(timeout=self.httpx_timeout, headers=self.headers, follow_redirects=True) as client:
                try:
                    response = await client.get(original_request_url)
                    response.raise_for_status()
                    fetched_content_bytes = response.content
                    final_url_after_redirects = str(response.url)
                    try:
                        fetched_content = fetched_content_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            fetched_content = fetched_content_bytes.decode('latin-1')
                        except UnicodeDecodeError:
                            self.logger.error(f"Failed to decode content from {final_url_after_redirects} with utf-8 or latin-1.")
                            # Fallback to Trafilatura's internal fetch if primary decoding fails
                            fetched_content = await self._fetch_content_with_trafilatura(original_request_url)
                            if fetched_content is None:
                                return ServiceResult.failure(f"Failed to fetch or decode content from {original_request_url}")
                
                except httpx.RequestError as e_httpx:
                    self.logger.error(f"HTTPX request failed for {original_request_url}: {e_httpx}", exc_info=True)
                    return ServiceResult.failure(f"Request failed for {original_request_url}: {e_httpx}")
                except httpx.HTTPStatusError as e_http_status:
                     self.logger.error(f"HTTP Error {e_http_status.response.status_code} for {original_request_url}: {e_http_status}", exc_info=True)
                     return ServiceResult.failure(f"HTTP Error {e_http_status.response.status_code} for {original_request_url}")

            if not fetched_content:
                 return ServiceResult.failure(f"No content fetched from {original_request_url}")

            # Step 2: (Optional) Get image details using Playwright from the ORIGINAL URL
            if self.service_settings.use_playwright_for_image_filtering:
                self.logger.debug(f"Playwright enabled. Fetching image details for original URL: {original_request_url}")
                # Pass original_request_url as base_url_for_resolution as well, since PW loads this directly.
                playwright_image_details_map = await self._get_playwright_image_details(original_request_url, original_request_url)
            
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

            if main_content_html_trafilatura:
                self.logger.debug(f"WebService execute: Trafilatura output type: {type(main_content_html_trafilatura)}, Length: {len(main_content_html_trafilatura)}")
                self.logger.debug(f"WebService execute: Trafilatura output snippet (first 500 chars):\\n{main_content_html_trafilatura[:500]}")
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

            document_metadata = DocumentMetadata(
                document_id=job_id,
                user_id=user_id or f"unknown_user_ws_{job_id}",
                source_identifier=original_request_url, # The URL user initially provided
                source_type="web",
                title=page_title,
                extracted_at=datetime.utcnow(),
                url_resolved=final_url_after_redirects
            )
            
            # Step 5: Parse the chosen HTML content and structure it, integrating Playwright details
            preliminary_blocks, raw_images = await self._parse_and_structure_html(
                html_content=main_content_html_to_parse, # This is key: parse Trafilatura's output
                base_url=final_url_after_redirects,    # Base for resolving relative links in the parsed HTML
                original_request_url=original_request_url, # For GCS paths and if PW needs to re-resolve
                job_id=job_id,
                user_id=user_id,
                playwright_image_details_map=playwright_image_details_map
            )
            
            duration = time.time() - start_time
            self.logger.info(f"WebService execution for {original_request_url} completed in {duration:.2f}s. Blocks: {len(preliminary_blocks)}, Images: {len(raw_images)}")
            
            if not preliminary_blocks and not raw_images:
                self.logger.warning(f"No content blocks or images were extracted for {original_request_url}. Trafilatura output length: {len(main_content_html_trafilatura or '')}. Full page length: {len(fetched_content)}.")
                # Consider if this should be a failure or an empty success
                # For now, let it proceed as success with empty content, Orchestrator might flag it.

            return ServiceResult.success(data=(preliminary_blocks, document_metadata, raw_images))

        except Exception as e_main:
            duration = time.time() - start_time
            self.logger.error(f"WebService failed for {original_request_url} in {duration:.2f}s: {e_main}", exc_info=True)
            return ServiceResult.failure(
                error_message=f"Failed to process URL {original_request_url}: {str(e_main)}",
                error_details={"url": original_request_url, "duration_seconds": duration}
            )