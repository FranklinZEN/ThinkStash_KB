from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

try:
    from url_normalize import url_normalize
except ImportError:
    print("WARNING: url-normalize library not found. Falling back to basic normalization for URLs.")
    url_normalize = None

def custom_normalize_url(url_string: str) -> str:
    original_url_for_fallback = str(url_string) # Ensure it's a string for operations

    # Step 1: Handle specific prefixes like chrome-extension://
    chrome_extension_prefix = "chrome-extension://"
    if original_url_for_fallback.startswith(chrome_extension_prefix):
        # Try to extract the actual URL part after the extension ID
        # Example: chrome-extension://<extension_id>/<actual_url>
        # We split by '/' at most 3 times: "chrome-extension:", "", "<extension_id>", "<actual_url_part>"
        parts = original_url_for_fallback.split('/', 3)
        if len(parts) > 3 and (parts[3].startswith("http:") or parts[3].startswith("https://")):
            url_string = parts[3]
        elif len(parts) > 3: # It has content after extension ID but not a clear http/https
             # Prepend https:// to the remainder, assuming it's a domain/path meant to be a URL
            url_string = "https://" + parts[3]
        else:
            # Not a pattern we can easily extract a standard URL from,
            # pass through and let url_normalize or manual parsing attempt it.
            # Or, consider returning original_url_for_fallback or raising an error if this pattern is invalid.
            url_string = original_url_for_fallback # Proceed with the original if unsure
    else:
        url_string = original_url_for_fallback


    # Step 2: Use url-normalize library if available
    if url_normalize:
        try:
            # url_normalize typically handles scheme addition, www removal, port removal, etc.
            normalized_url = url_normalize(url_string, default_scheme="https")
            return normalized_url
        except Exception as e_lib:
            print(f"url-normalize failed for '{url_string}': {e_lib}. Attempting manual normalization.")
            # Fall through to manual normalization if url_normalize fails
            # url_string at this point is either the original or the one stripped of chrome-extension

    # Step 3: Manual normalization (fallback or if url_normalize is not installed/failed)
    try:
        parsed = urlparse(url_string)
        
        current_scheme = parsed.scheme.lower() if parsed.scheme else ""
        current_netloc = parsed.netloc.lower() if parsed.netloc else ""
        current_path = parsed.path
        
        # Ensure a scheme exists, default to https.
        if not current_scheme:
            # If netloc is missing but path looks like a domain (e.g. "example.com/page")
            if not current_netloc and current_path and not current_path.startswith('/'):
                # Try to parse again assuming path was the netloc
                potential_netloc_parts = current_path.split('/', 1)
                current_netloc = potential_netloc_parts[0].lower()
                current_path = '/' + potential_netloc_parts[1] if len(potential_netloc_parts) > 1 else '/'
                current_scheme = "https" # Default scheme
            elif current_netloc: # Netloc exists, scheme was missing
                current_scheme = "https"
            else: # No clear netloc, problematic URL
                return original_url_for_fallback # Cannot reliably normalize

        # Remove default port
        if (current_scheme == "http" and current_netloc.endswith(":80")) or \
           (current_scheme == "https" and current_netloc.endswith(":443")):
            current_netloc = current_netloc.rsplit(":", 1)[0]
        
        # Remove 'www.' prefix
        if current_netloc.startswith("www."):
            current_netloc = current_netloc[4:]

        # Path normalization: remove duplicate slashes, handle dot segments (simplified)
        # A more robust solution for dot segments (./ and ../) is complex.
        # For now, just ensure path starts with a slash if netloc is present.
        normalized_path_segments = []
        if current_path:
            segments = current_path.split('/')
            for segment in segments:
                if segment == "..":
                    if normalized_path_segments:
                        normalized_path_segments.pop()
                elif segment != "." and segment != "": # Keep legitimate empty segments if they mean something (e.g. from //)
                    normalized_path_segments.append(segment)
        
        # Reconstruct path. If it was originally just "/", keep it. If segments made it empty, make it "/".
        # If original path had segments (e.g. /a/b), it should lead with empty string from split -> /a/b
        if not current_path:
             current_path = "/"
        elif current_path == "/":
             pass # Keep as is
        else:
            current_path = "/" + "/".join(normalized_path_segments) 
            current_path = current_path.replace('//','/') # Remove duplicate slashes one last time

        if not current_path and current_netloc: # If path became empty but there's a domain, should be "/"
            current_path = "/"


        # Query parameter sorting
        query_params_dict = parse_qs(parsed.query, keep_blank_values=True)
        sorted_query_items = sorted(query_params_dict.items())
        query_string = urlencode(sorted_query_items, doseq=True)
        
        # Remove fragment
        fragment_string = ""

        return urlunparse((current_scheme, current_netloc, current_path, parsed.params, query_string, fragment_string))

    except Exception as e_manual:
        print(f"Error during manual normalization of '{url_string}' (original: '{original_url_for_fallback}'): {e_manual}")
        return original_url_for_fallback # Return original if all attempts fail 