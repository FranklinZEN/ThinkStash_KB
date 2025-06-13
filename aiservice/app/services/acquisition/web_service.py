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
import tempfile
import logging
import httpx
from trafilatura.settings import use_config as use_trafilatura_config
from playwright.async_api import async_playwright
import platform
from lxml.html import fromstring

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
    user_id: Optional[str] = None

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
        self.logger = logger
        self.settings = settings or Settings()
        self.service_settings: WebServiceSpecificSettings = self.settings.web_service
        
        request_timeout_seconds = self.settings.default_request_timeout_seconds
        self.httpx_timeout = httpx.Timeout(request_timeout_seconds)

        self.trafilatura_config = use_trafilatura_config()
        self.trafilatura_config.set("DEFAULT", "EXTRACTION_TIMEOUT", str(request_timeout_seconds // 2 if request_timeout_seconds > 4 else 2))
        self.trafilatura_config.set("DEFAULT", "INCLUDE_IMAGES", "True")
        self.trafilatura_config.set("DEFAULT", "INCLUDE_COMMENTS", "False")
        self.trafilatura_config.set("DEFAULT", "INCLUDE_TABLES", "False")
        self.trafilatura_config.set("DEFAULT", "FAVOR_PRECISION", "True")

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

    async def _fetch_html(self, url: str) -> Tuple[Optional[str], str, int]:
        try:
            async with httpx.AsyncClient(timeout=self.httpx_timeout, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
                response = await client.get(url)
                final_url = str(response.url)
                status_code = response.status_code
                if status_code == 200:
                    content = await response.aread()
                    return content.decode('utf-8', errors='ignore'), final_url, status_code
                return None, final_url, status_code
        except Exception as e:
            self.logger.error(f"Failed to fetch HTML for {url}: {e}", exc_info=True)
            return None, url, -1

    async def _get_playwright_image_details(self, url: str, base_url_for_resolution: str) -> Dict[str, Dict[str, Any]]:
        image_details_map: Dict[str, Dict[str, Any]] = {}
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto(url, timeout=self.service_settings.playwright_page_load_timeout_ms)
                await page.wait_for_load_state('networkidle', timeout=self.service_settings.playwright_network_idle_timeout_ms)
                images_on_page = await page.query_selector_all('img')
                for img_handle in images_on_page:
                    src = await img_handle.get_attribute('src')
                    if not src: continue
                    abs_url = urljoin(base_url_for_resolution, src)
                    try:
                        box = await img_handle.bounding_box()
                        is_visible = await img_handle.is_visible()
                        alt = await img_handle.get_attribute('alt')
                        image_details_map[abs_url] = {
                            'width': box['width'] if box else 0,
                            'height': box['height'] if box else 0,
                            'alt': alt or "",
                            'visible': is_visible
                        }
                    except Exception as e_img:
                        self.logger.debug(f"Could not get details for image {abs_url}: {e_img}")
                await browser.close()
        except Exception as e_pw:
            self.logger.error(f"Playwright failed for {url}: {e_pw}", exc_info=True)
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
        preliminary_blocks: List[PreliminaryBlock] = []
        raw_images: List[RawImageInput] = []
        try:
            tree = fromstring(xml_content)
        except Exception as e:
            self.logger.error(f"Failed to parse XML content with lxml: {e}")
            return preliminary_blocks, raw_images

        doc_element = tree.find('.//doc')
        if doc_element is None: doc_element = tree

        for element in doc_element:
            if element.tag == 'p' and element.text:
                preliminary_blocks.append(PreliminaryBlock(
                    block_id=f"{job_id}_xml_p_{len(preliminary_blocks)}", type="text",
                    text_content=element.text.strip(), order=-1))
            elif element.tag == 'head' and element.text:
                level_str = (element.get('rend') or 'h4').replace('h', '')
                try: level = int(level_str)
                except (ValueError, TypeError): level = 4
                preliminary_blocks.append(PreliminaryBlock(
                    block_id=f"{job_id}_xml_h_{len(preliminary_blocks)}", type="heading",
                    text_content=element.text.strip(), heading_level=level, order=-1))
            elif element.tag == 'graphic':
                img_src = element.get('src')
                if not img_src: continue
                img_abs_url = urljoin(base_url, img_src)
                raw_image_id = f"img_{job_id}_{len(raw_images)}"
                raw_images.append(RawImageInput(
                    image_id=raw_image_id, source_url=img_abs_url,
                    alt_text=element.text.strip() if element.text else None,
                    original_source_identifier_for_gcs_path=original_request_url,
                    source_type_for_gcs_path=source_type, job_id_for_gcs_path=job_id,
                    user_id=user_id, document_id=source_document_id))
                preliminary_blocks.append(PreliminaryBlock(
                    block_id=f"{job_id}_xml_img_{len(preliminary_blocks)}",
                    type="image_placeholder", image_id_ref=raw_image_id, order=-1))
        return preliminary_blocks, raw_images

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
        start_time = time.time()
        self.logger.info(f"WebService: Starting acquisition for URL: {web_input.url}")

        fetched_content, final_url, status_code = await self._fetch_html(web_input.url)
        if status_code != 200:
            return ServiceResult.failure(error_message=f"Failed to fetch URL. Status code: {status_code}")
        if not fetched_content:
            return ServiceResult.failure(error_message="Could not retrieve valid HTML content.")

        document_id = web_input.job_id or str(uuid.uuid4())
        user_id = web_input.user_id or "unknown_user_web_service"
        document_metadata = DocumentMetadata(
            document_id=document_id, user_id=user_id, source_identifier=web_input.url,
            source_type="url", title="Untitled Web Page", extracted_at=datetime.utcnow())

        xml_content = trafilatura.extract(
            fetched_content, output_format='xml', config=self.trafilatura_config)

        if not xml_content:
            self.logger.warning(f"Trafilatura failed to extract any main content from {web_input.url}")
            return ServiceResult.failure(error_message="Content extraction with Trafilatura failed.")

        playwright_image_details = None
        if web_input.processing_level == "full_content" and self.service_settings.use_playwright_for_image_filtering:
            playwright_image_details = await self._get_playwright_image_details(url=final_url, base_url_for_resolution=final_url)

        preliminary_blocks, raw_images = await self._parse_and_structure_html(
            xml_content=xml_content, base_url=final_url, original_request_url=web_input.url,
            job_id=document_id, user_id=user_id, playwright_image_details_map=playwright_image_details,
            source_document_id=document_id, source_type=document_metadata.source_type)
        
        try:
            tree = fromstring(xml_content.encode('utf-8'))
            title_element = tree.find('.//doc/title')
            if title_element is not None and title_element.text:
                document_metadata.title = title_element.text.strip()
            else:
                soup = BeautifulSoup(fetched_content, 'lxml')
                document_metadata.title = soup.title.string.strip() if soup.title else "Untitled"
        except Exception:
            document_metadata.title = os.path.basename(urlparse(web_input.url).path) or "Untitled"

        for i, block in enumerate(preliminary_blocks):
            block.order = i

        duration_ms = (time.time() - start_time) * 1000
        self.logger.info(f"WebService for '{web_input.url}' completed in {duration_ms:.2f} ms. Blocks: {len(preliminary_blocks)}, Images: {len(raw_images)}.")
        
        return ServiceResult.success(data=(preliminary_blocks, document_metadata, raw_images))