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
import platform # Import platform

from pydantic import BaseModel, Field, HttpUrl

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput
from aiservice.app.config.settings import Settings
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
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                
                try:
                    await page.goto(url, timeout=self.service_settings.playwright_page_load_timeout_ms)
                    await page.wait_for_load_state('networkidle', timeout=self.service_settings.playwright_network_idle_timeout_ms)
                    self.logger.debug(f"Playwright: Page loaded for {url}")
                except Exception as e_nav:
                    self.logger.warning(f"Playwright: Navigation or load state wait failed for {url}: {e_nav}. Attempting to extract images anyway.")
                
                images_on_page = await page.query_selector_all('img')
                self.logger.debug(f"Playwright: Found {len(images_on_page)} <img> tags on {url}")
                
                for img_element in images_on_page:
                    try:
                        src = await img_element.get_attribute('src')
                        if not src: continue

                        abs_src = urljoin(base_url_for_resolution, src.strip())
                        if not abs_src: continue

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
                    except Exception as e_img_detail:
                        self.logger.warning(f"Playwright: Error getting details for an image on {url}: {e_img_detail}")
                
                await browser.close()
        except NotImplementedError as e_ni:
            self.logger.warning(f"Playwright: Could not initialize due to NotImplementedError (often on Windows without appropriate asyncio policy). Proceeding without Playwright image details. Error: {e_ni}")
        except Exception as e_pw_general:
            self.logger.error(f"Playwright: General error during execution for {url}: {e_pw_general}", exc_info=True)

        self.logger.debug(f"Playwright: Finished fetching image details for {url}. Found details for {len(image_details_map)} images.")
        return image_details_map

    async def _parse_and_structure_html(
        self,
        xml_content: str,
        base_url: str,
        original_request_url: str,
        job_id: str,
        user_id: Optional[str],
        playwright_image_details_map: Optional[Dict[str, Dict[str, Any]]],
        source_document_id: str,
        source_type: str,
    ) -> Tuple[List[PreliminaryBlock], List[RawImageInput]]:
        blocks: List[PreliminaryBlock] = []
        all_raw_images: List[RawImageInput] = []
        
        # We are now parsing the XML from trafilatura directly
        soup = BeautifulSoup(xml_content, 'xml')
        
        main_content = soup.find('main')
        if not main_content:
            self.logger.warning("Trafilatura output did not contain a <main> tag. Parsing entire document.")
            main_content = soup

        order = 0
        img_idx_counter = 0

        for element in main_content.find_all(True, recursive=True):
            if element.name == 'head':
                heading_level_str = element.get('rend', 'h2').replace('h', '')
                try:
                    level = int(heading_level_str)
                except (ValueError, TypeError):
                    level = 2 # Default to h2 if parsing fails
                
                text = element.get_text(strip=True)
                if text:
                    blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_head_{order}",
                        order=order,
                        type='heading',
                        text_content=text,
                        heading_level=level
                    ))
                    order += 1
            
            elif element.name == 'p':
                text = element.get_text(strip=True)
                if text:
                    blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_p_{order}",
                        order=order,
                        type='text',
                        text_content=text
                    ))
                    order += 1

            elif element.name == 'graphic':
                src = element.get('src')
                if src:
                    abs_url = urljoin(base_url, src)
                    image_id = f"web_{job_id}_img{img_idx_counter}"
                    
                    all_raw_images.append(RawImageInput(
                        image_id=image_id,
                        source_url=abs_url,
                        alt_text=element.get('alt'),
                        original_source_identifier_for_gcs_path=original_request_url,
                        source_document_id=source_document_id,
                        source_type_for_gcs_path=source_type,
                        job_id_for_gcs_path=job_id
                    ))
                    
                    blocks.append(PreliminaryBlock(
                        block_id=f"{job_id}_img_placeholder_{order}",
                        order=order,
                        type='image_placeholder',
                        image_id_ref=image_id
                    ))
                    order += 1
                    img_idx_counter += 1

            # Add logic for other tags like lists (<ul>, <ol>, <li>) and code (<code>, <pre>) here if needed

        return blocks, all_raw_images

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
        """
        Main method to process a web acquisition request.
        """
        # --- FIX: Reset the state for each execution ---
        self.processed_image_urls.clear()
        
        start_time = time.time()
        
        job_id_for_run = web_input.job_id or str(uuid.uuid4())
        user_id_for_run = web_input.user_id
        self.logger.info(f"WebService starting for URL: {web_input.url}, Job ID: {job_id_for_run}")

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
            preliminary_blocks, raw_images = await self._parse_and_structure_html(
                xml_content=main_content_html_to_parse, 
                base_url=final_url_after_redirects,    
                original_request_url=final_url_after_redirects, 
                job_id=job_id_for_run,
                user_id=user_id_for_run,
                playwright_image_details_map=playwright_image_details_map,
                source_document_id=job_id_for_run, # job_id serves as the document_id
                source_type='url' # source_type is 'url' for this service
            )

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