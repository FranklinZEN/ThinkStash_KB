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
from typing import Type, Dict, Optional, Any, List, Union, Set
import functools
import json

from pydantic import BaseModel, Field, HttpUrl

from aiservice.app.services.base import BaseService, ServiceResult

# --- Pydantic Models for WebAcquisitionService ---

class WebAcquisitionServiceInput(BaseModel):
    url: str = Field(..., description="The URL to fetch and process.")
    processing_level: str = Field(default="full_content", examples=["full_content", "text_only"], description="Controls whether to extract images. 'full_content' enables image extraction.")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking or unique ID generation.")

class ProcessedWebImage(BaseModel):
    image_id: str  # e.g., "WEB_IMG_1"
    image_url: HttpUrl
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    source_scope: Optional[str] = None # "main_content" or "full_page_heuristic"
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    # Potential future fields: width, height, mime_type if easily available

class WebAcquisitionServiceOutput(BaseModel):
    status: str = Field(..., examples=["success", "pdf_content_detected", "error_fetch", "error_parsing", "error_paywall", "error_unsupported_content_type", "error_invalid_url"])
    original_url: str
    final_url: Optional[str] = None
    page_title: Optional[str] = None
    extracted_text: Optional[str] = None
    images: Optional[List[ProcessedWebImage]] = Field(default_factory=list)
    pdf_content_bytes: Optional[bytes] = None
    is_paywalled: Optional[bool] = False
    error_message: Optional[str] = None
    processing_duration_seconds: Optional[float] = None

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

class WebAcquisitionService(BaseService):
    """
    Asynchronous service to fetch, parse, and extract content from web URLs.
    Adapts logic from V2.4 WebContentFetcherTool and WebURLContentAcquisitionAgent.
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

    async def _extract_images_from_html(self, html_content_str: str, base_url: str, job_id: Optional[str]) -> List[ProcessedWebImage]:
        """
        Extracts image URLs from HTML content using various strategies.
        Enhanced with more robust filtering.
        """
        images: List[ProcessedWebImage] = []
        processed_urls: Set[str] = set()
        soup = BeautifulSoup(html_content_str, 'lxml')
        image_counter = 0

        MIN_DIMENSION = 50  # Minimum width/height for an image to be considered relevant
        MIN_AREA = 5000 # Increased min area slightly (e.g. > 70x70)
        MAX_ASPECT_RATIO_DEVIATION = 4.0 

        IRRELEVANT_ALT_STRINGS_EXACT = [
            "logo", "avatar", "icon", "profile", "banner", "ad", "advertisement", 
            "pinterest", "pinterest engineering", "pinterest engineering blog", "walmart global tech blog", # Added specific
            "user", "author", "default", "placeholder", "loading", "spinner", "spacer", "pixel",
            "figure", "image", "photo", "illustration", "diagram" # Generic terms if alone
        ]
        IRRELEVANT_SUBSTRINGS_IN_ALT = [
            "logo", "avatar", "icon", "profile", "banner", "advert", "promo", "social", "button", "rating", 
            "star", "user photo", "profile picture", "author bio", "site badge", "user badge", "blog logo" # Added more specific and common phrases
        ]
        IRRELEVANT_URL_SEGMENTS = [
            "/logo", "/avatar", "/icon", "/banner", "/profile", "/badge", "/sprite", 
            "/spinner", "/loader", "/ads/", "/ad/", "/advert/", "pixel.gif", "spacer.gif",
            "/track", "/beacon", "gravatar.com", "/share_", "_share.", "/social_", "_social.",
            "feedburner.com", "doubleclick.net", "googlesyndication.com", "adservice.google.com",
            "feeds.feedburner.com", "ad.doubleclick.net", "stats.wordpress.com", "blogger.googleusercontent.com/img/b" # Added more
        ]
        ALLOWED_CONTENT_PATH_INDICATORS = [ 
            "/content/", "/media/", "/wp-content/uploads/", "/uploads/", "/images/", "/image/",
            "/wp-content/uploads", "/files/", "/assets/", "/_posts/", "/posts/", "/articles/", "/article/" # Added more
        ]

        def _create_image_id(index: int) -> str:
            job_prefix = f"{job_id}_" if job_id else ""
            # Fallback to hashing part of URL if no job_id and index is not enough for global uniqueness
            # This part might need access to the image URL itself if we want more unique IDs without job_id
            # For now, using a simpler counter if no job_id
            unique_part = str(index + 1)
            return f"WEB_IMG_{job_prefix}{unique_part}"

        # 1. Standard <img> tags
        for idx, img_tag in enumerate(soup.find_all('img')):
            if not isinstance(img_tag, Tag): continue
            src = img_tag.get('src')
            if not src: src = img_tag.get('data-src')
            if not src: src = img_tag.get('data-original')
            if not src or str(src).startswith('data:image'):
                continue

            try:
                abs_img_url = urljoin(base_url, str(src).strip())
                if abs_img_url in processed_urls:
                    continue

                # --- Start Filtering Logic (Enhanced) ---
                abs_img_url_lower = abs_img_url.lower()

                # Filter by URL segments
                is_url_potentially_irrelevant = any(segment in abs_img_url_lower for segment in IRRELEVANT_URL_SEGMENTS)
                is_url_explicitly_content = any(indicator in abs_img_url_lower for indicator in ALLOWED_CONTENT_PATH_INDICATORS)
                
                if is_url_potentially_irrelevant and not is_url_explicitly_content:
                    continue

                alt_text_raw = img_tag.get('alt', '').strip()
                alt_text_lower = alt_text_raw.lower()

                if alt_text_lower in IRRELEVANT_ALT_STRINGS_EXACT:
                    continue
                
                is_irrelevant_substring = False
                for substring in IRRELEVANT_SUBSTRINGS_IN_ALT:
                    if substring in alt_text_lower:
                        is_irrelevant_substring = True
                        break
                if is_irrelevant_substring:
                    continue
                
                # Dimension and Aspect Ratio Filtering
                width_str = img_tag.get('width')
                height_str = img_tag.get('height')
                width = None
                height = None

                if width_str and width_str.replace('px','').isdigit():
                    width = int(width_str.replace('px',''))
                if height_str and height_str.replace('px','').isdigit():
                    height = int(height_str.replace('px',''))

                if width is not None and width < MIN_DIMENSION:
                    continue
                if height is not None and height < MIN_DIMENSION:
                    continue
                
                if width is not None and height is not None:
                    if width * height < MIN_AREA:
                        continue
                    if height > 0 and (width / height > MAX_ASPECT_RATIO_DEVIATION):
                        continue
                    if width > 0 and (height / width > MAX_ASPECT_RATIO_DEVIATION):
                        continue
                # --- End Filtering Logic ---

                validated_url = HttpUrl(abs_img_url)
                processed_urls.add(abs_img_url)
                image_counter += 1
                
                alt_text = alt_text_raw or None # Use original case for storage, None if empty
                caption_text: Optional[str] = None
                figure_parent = img_tag.find_parent('figure')
                context_element = figure_parent if figure_parent else img_tag

                if figure_parent and isinstance(figure_parent, Tag):
                    figcaption = figure_parent.find('figcaption')
                    if figcaption and isinstance(figcaption, Tag): caption_text = figcaption.get_text(strip=True)

                if not caption_text:
                    title_attr = img_tag.get('title','').strip()
                    if title_attr: caption_text = title_attr
                    elif alt_text and len(alt_text.split()) > 3: caption_text = alt_text

                images.append(ProcessedWebImage(
                    image_id=_create_image_id(image_counter),
                    image_url=validated_url,
                    alt_text=alt_text,
                    caption=caption_text,
                    source_scope="img_tag",
                    context_before=await self._get_contextual_text(context_element, "before"),
                    context_after=await self._get_contextual_text(context_element, "after")
                ))
            except ValueError: # Pydantic validation error for HttpUrl
                continue
            except Exception as e:
                continue

        # 2. Meta tags (og:image, twitter:image)
        meta_tags_selectors = {
            'og:image': 'meta[property="og:image"]',
            'twitter:image': 'meta[name="twitter:image"]',
            'twitter:image:src': 'meta[name="twitter:image:src"]',
            'og:image:secure_url': 'meta[property="og:image:secure_url"]',
        }
        for key, selector in meta_tags_selectors.items():
            for meta_tag in soup.select(selector):
                if not isinstance(meta_tag, Tag): continue
                content = meta_tag.get('content')
                if content and str(content).strip() and not str(content).startswith('data:image'):
                    try:
                        abs_meta_url = urljoin(base_url, str(content).strip())
                        if abs_meta_url in processed_urls:
                            continue
                        validated_url = HttpUrl(abs_meta_url)
                        processed_urls.add(abs_meta_url)
                        image_counter += 1
                        # Try to get alt/caption from related meta tags if they exist
                        og_alt = soup.find('meta', property='og:image:alt')
                        alt_text_meta = og_alt['content'] if og_alt and isinstance(og_alt, Tag) and og_alt.get('content') else None

                        images.append(ProcessedWebImage(
                            image_id=_create_image_id(image_counter),
                            image_url=validated_url,
                            alt_text=alt_text_meta,
                            caption=f"Image from meta tag ({key})",
                            source_scope="meta_tag"
                        ))
                    except ValueError:
                        continue
                    except Exception as e:
                        continue

        # 3. JSON-LD scripts
        for script_tag in soup.find_all('script', type='application/ld+json'):
            if not isinstance(script_tag, Tag): continue
            try:
                json_ld_content = json.loads(script_tag.string if script_tag.string else "{}")
                if isinstance(json_ld_content, list):
                    for item in json_ld_content:
                        if isinstance(item, dict) and item.get("@type") == "ImageObject" and item.get("contentUrl"):
                            img_url_json = item["contentUrl"]
                            abs_json_img_url = urljoin(base_url, str(img_url_json).strip())
                            if abs_json_img_url in processed_urls:
                                continue
                            validated_url = HttpUrl(abs_json_img_url)
                            processed_urls.add(abs_json_img_url)
                            image_counter += 1
                            images.append(ProcessedWebImage(
                                image_id=_create_image_id(image_counter),
                                image_url=validated_url,
                                alt_text=item.get("caption") or item.get("name"),
                                caption=item.get("description") or "Image from JSON-LD",
                                source_scope="json_ld"
                            ))
                elif isinstance(json_ld_content, dict):
                    if json_ld_content.get("@type") == "ImageObject" and json_ld_content.get("contentUrl"):
                        img_url_json = json_ld_content["contentUrl"]
                        abs_json_img_url = urljoin(base_url, str(img_url_json).strip())
                        if abs_json_img_url not in processed_urls:
                            validated_url = HttpUrl(abs_json_img_url)
                            processed_urls.add(abs_json_img_url)
                            image_counter += 1
                            images.append(ProcessedWebImage(
                                image_id=_create_image_id(image_counter),
                                image_url=validated_url,
                                alt_text=json_ld_content.get("caption") or json_ld_content.get("name"),
                                caption=json_ld_content.get("description") or "Image from JSON-LD",
                                source_scope="json_ld"
                            ))
                    elif "image" in json_ld_content: # Common pattern for articles, etc.
                        image_field = json_ld_content["image"]
                        potential_urls = []
                        if isinstance(image_field, str): potential_urls.append(image_field)
                        elif isinstance(image_field, list):
                            for item in image_field:
                                if isinstance(item, str): potential_urls.append(item)
                                elif isinstance(item, dict) and item.get("url"): potential_urls.append(item["url"])
                        elif isinstance(image_field, dict) and image_field.get("url"):
                            potential_urls.append(image_field["url"])
                        
                        for img_url_item in potential_urls:
                            abs_json_img_url = urljoin(base_url, str(img_url_item).strip())
                            if abs_json_img_url in processed_urls: continue
                            try:
                                validated_url = HttpUrl(abs_json_img_url)
                                processed_urls.add(abs_json_img_url)
                                image_counter += 1
                                images.append(ProcessedWebImage(
                                    image_id=_create_image_id(image_counter),
                                    image_url=validated_url,
                                    alt_text=json_ld_content.get("headline") or "Image from JSON-LD",
                                    caption="Image from JSON-LD structure",
                                    source_scope="json_ld"
                                ))
                            except ValueError:
                                continue
            except json.JSONDecodeError:
                continue
            except Exception as e:
                continue
        
        # 4. <picture> tags (simplified: taking the first <img> or <source> src)
        for pic_tag in soup.find_all('picture'):
            if not isinstance(pic_tag, Tag): continue
            img_in_picture = pic_tag.find('img')
            source_in_picture = pic_tag.find('source')
            pic_src = None
            if img_in_picture and isinstance(img_in_picture, Tag) and img_in_picture.get('src'):
                pic_src = img_in_picture.get('src')
            elif source_in_picture and isinstance(source_in_picture, Tag) and source_in_picture.get('srcset'):
                # Take the first URL from srcset for simplicity
                pic_src = str(source_in_picture.get('srcset', '')).split(',')[0].strip().split(' ')[0]
            
            if pic_src and str(pic_src).strip() and not str(pic_src).startswith('data:image'):
                try:
                    abs_pic_url = urljoin(base_url, str(pic_src).strip())
                    if abs_pic_url in processed_urls:
                        continue
                    validated_url = HttpUrl(abs_pic_url)
                    processed_urls.add(abs_pic_url)
                    image_counter += 1
                    alt_text_pic = img_in_picture.get('alt', '').strip() if img_in_picture and isinstance(img_in_picture, Tag) else None
                    images.append(ProcessedWebImage(
                        image_id=_create_image_id(image_counter),
                        image_url=validated_url,
                        alt_text=alt_text_pic,
                        caption="Image from <picture> element",
                        source_scope="picture_tag"
                    ))
                except ValueError:
                     continue
                except Exception as e:
                    continue

        return images

    async def _parse_html_content(self, html_content: str, final_url: str, processing_level: str, job_id: Optional[str]) -> Dict[str, Any]:
        """Helper to parse HTML, extract text and images using BeautifulSoup and Trafilatura."""
        loop = asyncio.get_event_loop()

        # Run BeautifulSoup parsing in executor
        soup = await loop.run_in_executor(None, BeautifulSoup, html_content, 'lxml')
        page_title_tag = soup.find('title')
        page_title_text = page_title_tag.string.strip() if page_title_tag and isinstance(page_title_tag, Tag) else None
        print(f"WebAcquisitionService._parse_html_content: Page title: {page_title_text}")

        extracted_article_text: Optional[str] = None
        images_found: List[ProcessedWebImage] = []
        is_paywalled_after_parse = False
        paywall_detection_message = ""

        # Common Trafilatura config
        trafilatura_common_config = {
            "include_comments": False, 
            "include_tables": True, 
            "url": final_url
        }

        # Attempt 1: Trafilatura with favor_recall=True, output_format='txt'
        try:
            print(f"WebAcquisitionService._parse_html_content: Attempting Trafilatura (favor_recall=True) for {final_url}")
            trafilatura_func_recall = functools.partial(trafilatura.extract, **trafilatura_common_config, favor_recall=True, output_format='txt')
            text_attempt_1 = await loop.run_in_executor(None, trafilatura_func_recall, html_content)
            print(f"WebAcquisitionService._parse_html_content: Trafilatura (favor_recall) output length: {len(text_attempt_1) if text_attempt_1 else 0}")
            if text_attempt_1 and len(text_attempt_1.strip()) > 100:
                extracted_article_text = text_attempt_1
        except Exception as e_recall: 
            print(f"WebAcquisitionService._parse_html_content: Error during Trafilatura (favor_recall): {str(e_recall)}")

        if not extracted_article_text:
            try:
                print(f"WebAcquisitionService._parse_html_content: Attempting Trafilatura (favor_precision=True, html output) for {final_url}")
                trafilatura_func_precision_html = functools.partial(trafilatura.extract, **trafilatura_common_config, favor_precision=True, output_format='html')
                main_content_html_segment = await loop.run_in_executor(None, trafilatura_func_precision_html, html_content)
                if main_content_html_segment:
                    main_content_soup = await loop.run_in_executor(None, BeautifulSoup, main_content_html_segment, 'lxml')
                    temp_extracted_text = main_content_soup.get_text(separator='\n', strip=True)
                    print(f"WebAcquisitionService._parse_html_content: Trafilatura (favor_precision, html) extracted text length: {len(temp_extracted_text) if temp_extracted_text else 0}")
                    if temp_extracted_text and len(temp_extracted_text.strip()) > 100:
                        extracted_article_text = temp_extracted_text
            except Exception as e_precision: 
                print(f"WebAcquisitionService._parse_html_content: Error during Trafilatura (favor_precision, html): {str(e_precision)}")

        if not extracted_article_text:
            try:
                print(f"WebAcquisitionService._parse_html_content: Attempting Trafilatura (fallback, txt output) for {final_url}")
                trafilatura_func_fallback = functools.partial(trafilatura.extract, **trafilatura_common_config, output_format='txt') # Default recall/precision
                text_attempt_3 = await loop.run_in_executor(None, trafilatura_func_fallback, html_content)
                print(f"WebAcquisitionService._parse_html_content: Trafilatura (fallback, txt) output length: {len(text_attempt_3) if text_attempt_3 else 0}")
                if text_attempt_3 and len(text_attempt_3.strip()) > 100:
                    extracted_article_text = text_attempt_3
            except Exception as e_fallback:
                print(f"WebAcquisitionService._parse_html_content: Error during Trafilatura (fallback, txt): {str(e_fallback)}")
        
        print(f"WebAcquisitionService._parse_html_content: Final extracted_article_text length: {len(extracted_article_text.strip()) if extracted_article_text and extracted_article_text.strip() else 0}")

        # --- Paywall Check (Post-Extraction) ---
        html_lower = html_content.lower()
        for keyword in PAYWALL_KEYWORDS:
            if keyword in html_lower:
                is_paywalled_after_parse = True
                paywall_detection_message = f"Paywall keyword '{keyword}' found in HTML."
                break
        if not is_paywalled_after_parse:
            for selector in PAYWALL_HTML_SELECTORS:
                if soup.select_one(selector):
                    is_paywalled_after_parse = True
                    paywall_detection_message = f"Paywall CSS selector '{selector}' found in HTML."
                    break
        if (not extracted_article_text or len(extracted_article_text.strip()) < 300) and is_paywalled_after_parse:
            pass # Confirmed paywall for output status
        elif extracted_article_text and is_paywalled_after_parse:
            pass # Content extracted, but paywall clues present. is_paywalled_after_parse will be true.

        # --- Image Extraction ---
        if processing_level == "full_content":
            # Call the new comprehensive image extraction method
            try:
                images_found = await self._extract_images_from_html(html_content, final_url, job_id)
                print(f"WebAcquisitionService._parse_html_content: Found {len(images_found)} images via _extract_images_from_html.")
            except Exception as e_img_extract:
                print(f"WebAcquisitionService._parse_html_content: Error during _extract_images_from_html: {str(e_img_extract)}")
                images_found = [] # Ensure it's an empty list on error
        
        return {
            "page_title": page_title_text,
            "extracted_text": extracted_article_text,
            "images": images_found,
            "is_paywalled_after_parse": is_paywalled_after_parse,
            "paywall_detection_message": paywall_detection_message
        }

    async def _get_contextual_text(self, element, direction="before", max_length=150) -> Optional[str]:
        # This function can be blocking if element operations are sync.
        # Consider if it needs run_in_executor or if bs4 is async-friendly enough for simple traversals.
        # For now, assuming it's quick enough or bs4 handles it.
        if not element: return None
        context_snippets = []
        # Simplified logic from WebContentFetcherTool
        # ... (implementation detail: for brevity, this complex logic can be refined or adapted from original tool)
        # This needs careful adaptation to work with BeautifulSoup elements in an async context if complex.
        # A simpler version for now:
        current_node = element
        count = 0
        if direction == "before":
            while current_node and count < 2:
                prev_sibling = current_node.find_previous_sibling(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div'])
                if prev_sibling:
                    text = prev_sibling.get_text(strip=True)
                    if text: context_snippets.insert(0, text)
                    current_node = prev_sibling
                else:
                    current_node = current_node.parent if current_node.parent and current_node.parent.name != 'body' else None
                count +=1
        else: # after
             while current_node and count < 1: # Typically one block after is enough
                next_sibling = current_node.find_next_sibling(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div'])
                if next_sibling:
                    text = next_sibling.get_text(strip=True)
                    if text: context_snippets.append(text)
                    current_node = next_sibling
                else:
                    current_node = current_node.parent if current_node.parent and current_node.parent.name != 'body' else None
                count +=1
        
        full_context = " ".join(context_snippets).strip()
        return (full_context[:max_length] + "...") if len(full_context) > max_length else full_context

    async def _process_image_tag(self, img_tag, base_url: str, is_full_page_scope: bool, processed_urls: Set[str], index: int, job_id: Optional[str]) -> Optional[ProcessedWebImage]:
        # This method is now effectively replaced by the logic within _extract_images_from_html
        # Keeping it here to minimize diff for now, but it's not directly called by the new _parse_html_content flow for image extraction.
        # If called directly, it would still work for single img tags, but _extract_images_from_html is more comprehensive.
        src = img_tag.get('src')
        if not src: src = img_tag.get('data-src')
        if not src: src = img_tag.get('data-original')
        if not src or src.startswith('data:image'): return None

        try:
            abs_img_url_str = urljoin(base_url, src.strip())
            # Basic filter for very small or ad-like images by URL patterns
            if re.search(r'/(ads|banner|pixel|spacer|tracker|sidebar|logo|icon|avatar)s?(_|\.|/)', abs_img_url_str, re.I):
                 if not re.search(r'/content/|/media/|/wp-content/uploads/', abs_img_url_str, re.I): # Allow if it looks like content
                    return None
            if '.svg' in abs_img_url_str.lower() and 'icon' in abs_img_str.lower(): return None # Often small icons

            validated_img_url = HttpUrl(abs_img_url_str)
            if str(validated_img_url) in processed_urls: return None
        except ValueError: return None # Invalid URL

        # Dimension checks (simplified, can be enhanced if library for image size check is added)
        min_dimension = 75 if is_full_page_scope else 50 # Stricter for full page
        try:
            width = img_tag.get('width')
            height = img_tag.get('height')
            if width and width.isdigit() and int(width) < min_dimension: return None
            if height and height.isdigit() and int(height) < min_dimension: return None
        except ValueError: pass


        alt_text = img_tag.get('alt', '').strip() or None
        
        # Caption and context
        caption_text = None
        figure_parent = img_tag.find_parent('figure')
        context_element = figure_parent if figure_parent else img_tag

        if figure_parent:
            figcaption = figure_parent.find('figcaption')
            if figcaption: caption_text = figcaption.get_text(strip=True)

        if not caption_text: # Try title attribute or longer alt text as caption
            title_attr = img_tag.get('title','').strip()
            if title_attr: caption_text = title_attr
            elif alt_text and len(alt_text.split()) > 3: caption_text = alt_text
        
        # Generate unique image ID
        job_id_prefix = f"{job_id}_" if job_id else ""
        # Fallback to hashing part of URL if no job_id and index is not enough for global uniqueness
        unique_part = hashlib.md5(str(validated_img_url).encode()).hexdigest()[:8] if not job_id else str(index + 1)
        image_id = f"WEB_IMG_{job_id_prefix}{unique_part}"

        # Correctly await the async method _get_contextual_text
        context_before = await self._get_contextual_text(context_element, "before")
        context_after = await self._get_contextual_text(context_element, "after")
        
        processed_urls.add(str(validated_img_url))
        return ProcessedWebImage(
            image_id=image_id,
            image_url=validated_img_url,
            alt_text=alt_text,
            caption=caption_text,
            source_scope="full_page_heuristic" if is_full_page_scope else "main_content",
            context_before=context_before,
            context_after=context_after
        )

    async def execute(self, web_input: WebAcquisitionServiceInput) -> ServiceResult[WebAcquisitionServiceOutput]:
        start_time = time.time()
        original_url = web_input.url
        job_id = web_input.job_id

        try:
            # Validate URL early
            parsed_original_url = urlparse(original_url)
            if not all([parsed_original_url.scheme, parsed_original_url.netloc]):
                raise ValueError("Invalid URL scheme or netloc.")
        except ValueError as ve:
            duration = time.time() - start_time
            output = WebAcquisitionServiceOutput(
                status="error_invalid_url", original_url=original_url, error_message=f"Invalid URL format: {ve}",
                processing_duration_seconds=duration
            )
            return ServiceResult.failure(error_message=output.error_message, error_details=output.model_dump())

        # --- Initial URL Filtering (Domain/Path/Strict Paywall) ---
        current_domain = self._get_domain(original_url)
        current_path = parsed_original_url.path

        if self._check_domain_in_set(current_domain, UNSUPPORTED_URL_TYPE_DOMAINS):
            is_allowed_social = any(re.search(p, original_url, re.I) for p in ALLOWED_SOCIAL_MEDIA_POST_PATTERNS)
            is_unsupported_path = any(re.search(p, current_path, re.I) for p in UNSUPPORTED_URL_PATH_PATTERNS)
            if not is_allowed_social or (is_allowed_social and is_unsupported_path) : # An allowed social can still have unsupported path
                 duration = time.time() - start_time
                 output = WebAcquisitionServiceOutput(status="error_unsupported_content_type", original_url=original_url, error_message="URL points to an unsupported page type (e.g., social media feed, video platform).", processing_duration_seconds=duration)
                 return ServiceResult.success(data=output)


        if self._check_domain_in_set(current_domain, VERY_STRICT_PAYWALL_DOMAINS):
            duration = time.time() - start_time
            output = WebAcquisitionServiceOutput(status="error_paywall", original_url=original_url, final_url=original_url, is_paywalled=True, error_message="Site is known for a strict paywall; fetching not attempted.", processing_duration_seconds=duration)
            return ServiceResult.success(data=output)


        # --- HTTP Fetching ---
        final_url_str: Optional[str] = None
        html_content: Optional[str] = None
        pdf_bytes: Optional[bytes] = None
        # response_status_code: Optional[int] = None # Not strictly needed for output if using raise_for_status
        
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "ThinkStashBot/1.0 (compatible; Mozilla/5.0; +http://thinkstash.com/bot)"}) as session:
                async with session.get(original_url, timeout=aiohttp.ClientTimeout(total=20, connect=10), allow_redirects=True) as response:
                    # response_status_code = response.status # Store if needed before raise_for_status
                    final_url_str = str(response.url)
                    response.raise_for_status() # Raises for 4xx/5xx

                    content_type = response.headers.get('Content-Type', '').lower()
                    
                    if 'application/pdf' in content_type or (final_url_str and final_url_str.lower().endswith('.pdf')):
                        pdf_bytes = await response.read()
                        page_title_from_pdf = os.path.basename(urlparse(final_url_str).path)
                        content_disposition = response.headers.get('Content-Disposition')
                        if content_disposition:
                            disp_match = re.search(r"filename\\*?=[\'\\\"]?([^\'\\\"]+)[\'\\\"]?", content_disposition, re.I)
                            if disp_match: page_title_from_pdf = disp_match.group(1)
                        
                        duration = time.time() - start_time
                        output = WebAcquisitionServiceOutput(
                            status="pdf_content_detected", original_url=original_url, final_url=final_url_str,
                            page_title=page_title_from_pdf, pdf_content_bytes=pdf_bytes, processing_duration_seconds=duration
                        )
                        return ServiceResult.success(data=output)

                    if not ('text/html' in content_type or 'application/xhtml+xml' in content_type):
                        duration = time.time() - start_time
                        output = WebAcquisitionServiceOutput(status="error_unsupported_content_type", original_url=original_url, final_url=final_url_str, error_message=f"Unsupported content type: {content_type}", processing_duration_seconds=duration)
                        return ServiceResult.success(data=output)
                    
                    html_content = await response.text()

        except aiohttp.ClientResponseError as e:
            duration = time.time() - start_time
            error_message = f"HTTP error: {e.status} {e.message}"
            page_title_on_error = None 
            # if e.history: final_url_str = str(e.history[-1].url) # final_url_str might be set from successful part of redirect chain
            
            is_paywall_on_error = False
            if e.status in [401, 403, 451]: is_paywall_on_error = True
                
            output = WebAcquisitionServiceOutput(
                status="error_paywall" if is_paywall_on_error else "error_fetch",
                original_url=original_url, final_url=final_url_str or original_url,
                page_title=page_title_on_error,
                is_paywalled=is_paywall_on_error,
                error_message=error_message, processing_duration_seconds=duration
            )
            return ServiceResult.success(data=output)

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            duration = time.time() - start_time
            output = WebAcquisitionServiceOutput(status="error_fetch", original_url=original_url, final_url=final_url_str, error_message=f"Fetch error: {type(e).__name__} - {str(e)}", processing_duration_seconds=duration)
            return ServiceResult.success(data=output)
        except Exception as e:
            duration = time.time() - start_time
            output = WebAcquisitionServiceOutput(status="error_fetch", original_url=original_url, final_url=final_url_str, error_message=f"Unexpected fetch error: {type(e).__name__} - {str(e)}", processing_duration_seconds=duration)
            return ServiceResult.failure(error_message=output.error_message, error_details=output.model_dump())

        if not html_content or not final_url_str:
            duration = time.time() - start_time
            output = WebAcquisitionServiceOutput(status="error_parsing", original_url=original_url, final_url=final_url_str, error_message="No HTML content fetched.", processing_duration_seconds=duration)
            return ServiceResult.success(data=output)

        # --- HTML Parsing, Text/Image Extraction ---
        try:
            # Ensure _parse_html_content uses the job_id from web_input
            parsed_data = await self._parse_html_content(html_content, final_url_str, web_input.processing_level, web_input.job_id)
        except Exception as e:
            duration = time.time() - start_time
            output = WebAcquisitionServiceOutput(
                status="error_parsing", original_url=original_url, final_url=final_url_str,
                error_message=f"Error during HTML parsing: {str(e)}", processing_duration_seconds=duration
            )
            return ServiceResult.failure(error_message=output.error_message, error_details=output.model_dump())

        final_status = "success"
        final_is_paywalled = parsed_data.get("is_paywalled_after_parse", False)
        extracted_text_final = parsed_data.get("extracted_text")
        
        if final_is_paywalled and not extracted_text_final:
            final_status = "error_paywall"
        elif not extracted_text_final and not parsed_data.get("images"):
            if final_status != "error_paywall": final_status = "error_parsing"
            parsed_data["error_message"] = parsed_data.get("error_message", "Could not extract significant text or images.")

        duration = time.time() - start_time
        output = WebAcquisitionServiceOutput(
            status=final_status,
            original_url=original_url,
            final_url=final_url_str,
            page_title=parsed_data.get("page_title"),
            extracted_text=extracted_text_final,
            images=parsed_data.get("images"),
            is_paywalled=final_is_paywalled,
            error_message=parsed_data.get("error_message") if final_status != "success" else (parsed_data.get("paywall_detection_message") if final_is_paywalled else None),
            processing_duration_seconds=duration
        )
        return ServiceResult.success(data=output)

# Example (for local testing if needed)
async def main_test():
    service = WebAcquisitionService()
    # test_url = "https://www.example.com"
    test_url = "https://www.deeplearning.ai/the-batch/issue-301/"
    # test_url = "https://www.wsj.com/articles/some-article" # Paywall
    # test_url = "http://example.com/nonexistent.pdf" # Test PDF link that might 404 or be actual PDF

    inp = WebAcquisitionServiceInput(url=test_url, processing_level="full_content", job_id="testjob123")
    result = await service.execute(inp)

    if result.status == 'success':
        print("Service executed successfully!")
        output_data = result.data
        if output_data:
            print(f"Status: {output_data.status}")
            print(f"Title: {output_data.page_title}")
            print(f"Final URL: {output_data.final_url}")
            print(f"Is Paywalled: {output_data.is_paywalled}")
            # print(f"Text: {output_data.extracted_text[:200] if output_data.extracted_text else 'N/A'}...")
            if output_data.images:
                print(f"Found {len(output_data.images)} images.")
                # for img in output_data.images:
                #     print(f"  - ID: {img.image_id}, URL: {img.image_url}, Caption: {img.caption}")
            if output_data.pdf_content_bytes:
                print(f"PDF content detected, size: {len(output_data.pdf_content_bytes)} bytes")
            if output_data.error_message:
                 print(f"Error Message: {output_data.error_message}")

    else:
        print(f"Service execution failed: {result.error_message}")
        if result.error_details:
            print(f"Details: {result.error_details}")

if __name__ == "__main__":
    # # To run the test:
    # # Ensure you have a running event loop or use asyncio.run()
    # # This might require additional setup if run directly without a framework like FastAPI
    # try:
    #     asyncio.run(main_test())
    # except RuntimeError as e:
    #     if "There is no current event loop in thread" in str(e):
    #         print("Cannot run asyncio.run in this context (e.g. Jupyter notebook already has a loop).")
    #         print("Consider running in a separate Python script or adapting for existing loop.")
    #     else:
    #        raise
    pass 