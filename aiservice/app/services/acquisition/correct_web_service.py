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

logger = logging.getLogger(__name__)

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
}

class CorrectWebAcquisitionService(BaseService):
    """
    Asynchronous service to fetch, parse, and extract content from web URLs.
    This service's logic is based on the stable build's web_service.py.
    Outputs PreliminaryBlock, DocumentMetadata, and RawImageInput.
    """
    MAIN_CONTENT_SELECTORS: List[str] = [
        "article", "main", "[role='main']",
        "#main", "#content", "#body",
        ".main-content", ".post", ".article",
        "#article-body", ".article-body",
        ".post-content", ".entry-content",
        ".blog-post", ".text"
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
        self.cache_ttl_seconds: int = self.service_settings.web_html_cache_ttl_seconds if hasattr(self.service_settings, 'web_html_cache_ttl_seconds') else 3600

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
                        image_details_map[abs_src] = { 'width': width, 'height': height, 'visible': is_visible, 'alt': alt, 'source_method': 'playwright' }
                    except Exception as e_img_detail:
                        self.logger.warning(f"Playwright: Error getting details for an image on {url}: {e_img_detail}")
                await browser.close()
        except Exception as e_pw_general:
            self.logger.error(f"Playwright: General error during execution for {url}: {e_pw_general}", exc_info=True)
        self.logger.debug(f"Playwright: Finished. Found details for {len(image_details_map)} images.")
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
        if isinstance(element, Comment):
            return False

        if isinstance(element, str): # NavigableString
            text_content_stripped = element.strip()
            if not text_content_stripped:
                return False

            current_order = len(blocks)
            if blocks and blocks[-1].type == "text" and hasattr(blocks[-1], 'text_content'):
                blocks[-1].text_content += " " + text_content_stripped
            else:
                block_id = f"pb_{job_id}_{current_order}"
                new_block = PreliminaryBlock(
                    block_id=block_id, type="text", text_content=text_content_stripped,
                    order=current_order, 
                    custom_attributes={'source_url': original_request_url, 'tag_name': None}
                )
                blocks.append(new_block)
            return False

        # If not a string or comment, it's a Tag
        tag_name = element.name.lower() if element.name else ""

        # ADDED: Explicitly skip script and style tags and their contents
        if tag_name in ['script', 'style']:
            return False # Continue processing siblings, but skip this tag and its children entirely

        # Tag processing starts here
        if tag_name in self.HEADING_TAGS or \
           (tag_name == "head" and element.attrs.get("rend", "").lower().startswith("h")):
            heading_text_content = element.get_text(separator=" ", strip=True)
            normalized_heading_text = heading_text_content.lower().strip()

            if normalized_heading_text in self.stop_headings:
                self.logger.info(f"FILTERED (Stop Heading): Encountered stop heading '{heading_text_content}'. Halting processing of further siblings.")
                return True 
            
            if not heading_text_content and tag_name == "head": # Trafilatura <head> specific text reconstruction
                 if hasattr(element, 'contents') and element.contents:
                    child_texts = [str(c).strip() for c in element.contents if str(c).strip()]
                    heading_text_content = " ".join(child_texts)

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
                first_heading_encountered[0] = True # ADDED: Set flag when heading is encountered
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
            return False

        elif tag_name == "img" or tag_name == "graphic":
            img_src = element.attrs.get("src")
            # MODIFIED: Check for other src attributes like data-src or srcset if primary src is missing/problematic
            if not img_src or img_src.startswith("data:image") or not img_src.strip():
                srcset = element.attrs.get("srcset")
                data_src = element.attrs.get("data-src")
                data_original = element.attrs.get("data-original")

                if srcset: # Simplistic srcset handling: take the first URL
                    img_src = srcset.strip().split(',')[0].strip().split(' ')[0]
                elif data_src:
                    img_src = data_src
                elif data_original:
                    img_src = data_original
                else:
                    # Try to get from <picture> parent if available
                    parent_picture = element.find_parent('picture')
                    if parent_picture:
                        source_tag = parent_picture.find('source', srcset=True)
                        if source_tag and source_tag.attrs.get("srcset"):
                            img_src = source_tag.attrs["srcset"].strip().split(',')[0].strip().split(' ')[0]
            
            alt_text = element.attrs.get("alt", "")

            if not img_src or img_src.startswith("data:image") or not img_src.strip():
                pass # Fall through to child recursion
            else:
                img_abs_url = urljoin(base_url, img_src.strip())

                if not first_heading_encountered[0]:
                    self.processed_image_urls.add(img_abs_url) 
                    return False

                if img_abs_url in self.processed_image_urls:
                    return False 

                if not self._check_image_keyword_filters(img_abs_url, alt_text):
                    return False

                final_alt_text = alt_text
                pw_rendered_width, pw_rendered_height = None, None

                perform_playwright_filtering = self.service_settings.use_playwright_for_image_filtering and playwright_image_details_map is not None and bool(playwright_image_details_map)
                if perform_playwright_filtering:
                    details = playwright_image_details_map.get(img_abs_url)
                    if not details or not details.get("visible"): return False
                    
                    pw_rendered_width = details.get("width", 0)
                    pw_rendered_height = details.get("height", 0)
                    if pw_rendered_width < self.service_settings.min_image_width or pw_rendered_height < self.service_settings.min_image_height: return False
                    if (pw_rendered_width * pw_rendered_height) < self.service_settings.min_image_area: return False
                    if details.get("alt"): final_alt_text = details.get("alt")
                
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
                self.processed_image_urls.add(img_abs_url)
                
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
            
            if img_src and not img_src.startswith("data:image"):
                 return False

        if hasattr(element, 'contents') and element.contents:
            for child_element in element.contents:
                if await self._process_html_element(child_element, blocks, base_url, job_id, user_id, all_raw_images, img_idx_counter, playwright_image_details_map, original_request_url, first_heading_encountered):
                    return True 
        
        return False

    async def _parse_and_structure_html(self, html_content: str, base_url: str, original_request_url: str, job_id: str, user_id: Optional[str], playwright_image_details_map: Optional[Dict[str, Dict[str, Any]]]) -> Tuple[List[PreliminaryBlock], List[RawImageInput]]:
        
        preliminary_blocks: List[PreliminaryBlock] = []
        all_raw_images: List[RawImageInput] = []
        img_idx_counter: List[int] = [0]
        first_heading_encountered: List[bool] = [False]

        soup = BeautifulSoup(html_content, 'html.parser')
        
        for child_element in soup.contents:
            await self._process_html_element(
                child_element, 
                preliminary_blocks, 
                base_url,
                job_id, 
                user_id,
                all_raw_images,
                img_idx_counter,
                playwright_image_details_map,
                original_request_url,
                first_heading_encountered
            )
        
        consolidated_blocks: List[PreliminaryBlock] = []
        if preliminary_blocks:
            current_block = preliminary_blocks[0]
            for next_block in preliminary_blocks[1:]:
                if current_block.type == "text" and next_block.type == "text" and hasattr(current_block, 'text_content') and hasattr(next_block, 'text_content'):
                    current_block.text_content += " " + next_block.text_content
                else:
                    consolidated_blocks.append(current_block)
                    current_block = next_block
            consolidated_blocks.append(current_block) 
        
        for i, block in enumerate(consolidated_blocks):
            block.order = i
        
        final_blocks = [b for b in consolidated_blocks if not (b.type == "text" and not getattr(b, 'text_content', "").strip())]

        return final_blocks, all_raw_images

    async def _is_content_behind_paywall(self, extracted_html_content: Optional[str], domain: Optional[str]) -> bool:
        if not extracted_html_content:
            if self._check_domain_in_set(domain, VERY_STRICT_PAYWALL_DOMAINS): return True
            return False
        extracted_html_lower = extracted_html_content.lower()
        if any(keyword in extracted_html_lower for keyword in PAYWALL_KEYWORDS): return True
        if self._check_domain_in_set(domain, VERY_STRICT_PAYWALL_DOMAINS) and len(extracted_html_content) < self.service_settings.minimal_content_length_threshold: return True
        return False

    async def execute(self, web_input: WebAcquisitionServiceInput) -> ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]:
        job_id_for_run = web_input.job_id or str(uuid.uuid4())
        user_id_for_run = web_input.user_id
        self.logger.info(f"WebService starting for URL: {web_input.url}, Job ID: {job_id_for_run}")
        
        doc_metadata = DocumentMetadata(document_id=job_id_for_run, user_id=user_id_for_run or "anonymous_web_acq", source_identifier=web_input.url, source_type='url', extracted_at=datetime.utcnow())
        
        try:
            # Step 1: Fetch the raw HTML content using a robust HTTP client
            async with httpx.AsyncClient(timeout=self.httpx_timeout, headers=self.headers, follow_redirects=True) as client:
                response = await client.get(web_input.url)
                final_url_after_redirects = str(response.url)
                doc_metadata.final_url = final_url_after_redirects
                doc_metadata.source_identifier = final_url_after_redirects
                response.raise_for_status()
                raw_html_content = await response.aread()

            try:
                fetched_content_str = raw_html_content.decode('utf-8')
            except UnicodeDecodeError:
                fetched_content_str = raw_html_content.decode('latin-1')

            # Step 2: Use Trafilatura to extract the main content as structured XML/HTML
            main_content_html = trafilatura.extract(
                fetched_content_str,
                url=final_url_after_redirects,
                output_format='xml', # KEY CHANGE
                include_links=True,
                include_images=True,
                include_comments=self.service_settings.trafilatura_include_comments,
                include_tables=self.service_settings.trafilatura_include_tables,
                favor_recall=self.service_settings.trafilatura_favor_recall,
                deduplicate=self.service_settings.trafilatura_deduplicate,
                config=self.trafilatura_config
            )

            # Step 3: Extract metadata from the full, original page content
            full_page_soup = BeautifulSoup(fetched_content_str, 'html.parser')
            doc_metadata.title = full_page_soup.find('title').string.strip() if full_page_soup.find('title') else "Untitled Webpage"

            # Step 4: Check for paywall
            final_domain = self._get_domain(final_url_after_redirects)
            if await self._is_content_behind_paywall(main_content_html, final_domain):
                doc_metadata.is_paywalled = True
                return ServiceResult.success(data=([], doc_metadata, []))

            # Step 5: Use Playwright if configured
            playwright_image_details_map = {}
            if self.service_settings.use_playwright_for_image_filtering:
                playwright_image_details_map = await self._get_playwright_image_details(final_url_after_redirects, final_url_after_redirects)

            # Step 6: Parse the cleaned, structured HTML from Trafilatura
            html_to_parse = main_content_html or fetched_content_str
            preliminary_blocks, raw_images = await self._parse_and_structure_html(
                html_to_parse, 
                final_url_after_redirects, 
                web_input.url, 
                job_id_for_run, 
                user_id_for_run, 
                playwright_image_details_map
            )
            
            return ServiceResult.success(data=(preliminary_blocks, doc_metadata, raw_images))

        except Exception as e:
            self.logger.error(f"WebService failed for {web_input.url}: {e}", exc_info=True)
            return ServiceResult.failure(error_message=f"Failed to process URL {web_input.url}: {str(e)}")