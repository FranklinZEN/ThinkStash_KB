from thinkstash_ai_service.models import WebContent, StructuredData, Link, Image # Ensure Image is imported if not already
import aiohttp # Keep existing imports
from typing import Any # Keep existing imports
from thinkstash_ai_service.services.base_service import BaseService # Keep existing imports
from bs4 import BeautifulSoup
import urllib.parse
import json
import trafilatura # Assuming trafilatura is used as hinted in logs

class WebAcquisitionService(BaseService):
    def __init__(self, settings: Any = None):
        super().__init__(settings)
        print("<<<<< EXECUTING LATEST WebAcquisitionService __init__ VERSION 5.0 >>>>>") # Test print
        # Placeholder for AD_PATTERN and CONTENT_EXCLUSION_PATTERN if needed later for _is_potential_ad_or_filtered
        # For now, the new _extract_images_from_html doesn't use them directly.
        self.AD_PATTERN = None 
        self.CONTENT_EXCLUSION_PATTERN = None

    async def _is_potential_ad_or_filtered(self, img_tag: Any, img_src: str, min_dimension: int = 75) -> bool:
        # This is a pre-existing filtering logic that was causing issues.
        # We will bypass this for now by having it return False, 
        # allowing _extract_images_from_html to do its job more comprehensively.
        # The DEBUG messages from the log originated from a method like this.
        # print(f"DEBUG_IMG_PROCESS: Initial src found: {img_src}")
        # print(f"DEBUG_IMG_PROCESS: Absolute URL: {img_src}") 
        # print(f"DEBUG_IMG_PROCESS: Potential ad/pixel pattern matched: {bool(self.AD_PATTERN and self.AD_PATTERN.search(img_src))}")
        # print(f"DEBUG_IMG_PROCESS: Content exclusion pattern matched: {bool(self.CONTENT_EXCLUSION_PATTERN and self.CONTENT_EXCLUSION_PATTERN.search(img_src))}")
        # width = img_tag.get('width')
        # height = img_tag.get('height')
        # print(f"DEBUG_IMG_PROCESS: Dimension check - width_attr: '{width}', height_attr: '{height}', min_dim: {min_dimension}")
        # if width and height:
        #     try:
        #         if int(width) < min_dimension or int(height) < min_dimension:
        #             print(f"DEBUG_IMG_PROCESS: FILTERED OUT by small dimension.")
        #             return True
        #     except ValueError:
        #         pass # Non-integer dimension
        # if not width and not height: # Check parent if dimensions are in style
        #     style = img_tag.get('style', '')
        #     # Simplified style parsing, real parsing is more complex
        #     # if f'width:{min_dimension}px' in style or f'height:{min_dimension}px' in style: return True 
        return False # Effectively bypasses this filter for now

    async def _fetch_and_parse_url(self, session: aiohttp.ClientSession, url: str) -> WebContent:
        print("<<<<< EXECUTING LATEST _fetch_and_parse_url VERSION 5.0 >>>>>") # Test print
        """Fetches content from a URL and parses it into a WebContent object."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        html_content = ""
        page_title = ""
        extracted_article_text = ""
        links = []
        images = [] # Initialize images list
        structured_data_list = []
        # soup_for_trafilatura = None # Not strictly needed if trafilatura takes string

        try:
            async with session.get(url, headers=headers, timeout=20) as response:
                response.raise_for_status() # Raise an exception for HTTP errors
                html_content = await response.text()
                # base_url_for_images = str(response.url) # Use the final URL after any redirects

                # Attempt to parse with BeautifulSoup early for title and full content access
                full_soup = BeautifulSoup(html_content, 'html.parser')
                
                title_tag = full_soup.find('title')
                if title_tag and title_tag.string:
                    page_title = title_tag.string.strip()
                # print(f"WebAcquisitionService._parse_html_content: Page title: {page_title}") # Redundant with below

                # Text extraction using Trafilatura (as hinted in logs)
                # Favor recall to get more content, then can be refined by structuring LLM
                print(f"WebAcquisitionService: Attempting Trafilatura (favor_recall=True) for {url}")
                extracted_article_text = trafilatura.extract(html_content, 
                                                             include_comments=False, 
                                                             include_tables=True, 
                                                             favor_recall=True,
                                                             deduplicate=True)
                if not extracted_article_text:
                    # Fallback or further attempts if trafilatura fails or returns too little
                    print(f"WebAcquisitionService: Trafilatura returned little or no content for {url}. Consider fallback.")
                    # As a simple fallback, could use full_soup.get_text() or a portion of it
                    # extracted_article_text = full_soup.get_text(separator='\n', strip=True) # Basic fallback
                
                print(f"WebAcquisitionService: Final extracted_article_text length: {len(extracted_article_text if extracted_article_text else '')}")

                # Extract Links, Images, and Structured Data using the full_soup
                links = await self._extract_links(full_soup, str(response.url))
                images = await self._extract_images_from_html(html_content, str(response.url)) # Call the new method
                structured_data_list = await self._extract_structured_data(full_soup)

                # The old image extraction logic that used _is_potential_ad_or_filtered
                # has been replaced by the call to _extract_images_from_html above.
                # Any remaining DEBUG messages related to old filtering are from stale code execution if they persist.

        except aiohttp.ClientError as e:
            print(f"Error fetching URL {url}: {e}")
            # Consider returning a WebContent object with error information
            return WebContent(url=url, title="Error fetching content", raw_text=str(e), article_text=str(e), links=[], images=[], structured_data=[], metadata={})
        except Exception as e:
            print(f"An unexpected error occurred while processing {url}: {e}")
            return WebContent(url=url, title="Error processing content", raw_text=str(e), article_text=str(e), links=[], images=[], structured_data=[], metadata={})

        return WebContent(
            url=url,
            title=page_title,
            raw_text=html_content, # Full HTML
            article_text=extracted_article_text if extracted_article_text else "", # Main content text
            links=links,
            images=images, # Pass the extracted images
            structured_data=structured_data_list,
            metadata={}
        )

    async def _extract_links(self, soup: Any, base_url: str) -> list[Link]:
        # print("<<<<< STUB _extract_links VERSION 5.0 >>>>>")
        # Placeholder for now, assuming it might be complex or defined elsewhere fully
        # For E2E test to pass without error if it relies on this structure:
        found_links = []
        if soup and hasattr(soup, 'find_all'):
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                text = a_tag.string.strip() if a_tag.string else ''
                try:
                    absolute_url = urllib.parse.urljoin(base_url, href.strip())
                    if absolute_url not in [link.url for link in found_links]: # Basic deduplication
                         # Basic validation for http/https links
                        parsed_url = urllib.parse.urlparse(absolute_url)
                        if parsed_url.scheme in ['http', 'https']:
                            found_links.append(Link(url=absolute_url, text=text, type='related')) # Assuming 'related' type
                except Exception as e:
                    print(f"Error processing link URL '{href}': {e}")
        return found_links

    async def _extract_images_from_html(self, html_content: str, base_url: str) -> list[Image]:
        print("<<<<< EXECUTING LATEST _extract_images_from_html VERSION 5.0 >>>>>") # Test print
        """
        Extracts image URLs from HTML content.

        This method should parse the HTML to find images from various sources like
        <img> tags, <meta property="og:image">, <meta name="twitter:image">,
        JSON-LD scripts, and <picture> elements.
        It should also handle relative URLs by converting them to absolute URLs
        using the provided base_url.

        Args:
            html_content: The HTML content of the webpage as a string.
            base_url: The base URL of the webpage, used for resolving relative image paths.

        Returns:
            A list of Image objects, each containing the URL and potentially other metadata
            if available (like alt text).
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        found_images: list[Image] = []
        image_urls_seen: set[str] = set()

        def add_image(url: str | None, alt_text: str | None = None) -> None:
            if not url:
                return
            try:
                # Ensure the URL is not excessively long to prevent issues
                if len(url) > 2048: # Max URL length, can be adjusted
                    print(f"Skipping excessively long URL: {url[:100]}...")
                    return

                absolute_url = urllib.parse.urljoin(base_url, url.strip()) # Added strip()
                if absolute_url not in image_urls_seen:
                    parsed_url = urllib.parse.urlparse(absolute_url)
                    if parsed_url.scheme in ['http', 'https']:
                        # Consider adding a check for valid content types if fetching images later
                        found_images.append(Image(url=absolute_url, alt=alt_text if alt_text else ""))
                        image_urls_seen.add(absolute_url)
                    elif not parsed_url.scheme and parsed_url.path: # Handle relative paths properly
                        # This case should be covered by urljoin, but as a fallback if it's missed
                        if not absolute_url.lower().startswith("data:image"):
                            found_images.append(Image(url=absolute_url, alt=alt_text if alt_text else ""))
                            image_urls_seen.add(absolute_url)
                    # else: print(f"Skipping URL with unhandled scheme or structure: {absolute_url}")

            except Exception as e:
                print(f"Error processing image URL '{url}': {e}")

        # 1. <img> tags
        for img_tag in soup.find_all('img'):
            src = img_tag.get('src')
            alt = img_tag.get('alt')
            if src:
                add_image(src, alt)

            srcset = img_tag.get('srcset')
            if srcset:
                srcset_parts = srcset.split(',')
                for part in srcset_parts:
                    src_candidate_info = part.strip().split(' ')
                    if src_candidate_info and src_candidate_info[0]:
                        add_image(src_candidate_info[0], alt)
            
            data_src = img_tag.get('data-src') # Common for lazy loading
            if data_src:
                add_image(data_src, alt)

        # 2. <meta property="og:image">
        og_image_tag = soup.find('meta', property='og:image')
        if og_image_tag and og_image_tag.get('content'):
            add_image(og_image_tag['content'])
        
        og_image_secure_url_tag = soup.find('meta', property='og:image:secure_url')
        if og_image_secure_url_tag and og_image_secure_url_tag.get('content'):
            add_image(og_image_secure_url_tag['content'])

        # 3. <meta name="twitter:image"> / <meta name="twitter:image:src">
        twitter_image_tag = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image_tag and twitter_image_tag.get('content'):
            add_image(twitter_image_tag['content'])

        twitter_image_src_tag = soup.find('meta', attrs={'name': 'twitter:image:src'})
        if twitter_image_src_tag and twitter_image_src_tag.get('content'):
            add_image(twitter_image_src_tag['content'])

        # 4. JSON-LD
        for script_tag in soup.find_all('script', type='application/ld+json'):
            try:
                if script_tag.string:
                    data = json.loads(script_tag.string)
                    
                    def find_images_in_json(item: Any) -> None:
                        if isinstance(item, dict):
                            if item.get('@type') == 'ImageObject':
                                if item.get('contentUrl'): add_image(item['contentUrl'], item.get('caption') or item.get('name'))
                                elif item.get('url'): add_image(item['url'], item.get('caption') or item.get('name'))
                            elif item.get('image'):
                                image_data = item['image']
                                find_images_in_json(image_data) 
                            else:
                                for key, value in item.items():
                                    if key in ['thumbnail', 'logo', 'photo', 'picture', 'thumbnailUrl'] and isinstance(value, str):
                                        add_image(value)
                                    elif isinstance(value, (dict, list)):
                                        find_images_in_json(value)
                        elif isinstance(item, list):
                            for sub_item in item:
                                find_images_in_json(sub_item)
                        # elif isinstance(item, str) and (item.startswith('http://') or item.startswith('https://')):
                        #     pass # Decided against being too greedy here

                    find_images_in_json(data)

            except (json.JSONDecodeError, TypeError):
                pass 

        # 5. <picture> elements
        for pic_tag in soup.find_all('picture'):
            source_url = None
            alt_text = None
            img_in_picture = pic_tag.find('img')
            if img_in_picture:
                alt_text = img_in_picture.get('alt')

            for source_elem in pic_tag.find_all('source'):
                srcset = source_elem.get('srcset')
                if srcset:
                    srcset_parts = srcset.split(',')
                    if srcset_parts:
                        first_url_candidate = srcset_parts[0].strip().split(' ')[0]
                        if first_url_candidate:
                            source_url = first_url_candidate
                            break 
            if source_url:
                add_image(source_url, alt_text)
            elif img_in_picture and img_in_picture.get('src'):
                add_image(img_in_picture['src'], alt_text)
        
        # 6. <link rel="image_src">
        link_image_src_tag = soup.find('link', rel='image_src')
        if link_image_src_tag and link_image_src_tag.get('href'):
            add_image(link_image_src_tag['href'])
            
        print(f"WebAcquisitionService: Extracted {len(found_images)} images using BeautifulSoup method. Version 5.0") # Added version to print
        return found_images

    async def _extract_structured_data(self, soup: Any) -> list[StructuredData]:
        # print("<<<<< STUB _extract_structured_data VERSION 5.0 >>>>>")
        # Placeholder for now
        return [] # Return empty list to satisfy type hint

    async def run(self, url: str, content_type_hint: str = "url", level: str = "full_content") -> WebContent:
        print("<<<<< EXECUTING LATEST WebAcquisitionService run METHOD VERSION 5.0 >>>>>") # Test print
        """Main entry point to acquire web content."""
        async with aiohttp.ClientSession() as session:
            # TODO: Implement caching lookup here in the future
            # web_content_cached = await self._check_cache(url, level)
            # if web_content_cached:
            #     return web_content_cached

            web_content = await self._fetch_and_parse_url(session, url)
            
            # TODO: Implement caching storage here in the future
            # if web_content and not web_content.metadata.get("error"):
            # await self._store_cache(url, level, web_content)
            
            return web_content 