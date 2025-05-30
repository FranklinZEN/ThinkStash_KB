import asyncio
import hashlib
import time
import aiohttp
from bs4 import BeautifulSoup, Tag
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

from pydantic import BaseModel, Field, HttpUrl

from aiservice.app.services.base import BaseService, ServiceResult
from aiservice.app.models.pipeline_models import PreliminaryBlock, DocumentMetadata, RawImageInput
# Import PDFAcquisitionService and its input model
from aiservice.app.services.acquisition.pdf_service import PDFAcquisitionService, PDFAcquisitionServiceInput

# --- Pydantic Models for WebAcquisitionService ---

class WebAcquisitionServiceInput(BaseModel):
    url: str = Field(..., description="The URL to fetch and process.")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images. 'full_content' enables image extraction.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking or unique ID generation.")

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
        "article",
        "main",
        "[role='main']",
        "#main",
        "#content",
        ".content",
        "#main-content", # Common ID
        ".main-content", # Common class
        "#primary", # Common ID in WordPress
        ".post", # Common class for blog posts
        ".entry", # Common class for entries
        ".page-content", # Common class
        "#article", ".article", # Common for articles
        "#article-body", ".article-body",
        ".post-content", ".entry-content",
        ".blog-post", # Common class
        ".text" # Sometimes used for main text container
    ]

    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        self.settings_instance = settings # Store the settings instance if provided
        self.logger = logging.getLogger(__name__) # Initialize logger
        if self.settings_instance and hasattr(self.settings_instance, 'debug_mode') and self.settings_instance.debug_mode:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        # In-memory cache for HTML content: {url: (html_string, fetch_timestamp)}
        self.html_cache: Dict[str, Tuple[str, float]] = {}
        # Cache Time-To-Live in seconds
        if self.settings_instance and hasattr(self.settings_instance, 'web_html_cache_ttl_seconds'):
            self.cache_ttl_seconds: int = self.settings_instance.web_html_cache_ttl_seconds
        else:
            self.cache_ttl_seconds: int = 3600 # Fallback if settings not provided or field missing
        
        # For now, creating session per call for simplicity.

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

    async def _extract_images_from_html(self, 
                                        html_content_str: str, 
                                        base_url: str, 
                                        job_id: Optional[str],
                                        original_source_identifier_for_gcs_path: str,
                                        source_type_for_gcs_path: str
                                        ) -> List[RawImageInput]:
        """
        Extracts image URLs and metadata from HTML content, creating RawImageInput objects.
        Does NOT download image bytes.
        """
        raw_images: List[RawImageInput] = []
        processed_urls: Set[str] = set()
        soup = BeautifulSoup(html_content_str, 'lxml')
        image_counter = 0 # Used for generating image_id if job_id is missing

        MIN_DIMENSION = 50
        MIN_AREA = 5000
        MAX_ASPECT_RATIO_DEVIATION = 4.0 

        IRRELEVANT_ALT_STRINGS_EXACT = [
            "logo", "avatar", "icon", "profile", "banner", "ad", "advertisement", 
            "pinterest", "pinterest engineering", "pinterest engineering blog", "walmart global tech blog",
            "user", "author", "default", "placeholder", "loading", "spinner", "spacer", "pixel",
            "figure", "image", "photo", "illustration", "diagram"
        ]
        IRRELEVANT_SUBSTRINGS_IN_ALT = [
            "logo", "avatar", "icon", "profile", "banner", "advert", "promo", "social", "button", "rating", 
            "star", "user photo", "profile picture", "author bio", "site badge", "user badge", "blog logo"
        ]
        IRRELEVANT_URL_SEGMENTS = [
            "/logo", "/avatar", "/icon", "/banner", "/profile", "/badge", "/sprite", 
            "/spinner", "/loader", "/ads/", "/ad/", "/advert/", "pixel.gif", "spacer.gif",
            "/track", "/beacon", "gravatar.com", "/share_", "_share.", "/social_", "_social.",
            "feedburner.com", "doubleclick.net", "googlesyndication.com", "adservice.google.com",
            "feeds.feedburner.com", "ad.doubleclick.net", "stats.wordpress.com", "blogger.googleusercontent.com/img/b"
        ]
        ALLOWED_CONTENT_PATH_INDICATORS = [ 
            "/content/", "/media/", "/wp-content/uploads/", "/uploads/", "/images/", "/image/",
            "/wp-content/uploads", "/files/", "/assets/", "/_posts/", "/posts/", "/articles/", "/article/"
        ]

        # Consistent image_id generation
        doc_id_prefix = hashlib.md5(original_source_identifier_for_gcs_path.encode()).hexdigest()[:8]

        # 1. Standard <img> tags
        for idx, img_tag in enumerate(soup.find_all('img')):
            if not isinstance(img_tag, Tag): continue
            src = img_tag.get('src')
            if not src: src = img_tag.get('data-src')
            if not src: src = img_tag.get('data-original')
            if not src or str(src).startswith('data:image'):
                continue

            try:
                abs_img_url_str = urljoin(base_url, str(src).strip())
                if abs_img_url_str in processed_urls:
                    continue

                # --- Filtering Logic (Enhanced, from existing code) ---
                abs_img_url_lower = abs_img_url_str.lower()
                is_url_potentially_irrelevant = any(segment in abs_img_url_lower for segment in IRRELEVANT_URL_SEGMENTS)
                is_url_explicitly_content = any(indicator in abs_img_url_lower for indicator in ALLOWED_CONTENT_PATH_INDICATORS)
                if is_url_potentially_irrelevant and not is_url_explicitly_content:
                    continue

                alt_text_raw = img_tag.get('alt', '').strip()
                alt_text_lower = alt_text_raw.lower()
                if alt_text_lower in IRRELEVANT_ALT_STRINGS_EXACT:
                    continue
                is_irrelevant_substring = any(substring in alt_text_lower for substring in IRRELEVANT_SUBSTRINGS_IN_ALT)
                if is_irrelevant_substring:
                    continue
                
                width_str = img_tag.get('width')
                height_str = img_tag.get('height')
                width = int(width_str.replace('px','')) if width_str and width_str.replace('px','').isdigit() else None
                height = int(height_str.replace('px','')) if height_str and height_str.replace('px','').isdigit() else None

                if width is not None and width < MIN_DIMENSION: continue
                if height is not None and height < MIN_DIMENSION: continue
                if width is not None and height is not None:
                    if width * height < MIN_AREA: continue
                    if height > 0 and (width / height > MAX_ASPECT_RATIO_DEVIATION): continue
                    if width > 0 and (height / width > MAX_ASPECT_RATIO_DEVIATION): continue
                # --- End Filtering Logic ---

                validated_url = HttpUrl(abs_img_url_str) # Validate URL
                processed_urls.add(abs_img_url_str)
                image_counter += 1
                
                image_id = f"WEB_IMG_{job_id if job_id else doc_id_prefix}_{image_counter}"

                alt_text = alt_text_raw or None
                caption_text: Optional[str] = None
                figure_parent = img_tag.find_parent('figure')
                if figure_parent and isinstance(figure_parent, Tag):
                    figcaption = figure_parent.find('figcaption')
                    if figcaption and isinstance(figcaption, Tag): caption_text = figcaption.get_text(strip=True)
                if not caption_text:
                    title_attr = img_tag.get('title','').strip()
                    if title_attr: caption_text = title_attr
                    # Removed using alt_text as caption if long, as it's often redundant.

                raw_images.append(RawImageInput(
                    image_id=image_id,
                    image_bytes=None, # Bytes are not downloaded by acquisition service
                    source_url=str(validated_url),
                    original_filename=os.path.basename(urlparse(str(validated_url)).path) or f"image_{image_counter}.png", # Best guess
                    source_document_id=original_source_identifier_for_gcs_path, # e.g., final_url
                    page_number=None, # Not applicable for web pages in this context
                    bbox=None, # Not applicable from typical web <img> tags
                    mime_type=None, # Could try to infer from URL extension, but often unreliable
                    alt_text=alt_text,
                    caption=caption_text,
                    original_source_identifier_for_gcs_path=original_source_identifier_for_gcs_path,
                    source_type_for_gcs_path=source_type_for_gcs_path, # "url"
                    job_id_for_gcs_path=job_id if job_id else "unknown_job"
                ))
            except ValueError: # Pydantic validation error for HttpUrl
                continue
            except Exception: # Catch any other error during image processing
                # self.logger.warning(f"Error processing image tag {img_tag}: {e}", exc_info=True) # Optional logging
                continue
        
        # 2. Consider <meta property="og:image" ...>
        og_image_tag = soup.find('meta', property='og:image')
        if og_image_tag and isinstance(og_image_tag, Tag) and og_image_tag.get('content'):
            og_image_url_str = urljoin(base_url, str(og_image_tag['content']).strip())
            if og_image_url_str not in processed_urls:
                try:
                    validated_og_url = HttpUrl(og_image_url_str)
                    processed_urls.add(og_image_url_str)
                    image_counter += 1
                    image_id = f"WEB_IMG_{job_id if job_id else doc_id_prefix}_{image_counter}_og"
                    
                    og_alt = None
                    og_image_alt_tag = soup.find('meta', property='og:image:alt')
                    if og_image_alt_tag and isinstance(og_image_alt_tag, Tag) and og_image_alt_tag.get('content'):
                        og_alt = str(og_image_alt_tag['content']).strip()

                    raw_images.append(RawImageInput(
                        image_id=image_id,
                        image_bytes=None,
                        source_url=str(validated_og_url),
                        original_filename=os.path.basename(urlparse(str(validated_og_url)).path) or f"og_image_{image_counter}.png",
                        source_document_id=original_source_identifier_for_gcs_path,
                        alt_text=og_alt,
                        # caption usually not available for og:image
                        original_source_identifier_for_gcs_path=original_source_identifier_for_gcs_path,
                        source_type_for_gcs_path=source_type_for_gcs_path,
                        job_id_for_gcs_path=job_id if job_id else "unknown_job"
                    ))
                except ValueError:
                    pass # Invalid og:image URL
                except Exception:
                    pass # Other error with og:image

        # 3. Look for images in <figure> tags that might not have been caught
        # This might be redundant if all relevant images within figures are <img> tags.

        return raw_images

    async def _parse_and_structure_html(
        self, 
        html_to_parse: str, # This will be either Trafilatura's snippet or full HTML
        is_trafilatura_content: bool, # Flag to indicate the source of html_to_parse
        full_html_content_for_metadata_and_images: str, # Always the original full HTML
        final_url: str, 
        job_id: Optional[str], 
        processing_level: str
    ) -> Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]:
        
        preliminary_blocks: List[PreliminaryBlock] = []
        raw_images_list: List[RawImageInput] = []
        
        # Full page soup for metadata and image extraction - always from original full HTML
        soup_full_page = BeautifulSoup(full_html_content_for_metadata_and_images, 'lxml')
        
        isolated_main_content_html: Optional[str] = None # Will be set if not using Trafilatura content
        main_content_element_found: Optional[Tag] = None # Will be set if not using Trafilatura content
        soup_for_structuring: Optional[Union[BeautifulSoup, Tag]] = None # Can be the whole doc or a specific tag

        if is_trafilatura_content and html_to_parse:
            self.logger.info("Using Trafilatura's extracted HTML snippet for structuring.")
            temp_soup = BeautifulSoup(html_to_parse, 'lxml')
            main_tag_in_snippet = temp_soup.find('main')
            if main_tag_in_snippet:
                soup_for_structuring = main_tag_in_snippet 
            elif temp_soup.find('doc'): # Trafilatura often uses <doc>
                doc_tag_in_snippet = temp_soup.find('doc')
                soup_for_structuring = doc_tag_in_snippet
            else:
                soup_for_structuring = temp_soup 
        else:
            self.logger.info("Trafilatura content not used or empty. Falling back to BeautifulSoup parsing of full HTML.")
            # --- Start Fallback Main Content Isolation using BeautifulSoup Selectors ---
            main_content_element_found: Optional[Tag] = None
            for selector in self.MAIN_CONTENT_SELECTORS:
                try:
                    candidate_element = soup_full_page.select_one(selector)
                    if candidate_element:
                        if candidate_element.find(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']) and len(candidate_element.get_text(strip=True)) > 200:
                            main_content_element_found = candidate_element
                            log_snippet_raw = str(main_content_element_found)[:500]
                            log_snippet_clean = log_snippet_raw.replace('\n', ' ')
                            self.logger.debug(f"(Fallback) Selected main content element with selector '{selector}'. HTML snippet: {log_snippet_clean}")
                            break
                except Exception as e_select:
                    self.logger.warning(f"(Fallback) Selector error ('{selector}') during main content isolation: {e_select}")
                    pass
            self.logger.debug("Finished Main Content Isolation (Fallback BS4).")

            if main_content_element_found:
                log_isolated_snippet_raw = str(main_content_element_found)[:500]
                log_isolated_snippet_clean = log_isolated_snippet_raw.replace('\n', ' ')
                self.logger.debug(f"(Fallback) Using ISOLATED main content for structuring. Initial HTML: {log_isolated_snippet_clean}")
                isolated_main_content_html = str(main_content_element_found)
                soup_for_structuring = BeautifulSoup(isolated_main_content_html, 'lxml')
            else:
                self.logger.info("(Fallback) No specific main content container found by BS4, using full body/page for structuring.")
                if soup_full_page.body:
                    soup_for_structuring = BeautifulSoup(str(soup_full_page.body), 'lxml')
                else:
                    soup_for_structuring = soup_full_page
        
        # --- 0.B Remove Boilerplate Content (from the selected soup_for_structuring) ---
        # This runs whether content is from Trafilatura or BS4 fallback
        # print("--- Starting Boilerplate Removal ---") # DEBUG PRINT
        for selector_idx, selector in enumerate(BOILERPLATE_SELECTORS):
            try:
                # Ensure soup_for_structuring is not None before calling .select()
                if soup_for_structuring:
                    # print(f"DEBUG: Processing boilerplate selector #{selector_idx+1}/{len(BOILERPLATE_SELECTORS)}: {selector}") # DEBUG PRINT
                    elements_found = soup_for_structuring.select(selector)
                    # print(f"DEBUG: Found {len(elements_found)} elements for selector: {selector}") # DEBUG PRINT
                    
                    for i, element in enumerate(elements_found):
                        if element:
                            # if selector in ("nav", "header", "a[data-baseweb='button'][href*='m.uber.com/looking']"): # Example of selective uncommenting
                            #     print(f"DEBUG: Decomposing element {i+1}/{len(elements_found)} for selector '{selector}': {str(element)[:300]}")
                            element.decompose()
                else:
                    # print(f"DEBUG: soup_for_structuring is None, skipping boilerplate selector: {selector}")
                    pass # No need to print if it's none, just skip
            except Exception as e_decompose:
                # self.logger.warning(f"Error decomposing boilerplate with selector '{selector}': {e_decompose}") # Optional logging
                self.logger.warning(f"Error decomposing boilerplate with selector '{selector}': {e_decompose}")
                pass
        # print("--- Finished Boilerplate Removal ---") # DEBUG PRINT
        
        # --- 1. Populate DocumentMetadata (using soup_full_page for broader context like <head>) ---
        doc_title: Optional[str] = None
        if soup_full_page.title and soup_full_page.title.string:
            doc_title = soup_full_page.title.string.strip()
        
        og_title_tag = soup_full_page.find('meta', property='og:title')
        if og_title_tag and isinstance(og_title_tag, Tag) and og_title_tag.get('content'):
            og_title = str(og_title_tag['content']).strip()
            if og_title: doc_title = og_title

        og_description_tag = soup_full_page.find('meta', property='og:description')
        og_description = str(og_description_tag['content']).strip() if og_description_tag and isinstance(og_description_tag, Tag) and og_description_tag.get('content') else None
        
        meta_description_tag = soup_full_page.find('meta', attrs={'name': 'description'})
        meta_description = str(meta_description_tag['content']).strip() if meta_description_tag and isinstance(meta_description_tag, Tag) and meta_description_tag.get('content') else None
        
        description = og_description or meta_description

        source_identifier_for_gcs = final_url 
        source_type_for_gcs = "url"
        doc_job_id = job_id or f"web_{uuid.uuid4().hex[:8]}"

        document_metadata_obj = DocumentMetadata(
            document_id=doc_job_id, 
            source_identifier=final_url,
            source_type="url",
            final_url=final_url,
            title=doc_title,
            custom_fields={"description": description} if description else {},
            extracted_at=datetime.utcnow()
        )

        # --- 2. Extract RawImageInput objects (if full_content) ---
        # Always use the original full HTML for image extraction
        if processing_level == "full_content":
            raw_images_list = await self._extract_images_from_html(
                html_content_str=full_html_content_for_metadata_and_images, 
                base_url=final_url, 
                job_id=doc_job_id,
                original_source_identifier_for_gcs_path=source_identifier_for_gcs,
                source_type_for_gcs_path=source_type_for_gcs
            )

        # Ensure soup_for_structuring is not None before iterating
        iterable_elements = []
        if soup_for_structuring:
            iterable_elements = soup_for_structuring.find_all(True, recursive=True) 
        else:
            self.logger.error("soup_for_structuring is None before block extraction loop. No blocks will be generated.")

        processed_elements = set() 
        block_order = 0 

        # Variables for block data - initialize outside loop for clarity if needed for complex types
        heading_level_val: Optional[int] = None
        list_item_data_val: Optional[Any] = None
        list_level_val: Optional[int] = None
        list_ordered_val: Optional[bool] = None
        code_content_val: Optional[str] = None
        code_language_val: Optional[str] = None
        table_html_content_val: Optional[str] = None
        image_id_ref_val: Optional[str] = None

        for element_idx, element in enumerate(iterable_elements):
            # print(f"\nDEBUG WebAcquisitionService: --- Element Loop Start [#{element_idx + 1}/{len(iterable_elements)}] --- Tag: <{element.name}> ---")
            
            if element in processed_elements:
                # print(f"DEBUG WebAcquisitionService: Element <{element.name}> already processed. Skipping.")
                continue
            if not element.name:
                # print(f"DEBUG WebAcquisitionService: Element has no name. Skipping.")
                continue

            tags_to_skip_directly = ['script', 'style', 'meta', 'link', 'noscript', 'header', 'footer', 'nav', 'aside', 'form', 'button', 'input', 'select', 'textarea', 'label', 'option', 'doc', 'main']
            if element.name in tags_to_skip_directly:
                # print(f"DEBUG WebAcquisitionService: Element <{element.name}> is in direct skip list. Skipping.")
                for desc in element.find_all(True, recursive=True): processed_elements.add(desc)
                processed_elements.add(element)
                continue

            block_type: Optional[str] = None
            text_content: Optional[str] = None
            # Reset specific attributes for each element
            heading_level_val = None; list_item_data_val = None; list_level_val = None; list_ordered_val = None; code_content_val = None; code_language_val = None; table_html_content_val = None; image_id_ref_val = None

            current_element_text_content = element.get_text(separator=' ', strip=True)
            # print(f"DEBUG WebAcquisitionService: Element <{element.name}> extracted text (first 100 chars): '{current_element_text_content[:100]}'")

            if element.name == 'p':
                block_type = "text"; text_content = current_element_text_content
            elif element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                block_type = "heading"; text_content = current_element_text_content
                heading_level_val = int(element.name[1:])
            elif element.name == 'pre':
                block_type = "code_snippet"
                code_tag = element.find('code')
                code_content_val = code_tag.get_text(strip=True) if code_tag else current_element_text_content
                # Basic language detection from class (can be improved)
                lang_class = element.get('class', []) + (code_tag.get('class', []) if code_tag else [])
                for cls in lang_class:
                    if cls.startswith('language-'): code_language_val = cls.replace('language-', ''); break
                    if cls.startswith('lang-'): code_language_val = cls.replace('lang-', ''); break
            elif element.name == 'table':
                block_type = "table_placeholder"; table_html_content_val = str(element)
            elif element.name == 'li':
                block_type = "list_item"; text_content = current_element_text_content
                list_item_data_val = current_element_text_content
                parent_list = element.find_parent(['ul', 'ol'])
                list_ordered_val = parent_list.name == 'ol' if parent_list else False
                list_level_val = sum(1 for _ in element.find_parents(['ul', 'ol']))
            elif element.name in ['ul', 'ol']:
                # print(f"DEBUG WebAcquisitionService: Element <{element.name}> is list container. Individual <li> will be processed. Skipping direct block for <{element.name}>.")
                # Mark children as processed to avoid creating blocks from them AND their parent list tag
                for desc in element.find_all(True, recursive=True): processed_elements.add(desc)
                processed_elements.add(element) # Mark the list tag itself as processed
                continue # Explicitly skip creating a block for <ul>/<ol> itself
            
            # Fallback: if it has significant text and isn't one of the above structural tags AND not a container of them
            elif current_element_text_content and len(current_element_text_content) > 20: # Min length for fallback text block
                is_container_of_handled_types = False
                for child in element.children:
                    if isinstance(child, Tag) and child.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'table', 'ul', 'ol', 'li']:
                        is_container_of_handled_types = True; break
                if not is_container_of_handled_types:
                    block_type = "text"; text_content = current_element_text_content
                    # print(f"DEBUG WebAcquisitionService: Element <{element.name}> processed by FALLBACK text logic.")
                else:
                    # print(f"DEBUG WebAcquisitionService: Element <{element.name}> has text but is a container of other handled types. Skipping direct block creation.")
                    pass # No need to print, just skip
            
            # print(f"DEBUG WebAcquisitionService: After type decision for <{element.name}>: block_type='{block_type}', text_content present: {text_content is not None}")

            if block_type and (text_content or list_item_data_val or code_content_val or table_html_content_val or block_type == 'image_placeholder'):
                block_id = f"{job_id if job_id else 'doc'}_b{block_order}"
                prelim_block_data = {
                    "block_id": block_id, "type": block_type, "order": block_order,
                    "text_content": text_content, "page_number": None, "bbox": None,
                    "heading_level": heading_level_val, "list_item_data": list_item_data_val,
                    "list_level": list_level_val, "list_ordered": list_ordered_val,
                    "code_content": code_content_val, "code_language": code_language_val,
                    "custom_attributes": {"html_content": table_html_content_val} if table_html_content_val else None,
                    "image_id_ref": image_id_ref_val
                }
                # Filter out None values before passing to Pydantic model
                final_prelim_block_data = {k: v for k, v in prelim_block_data.items() if v is not None}
                
                # Limited debug print for created blocks
                debug_content_preview = ""
                if text_content: debug_content_preview = text_content[:70] + "..." if len(text_content) > 70 else text_content
                elif list_item_data_val: debug_content_preview = str(list_item_data_val)[:70] + "..." if len(str(list_item_data_val)) > 70 else str(list_item_data_val)
                elif code_content_val: debug_content_preview = code_content_val[:70] + "..." if len(code_content_val) > 70 else code_content_val
                
                if block_order < 5 or block_order % 10 == 0 : # Print for first 5 and then every 10th block
                    self.logger.debug(f"CREATED PrelimBlock for <{element.name}>: ID {block_id}, Type '{block_type}', Order {block_order}. Content: '{debug_content_preview}'")
                
                preliminary_blocks.append(PreliminaryBlock(**final_prelim_block_data)) # type: ignore
                block_order += 1
                # Mark the element and all its descendants as processed
                for desc in element.find_all(True, recursive=True): processed_elements.add(desc)
                processed_elements.add(element)

        # After loop, add image placeholders based on raw_images_list (extracted from full HTML)
        # This assumes raw_images_list is populated correctly by _extract_images_from_html
        if raw_images_list:
            self.logger.debug(f"Adding {len(raw_images_list)} image placeholders as PreliminaryBlocks.")
        for img_raw_input in raw_images_list:
            block_id = f"{job_id if job_id else 'doc'}_img_b{block_order}"
            preliminary_blocks.append(PreliminaryBlock(
                block_id=block_id,
                type="image_placeholder",
                image_id_ref=img_raw_input.image_id,
                order=block_order,
                page_number=img_raw_input.page_number, # Will be None for web
                bbox=img_raw_input.bbox # Will be None for web
                # alt_text and caption from RawImageInput are not directly part of PreliminaryBlock for image_placeholder
                # They are associated via EnrichedImageMetadata later.
            ))
            block_order += 1
            self.logger.debug(f"CREATED image_placeholder PreliminaryBlock: ID {block_id}, ImageRef {img_raw_input.image_id}, Order {block_order-1}.")

        self.logger.info(f"_parse_and_structure_html finished. Total PreliminaryBlocks created: {len(preliminary_blocks)} (incl. images).")
        # Ensure preliminary_blocks are sorted by order before returning
        preliminary_blocks.sort(key=lambda b: b.order)
        
        # Filter boilerplate text blocks AFTER all blocks (including images) have been ordered
        if preliminary_blocks: # Only filter if there are any blocks
            self.logger.debug(f"Calling _filter_boilerplate_preliminary_blocks with {len(preliminary_blocks)} blocks.")
            preliminary_blocks = self._filter_boilerplate_preliminary_blocks(preliminary_blocks, final_url)
            self.logger.debug(f"After _filter_boilerplate_preliminary_blocks, {len(preliminary_blocks)} blocks remaining.")

        return preliminary_blocks, document_metadata_obj, raw_images_list

    def _filter_boilerplate_preliminary_blocks(self, blocks: List[PreliminaryBlock], source_url_for_logging: str) -> List[PreliminaryBlock]:
        """ 
        Filters PreliminaryBlock objects that are likely boilerplate based on common patterns
        in their text_content. This is a secondary filter after HTML element decomposition.
        """
        if not blocks:
            return []

        # Compile regex patterns for efficiency if they are numerous or complex
        # For now, using simple string checks
        # Updated to be more conservative and focus on very common boilerplate indicators
        # that often survive initial HTML tag-based removal.
        PATTERNS_TO_FILTER = [
            re.compile(r"^\s*copyright\s*(©|\(c\))?\s*\d{4}(-\d{4})?\s*.+", re.IGNORECASE),
            re.compile(r"all\s+rights\s+reserved", re.IGNORECASE),
            re.compile(r"privacy\s+policy", re.IGNORECASE),
            re.compile(r"terms\s+of\s+(service|use|condition)", re.IGNORECASE),
            re.compile(r"cookie\s+(settings|preferences|policy)", re.IGNORECASE),
            re.compile(r"site\s+map", re.IGNORECASE),
            re.compile(r"powered\s+by", re.IGNORECASE),
            re.compile(r"^(subscribe|follow us|newsletter|sign up for our newsletter)$", re.IGNORECASE),
            re.compile(r"share\s+this\s+page", re.IGNORECASE),
            re.compile(r"log\s+in\s+/\s+register", re.IGNORECASE),
            re.compile(r"(previous|next)\s+(post|article)", re.IGNORECASE),
            re.compile(r"related\s+(articles|posts)", re.IGNORECASE),
            re.compile(r"leave\s+a\s+comment", re.IGNORECASE),
            re.compile(r"you\s+may\s+also\s+like", re.IGNORECASE),
            re.compile(r"advertisement", re.IGNORECASE), # Generic ad text
            re.compile(r"back\s+to\s+top", re.IGNORECASE),
            # Very short, likely navigation/utility links (be careful with these)
            re.compile(r"^\s*(home|about|contact|help|faq|blog|docs|support|careers)\s*$", re.IGNORECASE),
        ]

        MIN_TEXT_LENGTH_FOR_FILTERING = 10 # Don't filter very short text unless it's an exact match above
        MAX_TEXT_LENGTH_FOR_SHORT_LINK_FILTER = 25 # Max length for the very generic link filter

        filtered_blocks = []
        for block in blocks:
            if block.type == "text" and block.text_content:
                text_to_check = block.text_content.strip()
                is_boilerplate = False
                for pattern in PATTERNS_TO_FILTER:
                    if pattern.search(text_to_check):
                        # For the short link filter, apply length constraint
                        if pattern.pattern == r"^\s*(home|about|contact|help|faq|blog|docs|support|careers)\s*$" and len(text_to_check) > MAX_TEXT_LENGTH_FOR_SHORT_LINK_FILTER:
                            continue # Don't filter if it's a short link pattern but the text is longer
                        
                        # self.logger.debug(f"Filtering block ID {block.block_id} due to pattern: '{pattern.pattern}'. Text: '{text_to_check[:100]}...'")
                        is_boilerplate = True
                        break
                
                if not is_boilerplate:
                    filtered_blocks.append(block)
                # else: Keep the print above for when a block IS filtered by text
            else:
                # Non-text blocks or text blocks with no content are kept
                filtered_blocks.append(block)
        
        if len(blocks) != len(filtered_blocks):
            # self.logger.debug(f"Filtered out {len(blocks) - len(filtered_blocks)} boilerplate PreliminaryBlocks based on text patterns from {source_url_for_logging}.")
            pass

        return filtered_blocks

    async def execute(self, web_input: WebAcquisitionServiceInput) -> ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]:
        request_start_time = time.time()
        url = web_input.url
        job_id = web_input.job_id or f"web_job_{uuid.uuid4().hex[:8]}"
        processing_level = web_input.processing_level

        # Initialize variables that will be part of the successful return tuple
        preliminary_blocks_list: List[PreliminaryBlock] = []
        raw_images_list: List[RawImageInput] = [] # Use raw_images_list consistently
        
        # Initialize document_metadata_obj early and fully for consistent error returns
        document_metadata_obj = DocumentMetadata(
            document_id=job_id,
            source_identifier=url, # Use the input URL as the primary identifier
            source_type='url', 
            extracted_at=datetime.utcnow()
        )
        
        html_content_str: Optional[str] = None
        final_url_val: str = url # Start with input URL, will be updated by redirects if fetch occurs
        pdf_bytes_val: Optional[bytes] = None
        temp_pdf_file_path: Optional[str] = None

        # --- Cache Check ---
        current_time = time.time()
        if url in self.html_cache:
            cached_html, fetch_time = self.html_cache[url]
            if (current_time - fetch_time) < self.cache_ttl_seconds:
                self.logger.info(f"HTML cache HIT for {url}")
                html_content_str = cached_html
                # final_url_val remains 'url' (original input) if from cache
            else:
                self.logger.info(f"HTML cache STALE for {url}")
                del self.html_cache[url]

        # --- If cache miss or stale, proceed to fetch and then process ---
        if html_content_str is None: 
            self.logger.info(f"HTML cache MISS for {url}. Fetching...")
            
            normalized_url = url 
            if normalized_url.startswith("chrome-extension://"):
                match = re.search(r"(https?:\\\\/\\\\/[^\\\\s]+)", normalized_url)
                if match:
                    normalized_url = match.group(1)
                else:
                    return ServiceResult.failure(
                        error_message=f"Cannot fetch local file from chrome-extension URL: {url}",
                        error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)}
                    )
            
            parsed_normalized_url = urlparse(normalized_url)
            if not parsed_normalized_url.scheme:
                if parsed_normalized_url.netloc or (parsed_normalized_url.path and '.' in parsed_normalized_url.path.split('/')[0]):
                    normalized_url = f"https://{normalized_url}"
                else:
                     return ServiceResult.failure(
                        error_message=f"Invalid URL format (cannot determine scheme): {url}",
                        error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)}
                    )
            elif parsed_normalized_url.scheme not in ["http", "https"]:
                return ServiceResult.failure(
                    error_message=f"Unsupported URL scheme '{parsed_normalized_url.scheme}' in URL: {normalized_url}",
                    error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)}
                )

            try: # This try is for the network fetching part
                parsed_url_for_domain_check = urlparse(normalized_url) # Use normalized for domain checks
                if not all([parsed_url_for_domain_check.scheme, parsed_url_for_domain_check.netloc]):
                     return ServiceResult.failure(error_message=f"Invalid URL format after normalization: {normalized_url}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})

                domain = self._get_domain(normalized_url)
                if self._check_domain_in_set(domain, UNSUPPORTED_URL_TYPE_DOMAINS):
                    is_allowed_social = any(re.search(pattern, normalized_url, re.IGNORECASE) for pattern in ALLOWED_SOCIAL_MEDIA_POST_PATTERNS)
                    if not is_allowed_social:
                        return ServiceResult.failure(error_message=f"Unsupported domain: {domain} in URL: {normalized_url}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})

                async with aiohttp.ClientSession() as session:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    }
                    async with session.get(normalized_url, timeout=30, allow_redirects=True, headers=headers) as response:
                        final_url_val = str(response.url) # Update final_url_val after actual fetch
                        document_metadata_obj.final_url = final_url_val # Update metadata with the truly final URL

                        if response.status != 200:
                            return ServiceResult.failure(error_message=f"HTTP error {response.status} for URL: {final_url_val}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})

                        content_type = response.headers.get('Content-Type', '').lower()
                        if 'application/pdf' in content_type:
                            pdf_bytes_val = await response.read()
                        elif 'text/html' in content_type or 'application/xhtml+xml' in content_type or not content_type:
                            html_content_str = await response.text()
                            if html_content_str: # Store non-empty HTML in cache
                                self.html_cache[url] = (html_content_str, time.time()) # Use original 'url' as key
                                self.logger.info(f"Stored HTML in cache for {url}")
                        else:
                            return ServiceResult.failure(error_message=f"Unsupported content type: {content_type} for URL: {final_url_val}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})
            
            except aiohttp.ClientError as e_net:
                return ServiceResult.failure(error_message=f"Network/HTTP error fetching URL {normalized_url}: {str(e_net)}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})
            except asyncio.TimeoutError:
                return ServiceResult.failure(error_message=f"Timeout fetching URL {normalized_url}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})
            except Exception as e_fetch_prep: # Catch other errors during pre-fetch or fetch setup
                return ServiceResult.failure(error_message=f"Error during URL fetch preparation for {url}: {str(e_fetch_prep)}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})
        
        # --- Content Processing (PDF or HTML) ---
        # This block executes if html_content_str was from cache OR successfully fetched and set.
        # Or if pdf_bytes_val was set.
        try:
            if pdf_bytes_val: # final_url_val would have been updated if fetch occurred
                # --- Route to PDFAcquisitionService ---
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
                        tmpfile.write(pdf_bytes_val)
                        temp_pdf_file_path = tmpfile.name
                    
                    pdf_acq_service = PDFAcquisitionService(settings=self.settings) # Assuming settings can be passed
                    pdf_input_obj = PDFAcquisitionServiceInput(
                        file_path=temp_pdf_file_path,
                        job_id=job_id, # Pass along the job_id
                        processing_level=processing_level # Pass along processing_level
                    )
                    pdf_service_result = await pdf_acq_service.execute(pdf_input_obj)

                    if pdf_service_result.success and pdf_service_result.data:
                        preliminary_blocks_list, pdf_doc_metadata, raw_images_list = pdf_service_result.data
                        
                        # Merge DocumentMetadata: Keep original web URL, update with PDF specific info if valuable
                        # The document_metadata_obj is already initialized with web source info.
                        # We can enrich it with PDF-specific metadata if needed.
                        if document_metadata_obj and pdf_doc_metadata:
                            document_metadata_obj.title = pdf_doc_metadata.title or document_metadata_obj.title
                            document_metadata_obj.author = pdf_doc_metadata.author or document_metadata_obj.author
                            document_metadata_obj.subject = pdf_doc_metadata.subject or document_metadata_obj.subject
                            document_metadata_obj.keywords = pdf_doc_metadata.keywords or document_metadata_obj.keywords
                            document_metadata_obj.creation_date = pdf_doc_metadata.creation_date or document_metadata_obj.creation_date
                            document_metadata_obj.modification_date = pdf_doc_metadata.modification_date or document_metadata_obj.modification_date
                            document_metadata_obj.total_pages = pdf_doc_metadata.total_pages
                            # Ensure source_identifier remains the original URL, source_type 'url'
                            document_metadata_obj.source_type = "pdf_from_url" # Or keep as 'url' and add custom field? Let's mark as pdf_from_url
                        
                        # Job ID in PreliminaryBlocks and RawImageInput from PDFAcquisitionService should already be set
                        # based on the job_id passed to it.

                    else: # PDF service failed
                        error_msg = f"PDFAcquisitionService failed for PDF from URL {final_url_val}: {pdf_service_result.error_message if pdf_service_result else 'Unknown error'}"
                        if document_metadata_obj:
                            document_metadata_obj.custom_fields = document_metadata_obj.custom_fields or {}
                            document_metadata_obj.custom_fields["pdf_processing_error"] = error_msg
                        return ServiceResult.failure(error_message=error_msg, error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})

                except Exception as e_pdf_route:
                    # self.logger.error(f"Error routing PDF from {final_url_val} to PDFAcquisitionService: {e_pdf_route}", exc_info=True) # Optional logging
                    if document_metadata_obj:
                        document_metadata_obj.custom_fields = document_metadata_obj.custom_fields or {}
                        document_metadata_obj.custom_fields["pdf_processing_error"] = f"Routing/Tempfile error: {str(e_pdf_route)}"
                    return ServiceResult.failure(error_message=f"Error processing PDF from URL {final_url_val} via PDFAcquisitionService: {str(e_pdf_route)}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})
                finally:
                    if temp_pdf_file_path and os.path.exists(temp_pdf_file_path):
                        try:
                            os.remove(temp_pdf_file_path)
                        except Exception as e_remove:
                            # self.logger.warning(f"Could not remove temporary PDF file {temp_pdf_file_path}: {e_remove}") # Optional logging
                            pass
                # --- End Routing to PDFAcquisitionService ---

            elif html_content_str and final_url_val:
                # --- Start Trafilatura Integration ---
                main_content_html_snippet_by_trafilatura: Optional[str] = None
                is_trafilatura_content_available = False
                loop = asyncio.get_event_loop()
                try:
                    self.logger.info(f"Attempting main content HTML extraction with Trafilatura for {final_url_val}")
                    # Use run_in_executor for the synchronous trafilatura call
                    main_content_html_snippet_by_trafilatura = await loop.run_in_executor(
                        None, # Default thread pool executor
                        functools.partial(
                            trafilatura.extract,
                            html_content_str,
                            url=final_url_val,
                            output_format='xml', # Get structured HTML/XML
                            include_tables=True,
                            include_comments=False,
                            deduplicate=False # Adjust as needed
                        )
                    )
                    if main_content_html_snippet_by_trafilatura and len(main_content_html_snippet_by_trafilatura.strip()) >= 100: # Check if snippet is substantial
                        self.logger.info(f"Trafilatura successfully extracted HTML snippet (length: {len(main_content_html_snippet_by_trafilatura)}). Preview: {main_content_html_snippet_by_trafilatura[:200]}...")
                        is_trafilatura_content_available = True
                    else:
                        self.logger.info(f"Trafilatura returned very small or empty snippet (length: {len(main_content_html_snippet_by_trafilatura or '')}). Will use BS4 fallback.")
                        main_content_html_snippet_by_trafilatura = None # Ensure it's None if not substantial
                except Exception as e_traf:
                    self.logger.error(f"Trafilatura extraction failed for {final_url_val}: {e_traf}", exc_info=True)
                    main_content_html_snippet_by_trafilatura = None # Ensure it's None on error
                # --- End Trafilatura Integration ---

                # Paywall check should still happen on original full HTML
                soup_for_paywall_check = BeautifulSoup(html_content_str, 'lxml')
                is_paywalled = False
                if self._check_domain_in_set(self._get_domain(final_url_val), VERY_STRICT_PAYWALL_DOMAINS): # Use final_url_val
                    is_paywalled = True 
                else:
                    for selector in PAYWALL_HTML_SELECTORS:
                        if soup_for_paywall_check.select_one(selector): # Use soup_for_paywall_check
                            is_paywalled = True; break
                    if not is_paywalled:
                        text_lower_for_paywall = html_content_str.lower() # Use html_content_str
                        if any(keyword in text_lower_for_paywall for keyword in PAYWALL_KEYWORDS): # Use text_lower_for_paywall
                            is_paywalled = True
                
                if is_paywalled and document_metadata_obj:
                    document_metadata_obj.custom_fields = document_metadata_obj.custom_fields or {}
                    document_metadata_obj.custom_fields["paywall_detected"] = True
                
                # Determine what HTML to pass for parsing
                html_for_parsing: str
                if is_trafilatura_content_available and main_content_html_snippet_by_trafilatura:
                    html_for_parsing = main_content_html_snippet_by_trafilatura
                else:
                    html_for_parsing = html_content_str # Fallback to full original HTML

                preliminary_blocks_list, document_metadata_obj, raw_images_list = await self._parse_and_structure_html(
                    html_to_parse=html_for_parsing,
                    is_trafilatura_content=is_trafilatura_content_available, # Pass the flag
                    full_html_content_for_metadata_and_images=html_content_str, # Always pass original full HTML for metadata/images
                    final_url=final_url_val,
                    job_id=job_id,
                    processing_level=processing_level
                )
            else:
                # Should not happen if fetching was successful and content type was one of the above
                return ServiceResult.failure(error_message="No content (HTML or PDF) to process after fetching.", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})

            processing_duration = time.time() - request_start_time
            if document_metadata_obj: # Ensure metadata is not None
                document_metadata_obj.custom_fields = document_metadata_obj.custom_fields or {}
                document_metadata_obj.custom_fields["web_processing_duration_seconds"] = round(processing_duration, 3)
            
            # Ensure preliminary_blocks are sorted by order before returning
            preliminary_blocks_list.sort(key=lambda b: b.order)
            
            # Filter boilerplate text blocks AFTER all blocks (including images) have been ordered
            if preliminary_blocks_list: # Only filter if there are any blocks
                self.logger.debug(f"Calling _filter_boilerplate_preliminary_blocks with {len(preliminary_blocks_list)} blocks.")
                preliminary_blocks_list = self._filter_boilerplate_preliminary_blocks(preliminary_blocks_list, final_url_val)
                self.logger.debug(f"After _filter_boilerplate_preliminary_blocks, {len(preliminary_blocks_list)} blocks remaining.")

            return ServiceResult.success(data=(preliminary_blocks_list, document_metadata_obj, raw_images_list))

        except Exception as e_process: # Catch errors from PDF routing or HTML parsing/structuring
            processing_duration = time.time() - request_start_time
            if document_metadata_obj: 
                 document_metadata_obj.custom_fields = document_metadata_obj.custom_fields or {}
                 document_metadata_obj.custom_fields["web_processing_duration_seconds"] = round(processing_duration, 3)
                 document_metadata_obj.custom_fields["error"] = f"ContentProcessingError: {str(e_process)}"
            self.logger.exception(f"WEB_SERVICE_CONTENT_PROCESSING_ERROR for {final_url_val}", exc_info=True) # Use logger.exception for traceback
            return ServiceResult.failure(
                error_message=f"WEB_SERVICE_CONTENT_PROCESSING_ERROR: {type(e_process).__name__} for {final_url_val}. Details: {str(e_process)}",
                error_details={
                    "original_url": url,
                    "final_url_at_failure": final_url_val,
                    "exception_type": type(e_process).__name__,
                    "original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)
                }
            )