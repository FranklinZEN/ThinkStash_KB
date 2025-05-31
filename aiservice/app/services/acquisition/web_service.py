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
    user_id: Optional[str] = Field(None, description="Optional user ID for tracking and associating with metadata.")

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
        html_to_parse: str,
        is_trafilatura_content: bool,
        full_html_content_for_metadata_and_images: str,
        final_url: str, 
        job_id: Optional[str], 
        user_id: Optional[str],
        processing_level: str
    ) -> Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]:
        preliminary_blocks: List[PreliminaryBlock] = []
        raw_images_list: List[RawImageInput] = []
        
        self.logger.debug(f"_parse_and_structure_html called for URL: {final_url}, job_id: {job_id}, user_id: {user_id}")

        doc_id_prefix_for_blocks = job_id or hashlib.md5(final_url.encode()).hexdigest()[:16]

        # --- Document Metadata Creation ---
        doc_meta_obj = DocumentMetadata(
            document_id=job_id,
            user_id=user_id,
            source_identifier=final_url,
            source_type="url",
            final_url=final_url,
            extracted_at=datetime.utcnow(),
            title=None,
            author=None,
            subject=None,
            keywords=[],
            creation_date=None,
            modification_date=None,
            total_pages=None,
            language_detected=None,
            custom_fields={}
        )

        soup_for_metadata = BeautifulSoup(full_html_content_for_metadata_and_images, 'lxml')
        if soup_for_metadata.title and soup_for_metadata.title.string:
            doc_meta_obj.title = soup_for_metadata.title.string.strip()
        else:
            doc_meta_obj.title = urlparse(final_url).path.split('/')[-1] or urlparse(final_url).hostname
        
        meta_author = soup_for_metadata.find("meta", attrs={"name": re.compile(r"author", re.I)})
        if meta_author and meta_author.get("content"):
            doc_meta_obj.author = meta_author.get("content").strip()
        
        # --- Comprehensive Image Extraction ---
        if processing_level == "full_content":
            raw_images_list = await self._extract_images_from_html(
                html_content_str=full_html_content_for_metadata_and_images, 
                base_url=final_url, 
                job_id=job_id,
                original_source_identifier_for_gcs_path=final_url,
                source_type_for_gcs_path="url"
            )

        # --- Main Content Parsing into PreliminaryBlocks (NEW LOGIC) ---
        current_block_order = 0 # This variable is not strictly needed if order is len(blocks) at append
        main_content_soup = BeautifulSoup(html_to_parse, 'lxml') # Parse the (potentially Trafilatura-cleaned) main HTML

        # Create a lookup map for image_id_ref from the comprehensive raw_images_list
        # Key: absolute image URL, Value: image_id from RawImageInput
        raw_image_id_map_by_url: Dict[str, str] = {}
        raw_image_alt_map_by_url: Dict[str, Optional[str]] = {}
        if processing_level == "full_content":
            for raw_img in raw_images_list:
                if raw_img.source_url: # source_url should be the absolute URL of the image
                     raw_image_id_map_by_url[raw_img.source_url] = raw_img.image_id
                     raw_image_alt_map_by_url[raw_img.source_url] = raw_img.alt_text

        # Determine the starting point for iteration
        elements_to_iterate: List[Tag] = []
        if main_content_soup.body:
            elements_to_iterate = [child for child in main_content_soup.body.children if isinstance(child, Tag)]
            self.logger.debug(f"Parsing main content from body. Found {len(elements_to_iterate)} direct child Tags.")
        else: 
            elements_to_iterate = [child for child in main_content_soup.children if isinstance(child, Tag)]
            self.logger.debug(f"Parsing main content from fragment root. Found {len(elements_to_iterate)} direct child Tags.")
        
        # If no direct children tags were found, but the soup is not empty, 
        # it might be a case where trafilatura returns a list of tags not under a single root,
        # or a single root tag whose children we want (like <doc> -> <p>, <h1>)
        # So, if elements_to_iterate is empty but main_content_soup has *some* tags, let's try to get them all.
        if not elements_to_iterate and main_content_soup.find(True): # find(True) checks if any tag exists
            self.logger.debug("No direct children Tags found for iteration, attempting to find all relevant block-level tags recursively from main_content_soup root.")
            # This will get all specified tags, regardless of depth from main_content_soup root
            elements_to_iterate = main_content_soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'img', 'figure', 'pre', 'ul', 'ol', 'table', 'div'], recursive=True)
            self.logger.debug(f"Found {len(elements_to_iterate)} tags via recursive find_all as a fallback.")

        for element in elements_to_iterate:
            # Call the recursive processor for each top-level element found or all relevant tags if using fallback
            # The _process_html_element function will append to preliminary_blocks and handle order internally.
            await self._process_html_element(element, final_url, doc_id_prefix_for_blocks, preliminary_blocks, raw_image_id_map_by_url, raw_image_alt_map_by_url)

        # Fallback if no blocks were created (e.g., very unusual HTML structure or empty trafilatura output)
        if not preliminary_blocks and html_to_parse.strip():
            self.logger.warning(f"_parse_and_structure_html for {final_url}: No blocks created from main content parsing. Creating a single text block as fallback.")
            fallback_text = BeautifulSoup(html_to_parse, 'lxml').get_text(separator='\\n', strip=True)
            if fallback_text:
                preliminary_blocks.append(PreliminaryBlock(
                    block_id=f"{doc_id_prefix_for_blocks}_b0",
                    type="text",
                    text_content=fallback_text,
                    order=0
                ))
        
        self.logger.debug(f"_parse_and_structure_html returning {len(preliminary_blocks)} preliminary_blocks for job_id {job_id}. Title: {doc_meta_obj.title}")

        # Log the HTML structure being parsed
        self.logger.debug(f"_parse_and_structure_html: About to process the following HTML structure from Trafilatura:\\n{main_content_soup.prettify()}") # ADDED LOG

        # --- Add any remaining images from raw_images_list that weren't turned into placeholders ---
        # This handles cases where Trafilatura might have stripped image tags processed by _extract_images_from_html
        if processing_level == "full_content":
            processed_image_ids_in_blocks = set()
            for pb in preliminary_blocks:
                if pb.type == 'image_placeholder' and pb.image_id_ref:
                    processed_image_ids_in_blocks.add(pb.image_id_ref)
            
            self.logger.debug(f"Image IDs already processed into blocks by _process_html_element: {processed_image_ids_in_blocks}")

            for raw_img in raw_images_list:
                if raw_img.image_id not in processed_image_ids_in_blocks:
                    self.logger.debug(f"Adding image {raw_img.image_id} ({raw_img.source_url}) from raw_images_list as it was not found in Trafilatura-processed blocks.")
                    new_block_order = len(preliminary_blocks)
                    block_id_str = f"{doc_id_prefix_for_blocks}_b{new_block_order}"
                    
                    custom_attrs_for_raw_img = {}
                    if raw_img.alt_text:
                        custom_attrs_for_raw_img['alt_text'] = raw_img.alt_text
                    if raw_img.caption: # Assuming RawImageInput might have a caption
                        custom_attrs_for_raw_img['caption'] = raw_img.caption
                    
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=block_id_str,
                        type='image_placeholder',
                        image_id_ref=raw_img.image_id,
                        order=new_block_order,
                        custom_attributes=custom_attrs_for_raw_img if custom_attrs_for_raw_img else None
                    ))
            self.logger.debug(f"Total preliminary_blocks after adding remaining raw images: {len(preliminary_blocks)}")
        # --- End of adding remaining images ---
        
        return preliminary_blocks, doc_meta_obj, raw_images_list

    async def _process_html_element(self, element: Tag, base_url: str, doc_id_prefix: str, 
                                    blocks: List[PreliminaryBlock], 
                                    image_id_map: Dict[str, str], 
                                    image_alt_map: Dict[str, Optional[str]]):
        """
        Recursively processes an HTML element to create PreliminaryBlock objects.
        Appends new blocks to the `blocks` list.
        Order is determined by the length of the blocks list at the time of append.
        """
        self.logger.debug(f"_process_html_element CALLED with tag: <{element.name}>") # ENTRY LOGGING
        # block_id_str will use the current length of blocks for its suffix.
        # Order for the new block will also be the current length of blocks.
        # This ensures sequential block_ids and order values.
        
        tag_name = element.name
        custom_attrs = {}

        # Check if this element (or its significant content) has already been processed 
        # by a parent that decided to consume it (e.g. a <p> that contains only an <img>)
        # This is a complex problem to solve perfectly. A simple check could be based on element attributes or source line.
        # For now, we rely on the parsing logic not to duplicate; e.g. if <p><img></p>, the 'p' handler might call for 'img'.

        if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            text_content = element.get_text(strip=True)
            if text_content:
                block_id_str = f"{doc_id_prefix}_b{len(blocks)}"
                blocks.append(PreliminaryBlock(
                    block_id=block_id_str,
                    type='heading',
                    text_content=text_content,
                    heading_level=int(tag_name[1]),
                    order=len(blocks) # Order is current size before append
                ))
        elif tag_name == 'p':
            # Handle <p> tags. If a <p> only contains an <img>, process <img> directly.
            # Otherwise, create a text block.
            children_tags = [child for child in element.children if isinstance(child, Tag)]
            text_content_direct = (''.join(c.string for c in element.children if isinstance(c, str) and c.string)).strip()
            
            if len(children_tags) == 1 and children_tags[0].name == 'img' and not text_content_direct:
                # Paragraph contains only an image and no other text content
                # self.logger.debug(f"Paragraph contains only an image. Processing image: {children_tags[0]}")
                await self._process_html_element(children_tags[0], base_url, doc_id_prefix, blocks, image_id_map, image_alt_map)
            else:
                full_text_content = element.get_text(strip=True)
                if full_text_content: # Only add if there's actual text
                    block_id_str = f"{doc_id_prefix}_b{len(blocks)}"
                    blocks.append(PreliminaryBlock(
                        block_id=block_id_str,
                        type='text',
                        text_content=full_text_content,
                        order=len(blocks)
                    ))
        elif tag_name == 'img':
            src = element.get('src') or element.get('data-src')
            if src:
                abs_img_url = urljoin(base_url, src.strip())
                self.logger.debug(f"IMG tag: Attempting to find image_id for abs_img_url: '{abs_img_url}'. Map keys: {list(image_id_map.keys())}") # DEBUG LOGGING
                image_id_ref = image_id_map.get(abs_img_url)
                alt_text = image_alt_map.get(abs_img_url, element.get('alt','').strip())

                if not image_id_ref: 
                    self.logger.warning(f"Image {abs_img_url} in main content but not in pre-scanned raw_images_list. Generating temp ID.")
                    image_id_ref = f"TEMP_IMG_{hashlib.md5(abs_img_url.encode()).hexdigest()[:10]}"
                
                current_custom_attrs = {'alt_text': alt_text} # Use a fresh dict for each block
                
                block_id_str = f"{doc_id_prefix}_b{len(blocks)}"
                blocks.append(PreliminaryBlock(
                    block_id=block_id_str,
                    type='image_placeholder',
                    image_id_ref=image_id_ref,
                    order=len(blocks),
                    custom_attributes=current_custom_attrs
                ))

        elif tag_name == 'figure':
            img_in_figure = element.find('img')
            figcaption_text: Optional[str] = None
            figcaption_tag = element.find('figcaption')
            if figcaption_tag:
                figcaption_text = figcaption_tag.get_text(strip=True)

            if img_in_figure:
                # If figure contains an image, prioritize the image block.
                # The caption will be part of the image block's custom_attributes.
                src = img_in_figure.get('src') or img_in_figure.get('data-src')
                if src:
                    abs_img_url = urljoin(base_url, src.strip())
                    self.logger.debug(f"FIGURE tag: Attempting to find image_id for abs_img_url: '{abs_img_url}'. Map keys: {list(image_id_map.keys())}") # DEBUG LOGGING
                    image_id_ref = image_id_map.get(abs_img_url)
                    alt_text = image_alt_map.get(abs_img_url, img_in_figure.get('alt','').strip())

                    if not image_id_ref:
                        self.logger.warning(f"Image {abs_img_url} in figure not in pre-scanned list. Generating temp ID.")
                        image_id_ref = f"TEMP_IMG_{hashlib.md5(abs_img_url.encode()).hexdigest()[:10]}"
                    
                    current_custom_attrs = {'alt_text': alt_text}
                    if figcaption_text:
                        current_custom_attrs['caption'] = figcaption_text

                    block_id_str = f"{doc_id_prefix}_b{len(blocks)}"
                    blocks.append(PreliminaryBlock(
                        block_id=block_id_str,
                        type='image_placeholder',
                        image_id_ref=image_id_ref,
                        order=len(blocks),
                        custom_attributes=current_custom_attrs
                    ))
            elif figcaption_text: # Figure with caption but no image? Treat as text.
                block_id_str = f"{doc_id_prefix}_b{len(blocks)}"
                blocks.append(PreliminaryBlock(
                    block_id=block_id_str,
                    type='text',
                    text_content=figcaption_text,
                    order=len(blocks)
                ))
            # else: Figure with neither, or complex content not handled by this simple parser.
            # Could add recursion here if figures can contain other block types: 
            # for child in element.children: if isinstance(child, Tag) and child not in [img_in_figure, figcaption_tag]: await self._process_html_element(...)
            
        elif tag_name == 'pre':
            code_content = element.get_text() 
            lang = None
            # Look for class="language-xxx" on <pre> or a child <code> tag
            lang_classes = element.get('class', [])
            if element.code and element.code.get('class'):
                lang_classes.extend(element.code.get('class'))
            
            for c in lang_classes:
                if c.startswith('language-'):
                    lang = c.replace('language-', '')
                    break
            block_id_str = f"{doc_id_prefix}_b{len(blocks)}"
            blocks.append(PreliminaryBlock(
                block_id=block_id_str,
                type='code_snippet',
                text_content=code_content, 
                code_language=lang, 
                order=len(blocks)
            ))

        elif tag_name in ['ul', 'ol']:
            # Each <li> will become a separate 'list_item' block.
            # The parent <ul>/<ol> itself does not become a block.
            for li in element.find_all('li', recursive=False):
                # Process children of li to handle nested structures or complex li content
                await self._process_html_element(li, base_url, doc_id_prefix, blocks, image_id_map, image_alt_map)
        
        elif tag_name == 'li': # Handle <li> elements when called directly (e.g. from ul/ol loop)
            # For <li>, we create a block for its content. 
            # If <li> contains further block elements (like a <p> or another <ul>), 
            # the recursive calls for its children will handle them.
            # What constitutes the "text" of the li? If it has a <p>, that p's text is usually primary.
            # This simplified version takes all text from the <li>.
            item_text = element.get_text(strip=True)
            if item_text:
                block_id_str = f"{doc_id_prefix}_b{len(blocks)}"
                blocks.append(PreliminaryBlock(
                    block_id=block_id_str,
                    type='list_item',
                    text_content=item_text,
                    list_ordered=(element.parent.name == 'ol' if element.parent else None),
                    order=len(blocks)
                ))
            # After creating the list_item block for the direct text, recurse for complex children if any
            for child in element.children:
                 if isinstance(child, Tag) and child.name not in ['ul','ol']: # Avoid double processing ul/ol within li if li itself makes a block
                    # This recursion part for <li> children needs care to avoid duplicating content
                    # If the get_text() above already captured children's text, this might be redundant
                    # This is where parsing gets very tricky. For now, let's assume get_text() is sufficient for simple list items.
                    # More complex <li> with <p> and <img> would need the child recursion.
                    pass # Simplified: rely on get_text for <li> content for now.

        elif tag_name == 'table':
            current_custom_attrs = {'html_table_content': str(element)}
            block_id_str = f"{doc_id_prefix}_b{len(blocks)}"
            blocks.append(PreliminaryBlock(
                block_id=block_id_str,
                type='table_placeholder', 
                text_content="[Table Content]", 
                order=len(blocks),
                custom_attributes=current_custom_attrs
            ))
        
        # Generic container processing: if a div/section etc. has direct text not part of a sub-block, make a text block.
        # Must be careful not to re-process elements that created their own blocks (p, h1, img etc.)
        # The primary loop in _parse_and_structure_html iterates, and this _process_html_element is called for each.
        # If `element` is one of p, h1, img etc., it's handled above. 
        # If `element` is div, section, etc., we then recurse for its children below.
        # This `elif` is for cases where a div might have text directly like <div>Text</div>, not <div><p>Text</p></div>
        elif tag_name in ['div', 'span', 'section', 'article', 'main', 'aside'] and not element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'img', 'figure', 'pre', 'ul', 'ol', 'table'], recursive=False):
            # Only consider if it has no known block-level children, but might have direct text.
            # This check is a heuristic.
            direct_text = (''.join(c.string for c in element.children if isinstance(c, str) and c.string)).strip()
            if direct_text:
                # Avoid creating blocks for divs that are just wrappers around elements we will process via recursion
                # This requires checking if any child tag would form a block itself.
                # This heuristic is tricky. For now, if direct_text exists, make a block.
                # It might lead to some duplication if children are also block-formers.
                block_id_str = f"{doc_id_prefix}_b{len(blocks)}"
                blocks.append(PreliminaryBlock(
                    block_id=block_id_str,
                    type='text',
                    text_content=direct_text, 
                    order=len(blocks)
                ))

        # Recursive call for children of the CURRENT element, 
        # IF the current element itself didn't form a block that consumed all its relevant content
        # OR if it's a known container type.
        # This is the most complex part to get right to avoid duplicates and missed content.
        if tag_name in ['div', 'section', 'article', 'main', 'aside', 'details', 'summary', 'blockquote', 'body', 'doc']:
            # For these container tags, always try to process their children.
            # (Removed 'li' from here as its direct content should form a block, and its children handling needs to be more specific)
            for child in element.children:
                if isinstance(child, Tag):
                    # Pass the same image_id_map and image_alt_map down
                    await self._process_html_element(child, base_url, doc_id_prefix, blocks, image_id_map, image_alt_map)

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
        start_time = time.time()
        current_job_id = web_input.job_id or f"web_job_{uuid.uuid4().hex[:8]}"
        current_user_id = web_input.user_id

        preliminary_blocks_default: List[PreliminaryBlock] = []
        document_metadata_default = DocumentMetadata(
            document_id=current_job_id,
            user_id=current_user_id,
            source_identifier=web_input.url,
            source_type="url",
            extracted_at=datetime.utcnow(),
            title=urlparse(web_input.url).path.split('/')[-1] or urlparse(web_input.url).hostname
        )
        raw_images_default: List[RawImageInput] = []
        
        html_content_str: Optional[str] = None
        final_url_val: str = web_input.url # Start with input URL, will be updated by redirects if fetch occurs
        pdf_bytes_val: Optional[bytes] = None
        temp_pdf_file_path: Optional[str] = None

        # --- Cache Check ---
        current_time = time.time()
        if web_input.url in self.html_cache:
            cached_html, fetch_time = self.html_cache[web_input.url]
            if (current_time - fetch_time) < self.cache_ttl_seconds:
                self.logger.info(f"HTML cache HIT for {web_input.url}")
                html_content_str = cached_html
                # final_url_val remains 'url' (original input) if from cache
            else:
                self.logger.info(f"HTML cache STALE for {web_input.url}")
                del self.html_cache[web_input.url]

        # --- If cache miss or stale, proceed to fetch and then process ---
        if html_content_str is None: 
            self.logger.info(f"HTML cache MISS for {web_input.url}. Fetching...")
            
            normalized_url = web_input.url 
            if normalized_url.startswith("chrome-extension://"):
                match = re.search(r"(https?:\\\\/\\\\/[^\\\\s]+)", normalized_url)
                if match:
                    normalized_url = match.group(1)
                else:
                    return ServiceResult.failure(
                        error_message=f"Cannot fetch local file from chrome-extension URL: {web_input.url}",
                        error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)}
                    )
            
            parsed_normalized_url = urlparse(normalized_url)
            if not parsed_normalized_url.scheme:
                if parsed_normalized_url.netloc or (parsed_normalized_url.path and '.' in parsed_normalized_url.path.split('/')[0]):
                    normalized_url = f"https://{normalized_url}"
                else:
                     return ServiceResult.failure(
                        error_message=f"Invalid URL format (cannot determine scheme): {web_input.url}",
                        error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)}
                    )
            elif parsed_normalized_url.scheme not in ["http", "https"]:
                return ServiceResult.failure(
                    error_message=f"Unsupported URL scheme '{parsed_normalized_url.scheme}' in URL: {normalized_url}",
                    error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)}
                )

            try: # This try is for the network fetching part
                parsed_url_for_domain_check = urlparse(normalized_url) # Use normalized for domain checks
                if not all([parsed_url_for_domain_check.scheme, parsed_url_for_domain_check.netloc]):
                     return ServiceResult.failure(error_message=f"Invalid URL format after normalization: {normalized_url}", error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})

                domain = self._get_domain(normalized_url)
                if self._check_domain_in_set(domain, UNSUPPORTED_URL_TYPE_DOMAINS):
                    is_allowed_social = any(re.search(pattern, normalized_url, re.IGNORECASE) for pattern in ALLOWED_SOCIAL_MEDIA_POST_PATTERNS)
                    if not is_allowed_social:
                        return ServiceResult.failure(error_message=f"Unsupported domain: {domain} in URL: {normalized_url}", error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})

                async with aiohttp.ClientSession() as session:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    }
                    async with session.get(normalized_url, timeout=30, allow_redirects=True, headers=headers) as response:
                        final_url_val = str(response.url) # Update final_url_val after actual fetch
                        document_metadata_default.final_url = final_url_val # Update metadata with the truly final URL

                        if response.status != 200:
                            return ServiceResult.failure(error_message=f"HTTP error {response.status} for URL: {final_url_val}", error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})

                        content_type = response.headers.get('Content-Type', '').lower()
                        if 'application/pdf' in content_type:
                            pdf_bytes_val = await response.read()
                        elif 'text/html' in content_type or 'application/xhtml+xml' in content_type or not content_type:
                            html_content_str = await response.text()
                            if html_content_str: # Store non-empty HTML in cache
                                self.html_cache[web_input.url] = (html_content_str, time.time()) # Use original 'url' as key
                                self.logger.info(f"Stored HTML in cache for {web_input.url}")
                        else:
                            return ServiceResult.failure(error_message=f"Unsupported content type: {content_type} for URL: {final_url_val}", error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})
            
            except aiohttp.ClientError as e_net:
                return ServiceResult.failure(error_message=f"Network/HTTP error fetching URL {normalized_url}: {str(e_net)}", error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})
            except asyncio.TimeoutError:
                return ServiceResult.failure(error_message=f"Timeout fetching URL {normalized_url}", error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})
            except Exception as e_fetch_prep: # Catch other errors during pre-fetch or fetch setup
                return ServiceResult.failure(error_message=f"Error during URL fetch preparation for {web_input.url}: {str(e_fetch_prep)}", error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})
        
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
                    pdf_acq_input = PDFAcquisitionServiceInput(
                        file_path=temp_pdf_file_path,
                        processing_level=web_input.processing_level,
                        job_id=current_job_id,
                        user_id=current_user_id
                    )
                    pdf_service_result = await pdf_acq_service.execute(pdf_acq_input)

                    if pdf_service_result.success and pdf_service_result.data:
                        preliminary_blocks_list, pdf_doc_metadata, raw_images_list = pdf_service_result.data
                        
                        # Merge DocumentMetadata: Keep original web URL, update with PDF specific info if valuable
                        # The document_metadata_obj is already initialized with web source info.
                        # We can enrich it with PDF-specific metadata if needed.
                        if document_metadata_default and pdf_doc_metadata:
                            document_metadata_default.title = pdf_doc_metadata.title or document_metadata_default.title
                            document_metadata_default.author = pdf_doc_metadata.author or document_metadata_default.author
                            document_metadata_default.subject = pdf_doc_metadata.subject or document_metadata_default.subject
                            document_metadata_default.keywords = pdf_doc_metadata.keywords or document_metadata_default.keywords
                            document_metadata_default.creation_date = pdf_doc_metadata.creation_date or document_metadata_default.creation_date
                            document_metadata_default.modification_date = pdf_doc_metadata.modification_date or document_metadata_default.modification_date
                            document_metadata_default.total_pages = pdf_doc_metadata.total_pages
                            # Ensure source_identifier remains the original URL, source_type 'url'
                            document_metadata_default.source_type = "pdf_from_url" # Or keep as 'url' and add custom field? Let's mark as pdf_from_url
                        
                        # Job ID in PreliminaryBlocks and RawImageInput from PDFAcquisitionService should already be set
                        # based on the job_id passed to it.

                    else: # PDF service failed
                        error_msg = f"PDFAcquisitionService failed for PDF from URL {final_url_val}: {pdf_service_result.error_message if pdf_service_result else 'Unknown error'}"
                        if document_metadata_default:
                            document_metadata_default.custom_fields = document_metadata_default.custom_fields or {}
                            document_metadata_default.custom_fields["pdf_processing_error"] = error_msg
                        return ServiceResult.failure(error_message=error_msg, error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})

                except Exception as e_pdf_route:
                    # self.logger.error(f"Error routing PDF from {final_url_val} to PDFAcquisitionService: {e_pdf_route}", exc_info=True) # Optional logging
                    if document_metadata_default:
                        document_metadata_default.custom_fields = document_metadata_default.custom_fields or {}
                        document_metadata_default.custom_fields["pdf_processing_error"] = f"Routing/Tempfile error: {str(e_pdf_route)}"
                    return ServiceResult.failure(error_message=f"Error processing PDF from URL {final_url_val} via PDFAcquisitionService: {str(e_pdf_route)}", error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})
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
                
                if is_paywalled and document_metadata_default:
                    document_metadata_default.custom_fields = document_metadata_default.custom_fields or {}
                    document_metadata_default.custom_fields["paywall_detected"] = True
                
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
                    job_id=current_job_id,
                    user_id=current_user_id,
                    processing_level=web_input.processing_level
                )
            else:
                # Should not happen if fetching was successful and content type was one of the above
                return ServiceResult.failure(error_message="No content (HTML or PDF) to process after fetching.", error_details={"original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)})

            processing_duration = time.time() - start_time
            if document_metadata_default: # Ensure metadata is not None
                document_metadata_default.custom_fields = document_metadata_default.custom_fields or {}
                document_metadata_default.custom_fields["web_processing_duration_seconds"] = round(processing_duration, 3)
            
            # Ensure preliminary_blocks are sorted by order before returning
            preliminary_blocks_list.sort(key=lambda b: b.order)
            
            # Filter boilerplate text blocks AFTER all blocks (including images) have been ordered
            if preliminary_blocks_list: # Only filter if there are any blocks
                self.logger.debug(f"Calling _filter_boilerplate_preliminary_blocks with {len(preliminary_blocks_list)} blocks.")
                preliminary_blocks_list = self._filter_boilerplate_preliminary_blocks(preliminary_blocks_list, final_url_val)
                self.logger.debug(f"After _filter_boilerplate_preliminary_blocks, {len(preliminary_blocks_list)} blocks remaining.")

            return ServiceResult.success(data=(preliminary_blocks_list, document_metadata_default, raw_images_list))

        except Exception as e_process: # Catch errors from PDF routing or HTML parsing/structuring
            processing_duration = time.time() - start_time
            if document_metadata_default: 
                 document_metadata_default.custom_fields = document_metadata_default.custom_fields or {}
                 document_metadata_default.custom_fields["web_processing_duration_seconds"] = round(processing_duration, 3)
                 document_metadata_default.custom_fields["error"] = f"ContentProcessingError: {str(e_process)}"
            self.logger.exception(f"WEB_SERVICE_CONTENT_PROCESSING_ERROR for {final_url_val}", exc_info=True) # Use logger.exception for traceback
            return ServiceResult.failure(
                error_message=f"WEB_SERVICE_CONTENT_PROCESSING_ERROR: {type(e_process).__name__} for {final_url_val}. Details: {str(e_process)}",
                error_details={
                    "original_url": web_input.url,
                    "final_url_at_failure": final_url_val,
                    "exception_type": type(e_process).__name__,
                    "original_data": (preliminary_blocks_default, document_metadata_default, raw_images_default)
                }
            )