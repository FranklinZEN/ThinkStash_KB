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

# PDF processing library (PyMuPDF) - fitz import is no longer needed here if _parse_pdf_content_to_preliminary_blocks is removed
# import fitz # PyMuPDF # This can be removed if not used elsewhere in this file.

class WebAcquisitionService(BaseService):
    """
    Asynchronous service to fetch, parse, and extract content from web URLs.
    Outputs PreliminaryBlock, DocumentMetadata, and RawImageInput.
    """

    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        # Consider initializing an aiohttp.ClientSession here if it's to be reused across calls
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
        html_content: str, 
        final_url: str, 
        job_id: Optional[str], 
        processing_level: str
    ) -> Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]:
        
        preliminary_blocks: List[PreliminaryBlock] = []
        raw_images_list: List[RawImageInput] = []
        
        soup = BeautifulSoup(html_content, 'lxml')
        
        # --- 1. Populate DocumentMetadata ---
        doc_title: Optional[str] = None
        if soup.title and soup.title.string:
            doc_title = soup.title.string.strip()
        
        og_title_tag = soup.find('meta', property='og:title')
        if og_title_tag and isinstance(og_title_tag, Tag) and og_title_tag.get('content'):
            og_title = str(og_title_tag['content']).strip()
            if og_title: doc_title = og_title

        og_description_tag = soup.find('meta', property='og:description')
        og_description = str(og_description_tag['content']).strip() if og_description_tag and isinstance(og_description_tag, Tag) and og_description_tag.get('content') else None
        
        meta_description_tag = soup.find('meta', attrs={'name': 'description'})
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
        if processing_level == "full_content":
            raw_images_list = await self._extract_images_from_html(
                html_content_str=html_content, 
                base_url=final_url, 
                job_id=doc_job_id,
                original_source_identifier_for_gcs_path=source_identifier_for_gcs,
                source_type_for_gcs_path=source_type_for_gcs
            )

        # --- 3. Extract PreliminaryBlocks ---
        block_order_counter = 0 # Use a single counter for global order
        
        # Map image URLs from RawImageInput to their IDs for quick lookup
        # This is useful if we encounter images during main content parsing (e.g. within <figure>)
        # and want to link them to an already created RawImageInput.
        # However, _extract_images_from_html should already find most renderable images.
        # Image placeholders will be created based on raw_images_list *after* main content parsing
        # to try and interleave them correctly based on their DOM position relative to text.

        # For now, we'll first parse text/structure, then insert image placeholders.
        # A more advanced approach might involve a single pass through the DOM.

        body = soup.body
        if not body: # Fallback if no body tag
            body = soup 

        # Define tags to process and their handlers
        # This is a simplified approach. Real-world HTML can be much more complex.
        # We are looking for common block-level semantic tags.

        processed_elements = set() # To avoid processing the same element multiple times if nested

        for element in body.find_all(True, recursive=True): # Find all tags
            if element in processed_elements or not element.name:
                continue

            # Skip script, style, meta, link, noscript, and other non-content tags early
            if element.name in ['script', 'style', 'meta', 'link', 'noscript', 'header', 'footer', 'nav', 'aside', 'form', 'button', 'input', 'select', 'textarea', 'label', 'option']:
                # Mark element and its children as processed to avoid redundant checks
                for child in element.find_all(True, recursive=True):
                    processed_elements.add(child)
                processed_elements.add(element)
                continue
            
            # Check if parent is already processed to handle elements that generate multiple blocks (like lists)
            # or to ensure we're not double-counting text.
            # If a parent generated a block (e.g., <ul> created a series of list_item blocks),
            # we don't want its children (e.g. text nodes directly under <ul>) to create separate text blocks.
            # If a parent generated a block (e.g., <ul> created a series of list_item blocks),
            # we don't want its children (e.g. text nodes directly under <ul>) to create separate text blocks.
            parent_processed = False
            current_parent = element.parent
            while current_parent:
                if current_parent in processed_elements:
                    parent_processed = True
                    break
                current_parent = current_parent.parent
            if parent_processed and element.name not in ['li']: # Allow li to be processed even if ul/ol parent was
                 processed_elements.add(element)
                 continue


            block_id_base = f"{doc_job_id}_elem_{block_order_counter}"
            text_content = None
            block_type = None
            heading_level = None
            code_language = None
            list_item_data = None
            list_level = 0
            list_ordered = None
            custom_attrs = {}

            # Headings
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                block_type = "heading"
                text_content = element.get_text(separator=' ', strip=True)
                heading_level = int(element.name[1:])
            
            # Paragraphs
            elif element.name == 'p':
                block_type = "text"
                text_content = element.get_text(separator=' ', strip=True)

            # Lists (ul, ol) and List Items (li)
            elif element.name in ['ul', 'ol']:
                list_ordered = (element.name == 'ol')
                # Determine list level by counting ancestor ul/ol tags
                current_level = 0
                parent = element.parent
                while parent:
                    if parent.name in ['ul', 'ol']:
                        current_level += 1
                    parent = parent.parent
                
                for li_idx, li_element in enumerate(element.find_all('li', recursive=False)): # Only direct children li
                    if li_element in processed_elements: continue
                    
                    li_text = li_element.get_text(separator=' ', strip=True)
                    if li_text:
                        preliminary_blocks.append(PreliminaryBlock(
                            block_id=f"{block_id_base}_li_{li_idx}",
                            type="list_item",
                            text_content=li_text, # Storing text content directly
                            order=block_order_counter,
                            list_level=current_level,
                            list_ordered=list_ordered
                        ))
                        block_order_counter += 1
                    processed_elements.add(li_element) # Mark li as processed
                block_type = None # Handled by li items
                processed_elements.add(element) # Mark ul/ol as processed

            # Code Blocks (pre > code)
            elif element.name == 'pre':
                code_tag = element.find('code')
                target_code_element = code_tag if code_tag else element
                
                # Try to get language from class (e.g., class="language-python")
                lang_class = target_code_element.get('class', [])
                for cls in lang_class:
                    if cls.startswith('language-'):
                        code_language = cls.replace('language-', '')
                        break
                    elif cls.startswith('lang-'):
                        code_language = cls.replace('lang-', '')
                        break
                
                block_type = "code_snippet"
                code_content = target_code_element.get_text() # Keep original formatting as much as possible
                custom_attrs["raw_code_element_html"] = str(target_code_element) # Store raw html of code element

                # Add the preliminary block for code
                preliminary_blocks.append(PreliminaryBlock(
                    block_id=f"{block_id_base}_code",
                    type=block_type,
                    code_content=code_content,
                    code_language=code_language,
                    order=block_order_counter,
                    custom_attributes=custom_attrs
                ))
                block_order_counter += 1
                processed_elements.add(element) # Mark pre as processed
                if code_tag: processed_elements.add(code_tag)
                block_type = None # Reset block_type as it's handled


            # Tables
            elif element.name == 'table':
                block_type = "table_placeholder"
                # Store the outer HTML of the table
                custom_attrs["html_content"] = str(element)
                # Could add more sophisticated table parsing here if needed in future
                # For now, just placeholder and raw HTML

            # Image handling (<img> within the flow, primarily for ordering)
            # This is tricky because _extract_images_from_html already found images.
            # We need to place placeholders for them in the correct order.
            # This simplified loop processes elements sequentially.
            # We will insert all image placeholders collected earlier, sorted by their original DOM position if possible,
            # or simply append them if DOM position is hard to get reliably for all cases.
            # For now, let's add image placeholders derived from raw_images_list *after* this loop.
            # This element-by-element loop focuses on text and structure.

            # Default text extraction for other block-ish tags if not handled above
            # (e.g., div, article, section if they contain direct text not in p, h, etc.)
            # This needs to be careful not to extract text from already processed containers (like lists)
            # Only extract if the element itself has meaningful direct text content.
            elif element.name in ['div', 'span', 'article', 'section', 'main', 'blockquote', 'details', 'summary'] and not block_type:
                # Heuristic: only create a text block if it has direct text children
                # and is not just a container for other block elements we've already processed.
                # Also, check if the text is substantial.
                element_text_content = element.get_text(separator=' ', strip=True)
                is_container_only = any(child.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'pre', 'table', 'img', 'figure'] for child in element.find_all(recursive=False))
                
                if element_text_content and not is_container_only and len(element_text_content) > 20: # Arbitrary length check
                    block_type = "text"
                    text_content = element_text_content
            
            if block_type and text_content: # For text-based blocks (text, heading)
                preliminary_blocks.append(PreliminaryBlock(
                    block_id=block_id_base,
                    type=block_type,
                    text_content=text_content,
                    heading_level=heading_level,
                    order=block_order_counter
                ))
                block_order_counter += 1
                processed_elements.add(element)
            elif block_type == "table_placeholder": # For table
                preliminary_blocks.append(PreliminaryBlock(
                    block_id=block_id_base,
                    type=block_type,
                    order=block_order_counter,
                    custom_attributes=custom_attrs
                ))
                block_order_counter += 1
                processed_elements.add(element)

        # Now, add image placeholders from the raw_images_list.
        # This is a simplification; ideally, these would be interleaved correctly based on DOM position.
        # For now, we append them. A more robust solution would involve a single-pass DOM traversal
        # that identifies text, structure, AND images in order.
        for img_input in raw_images_list:
            placeholder_block_id = f"{doc_job_id}_img_placeholder_{block_order_counter}"
            preliminary_blocks.append(PreliminaryBlock(
                block_id=placeholder_block_id,
                type="image_placeholder",
                image_id_ref=img_input.image_id,
                order=block_order_counter,
                # page_number and bbox are None for web typically
            ))
            # image_id_to_block_map[img_input.image_id] = placeholder_block_id # Not currently used but good for future linking
            block_order_counter += 1
        
        # Remove the old trafilatura fallback if we have blocks from BeautifulSoup
        # If BeautifulSoup parsing yields no blocks, trafilatura could be a fallback.
        # For now, if preliminary_blocks is empty and trafilatura was enabled:
        if not preliminary_blocks: # If BS4 parsing yielded nothing substantial
            loop = asyncio.get_event_loop()
            try:
                main_content_text = await loop.run_in_executor(
                    None, 
                    functools.partial(trafilatura.extract, html_content, url=final_url, output_format='txt', include_comments=False, include_tables=True) # include_tables might give some table text
                )
                if main_content_text:
                    preliminary_blocks.append(PreliminaryBlock(
                        block_id=f"{doc_job_id}_txt_main_trafilatura_{block_order_counter}",
                        type="text",
                        text_content=main_content_text.strip(),
                        order=block_order_counter
                    ))
                    block_order_counter += 1
            except Exception as e:
                # self.logger.warning(f\"Trafilatura extraction failed for {final_url}: {e}\") # Optional logging
                pass 

        preliminary_blocks.sort(key=lambda b: b.order) # Ensure final sort by order
        
        return preliminary_blocks, document_metadata_obj, raw_images_list

    async def execute(self, web_input: WebAcquisitionServiceInput) -> ServiceResult[Tuple[List[PreliminaryBlock], DocumentMetadata, List[RawImageInput]]]:
        start_time = time.time()
        job_id = web_input.job_id or f"web_{uuid.uuid4().hex[:12]}"

        preliminary_blocks_list: List[PreliminaryBlock] = []
        document_metadata_obj: Optional[DocumentMetadata] = None
        raw_images_list: List[RawImageInput] = []
        temp_pdf_file_path: Optional[str] = None # Initialize here

        original_url = web_input.url.strip() # Ensure no leading/trailing whitespace

        # --- URL Normalization ---
        normalized_url = original_url
        if normalized_url.startswith("chrome-extension://"):
            # Try to find an embedded http/https URL
            match = re.search(r"(https?://[^\s]+)", normalized_url)
            if match:
                normalized_url = match.group(1)
            else:
                # If no http/https URL is found, it's likely a local file, which we can't fetch
                return ServiceResult.failure(
                    error_message=f"Cannot fetch local file from chrome-extension URL: {original_url}",
                    error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)}
                )
        
        parsed_normalized_url = urlparse(normalized_url)
        if not parsed_normalized_url.scheme:
            if parsed_normalized_url.netloc or (parsed_normalized_url.path and '.' in parsed_normalized_url.path.split('/')[0]): # Heuristic for domain-like path
                normalized_url = f"https://{normalized_url}" # Default to HTTPS
            else:
                # If it doesn't look like a domain/path that can be made a URL, fail early
                 return ServiceResult.failure(
                    error_message=f"Invalid URL format (cannot determine scheme): {original_url}",
                    error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)}
                )
        elif parsed_normalized_url.scheme not in ["http", "https"]:
            # If it has a scheme but it's not http/https (e.g. file://, ftp:// after initial chrome-ext stripping)
            return ServiceResult.failure(
                error_message=f"Unsupported URL scheme '{parsed_normalized_url.scheme}' in URL: {normalized_url}",
                error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)}
            )
        # --- End URL Normalization ---
        
        final_url_val: Optional[str] = None
        
        document_metadata_obj = DocumentMetadata(
            document_id=job_id,
            source_identifier=original_url, # Keep original URL as source_identifier
            source_type="url",
            extracted_at=datetime.utcnow()
        )

        try:
            # --- URL Validation and Filtering (uses normalized_url) ---
            parsed_url = urlparse(normalized_url) # Use the cleaned and potentially schemed URL
            if not all([parsed_url.scheme, parsed_url.netloc]):
                # This check might be redundant if normalization ensures scheme and netloc for http/https URLs
                return ServiceResult.failure(error_message=f"Invalid URL format after normalization: {normalized_url}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})
            
            domain = self._get_domain(normalized_url)
            if self._check_domain_in_set(domain, UNSUPPORTED_URL_TYPE_DOMAINS):
                is_allowed_social = any(re.search(pattern, normalized_url, re.IGNORECASE) for pattern in ALLOWED_SOCIAL_MEDIA_POST_PATTERNS)
                if not is_allowed_social:
                    return ServiceResult.failure(error_message=f"Unsupported domain: {domain} in URL: {normalized_url}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})

            # --- Fetching Content (uses normalized_url) ---
            async with aiohttp.ClientSession() as session:
                try:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    }
                    async with session.get(normalized_url, timeout=30, allow_redirects=True, headers=headers) as response: # Use normalized_url
                        final_url_val = str(response.url)
                        if document_metadata_obj: document_metadata_obj.final_url = final_url_val

                        if response.status != 200:
                            return ServiceResult.failure(error_message=f"HTTP error {response.status} for URL: {final_url_val}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})

                        content_type = response.headers.get('Content-Type', '').lower()
                        html_content_str: Optional[str] = None 
                        pdf_bytes_val: Optional[bytes] = None 

                        if 'application/pdf' in content_type:
                            pdf_bytes_val = await response.read()
                        elif 'text/html' in content_type or 'application/xhtml+xml' in content_type or not content_type:
                            html_content_str = await response.text()
                        else:
                            return ServiceResult.failure(error_message=f"Unsupported content type: {content_type} for URL: {final_url_val}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})

                except aiohttp.ClientError as e:
                    return ServiceResult.failure(error_message=f"Network/HTTP error fetching URL {normalized_url}: {str(e)}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)}) # Use normalized_url
                except asyncio.TimeoutError:
                     return ServiceResult.failure(error_message=f"Timeout fetching URL {normalized_url}", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)}) # Use normalized_url
            
            if pdf_bytes_val and final_url_val:
                # --- Route to PDFAcquisitionService ---
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
                        tmpfile.write(pdf_bytes_val)
                        temp_pdf_file_path = tmpfile.name
                    
                    pdf_acq_service = PDFAcquisitionService(settings=self.settings) # Assuming settings can be passed
                    pdf_input_obj = PDFAcquisitionServiceInput(
                        file_path=temp_pdf_file_path,
                        job_id=job_id, # Pass along the job_id
                        processing_level=web_input.processing_level # Pass along processing_level
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
                soup_for_paywall_check = BeautifulSoup(html_content_str, 'lxml')
                is_paywalled = False
                if self._check_domain_in_set(self._get_domain(final_url_val), VERY_STRICT_PAYWALL_DOMAINS):
                    is_paywalled = True 
                else:
                    for selector in PAYWALL_HTML_SELECTORS:
                        if soup_for_paywall_check.select_one(selector):
                            is_paywalled = True; break
                    if not is_paywalled:
                        text_lower = html_content_str.lower()
                        if any(keyword in text_lower for keyword in PAYWALL_KEYWORDS):
                            is_paywalled = True
                
                if is_paywalled and document_metadata_obj:
                    document_metadata_obj.custom_fields = document_metadata_obj.custom_fields or {}
                    document_metadata_obj.custom_fields["paywall_detected"] = True

                preliminary_blocks_list, document_metadata_obj, raw_images_list = await self._parse_and_structure_html(
                    html_content=html_content_str,
                    final_url=final_url_val,
                    job_id=job_id,
                    processing_level=web_input.processing_level
                )
            else:
                # Should not happen if fetching was successful and content type was one of the above
                return ServiceResult.failure(error_message="No content (HTML or PDF) to process after fetching.", error_details={"original_data": (preliminary_blocks_list, document_metadata_obj, raw_images_list)})

            processing_duration = time.time() - start_time
            if document_metadata_obj: # Ensure metadata is not None
                document_metadata_obj.custom_fields = document_metadata_obj.custom_fields or {}
                document_metadata_obj.custom_fields["web_processing_duration_seconds"] = round(processing_duration, 3)
            
            return ServiceResult.success(data=(preliminary_blocks_list, document_metadata_obj, raw_images_list))

        except Exception as e:
            # self.logger.error(f"WebAcquisitionService error for URL {original_url}: {e}", exc_info=True) # Optional logging
            processing_duration = time.time() - start_time
            if document_metadata_obj: 
                 document_metadata_obj.custom_fields = document_metadata_obj.custom_fields or {}
                 document_metadata_obj.custom_fields["web_processing_duration_seconds"] = round(processing_duration, 3)
                 document_metadata_obj.custom_fields["error"] = str(e)

            return ServiceResult.failure(
                error_message=f"WEB_SERVICE_FATAL_ERROR: {type(e).__name__} for {normalized_url}. Check logs.",
                error_details={
                    "original_url": original_url,
                    "normalized_url_at_failure": normalized_url,
                    "exception_type": type(e).__name__,
                    "original_data": (
                        preliminary_blocks_list if preliminary_blocks_list is not None else [], 
                        document_metadata_obj, 
                        raw_images_list if raw_images_list is not None else []
                    )
                }
            )
        finally:
            if temp_pdf_file_path and os.path.exists(temp_pdf_file_path):
                try:
                    os.remove(temp_pdf_file_path)
                except Exception as e_remove:
                    # self.logger.warning(f"Could not remove temporary PDF file {temp_pdf_file_path}: {e_remove}") # Optional logging
                    pass 