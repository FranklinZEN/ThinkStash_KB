import requests
from crewai.tools import BaseTool
import os
import mimetypes # For guessing type from extension
from typing import Type, Optional, Dict, Any # Added Dict, Any
from pydantic import BaseModel, Field # Added Pydantic imports

class ContentTypeDetectionToolInput(BaseModel):
    identifier: str = Field(..., description="The file path or URL to detect content type from.")
    is_file: Optional[bool] = Field(default=None, description="Specify if the identifier is a file path (True) or URL (False). Tool will infer if None.")

class ContentTypeDetectionTool(BaseTool):
    """Detects content type for files and URLs using mimetypes and HEAD requests.

    For local files, it uses the `mimetypes` module to guess based on extension.
    For URLs, it attempts a HEAD request to get the Content-Type header and also checks extensions.
    Designed to be used by the OrchestrationAgent for routing.
    """
    name: str = "Content Type Detector (mimetypes/requests)"
    description: str = (
        "Detects or infers a simplified content type (e.g., 'html', 'pdf', 'docx', 'text') "
        "from a local file path or a URL. "
        "Input to the tool should be a string: the file path or the URL. "
        "An optional boolean 'is_file' can specify if the input is a file path (True) or URL (False); "
        "if omitted, the tool attempts to infer this."
    )
    args_schema: Type[BaseModel] = ContentTypeDetectionToolInput # Explicitly set args_schema

    def _run(self, identifier: str, is_file: Optional[bool] = None) -> str:
        print(f"ContentTypeDetectionTool (mimetypes): Running for identifier: {identifier}, is_file: {is_file}")
        simplified_type = "unknown"

        if is_file is None:
            if identifier.startswith("http://") or identifier.startswith("https://"):
                is_file = False
            elif os.path.exists(identifier):
                is_file = True
            else:
                print(f"ContentTypeDetectionTool (mimetypes): Ambiguous identifier '{identifier}'. Assuming URL as it doesn't exist locally.")
                is_file = False 

        try:
            if is_file:
                print(f"ContentTypeDetectionTool (mimetypes): Processing as file: {identifier}")
                if not os.path.exists(identifier):
                    print(f"ContentTypeDetectionTool (mimetypes): File not found: {identifier}")
                    return "error_file_not_found"
                
                # Use mimetypes to guess type from extension
                mime_type, _ = mimetypes.guess_type(identifier)
                print(f"ContentTypeDetectionTool (mimetypes): Guessed MIME type (file): {mime_type}")
                
                if mime_type:
                    simplified_type = self._simplify_mime_type(mime_type)
                else: 
                    # If mimetypes returns None, try to infer from common extensions
                    _, ext = os.path.splitext(identifier)
                    ext = ext.lower()
                    print(f"ContentTypeDetectionTool (mimetypes): MIME type was None, trying extension '{ext}' directly.")
                    if ext == ".pdf":
                        simplified_type = "pdf"
                    elif ext == ".docx":
                        simplified_type = "docx"
                    elif ext == ".md":
                        simplified_type = "md"
                    elif ext == ".txt":
                        simplified_type = "txt"
                    elif ext in [".jpg", ".jpeg"]:
                        simplified_type = "jpeg"
                    elif ext == ".png":
                        simplified_type = "png"
                    # Add other common extensions here if needed
                    else:
                        simplified_type = "unknown_file_type"
                
                # Fallback if still unknown after extension check
                if simplified_type == "unknown":
                     simplified_type = "unknown_file_type"

            else: # It's a URL
                print(f"ContentTypeDetectionTool (mimetypes): Processing as URL: {identifier}")
                # For URLs, first try to infer from path extension
                parsed_url = requests.utils.urlparse(identifier)
                path = parsed_url.path
                ext = os.path.splitext(path)[1].lower()
                
                # Try extension first
                if ext:
                    simplified_type_from_ext = self._simplify_mime_type(mimetypes.guess_type(f"file.{ext}")[0] or "")
                    if simplified_type_from_ext != "unknown":
                        simplified_type = simplified_type_from_ext
                        print(f"ContentTypeDetectionTool (mimetypes): Inferred type from URL extension '{ext}': {simplified_type}")

                # If type is still unknown or HTML (common default), try HEAD request for more specific type
                if simplified_type == "unknown" or simplified_type == "html" or not ext:
                    print(f"ContentTypeDetectionTool (mimetypes): Extension type is '{simplified_type}'. Attempting HEAD request for {identifier}")
                    try:
                        # Ensure URL has a scheme
                        url_to_fetch = identifier
                        if not parsed_url.scheme:
                            url_to_fetch = "http://" + identifier # Default to http, requests will handle https upgrade if any
                            print(f"ContentTypeDetectionTool (mimetypes): Prepended http:// to URL: {url_to_fetch}")
                        
                        response = requests.head(url_to_fetch, timeout=5, allow_redirects=True)
                        response.raise_for_status() 
                        content_type_header = response.headers.get('Content-Type', '').lower()
                        print(f"ContentTypeDetectionTool (mimetypes): Detected Content-Type header (URL): {content_type_header}")
                        simplified_type_from_header = self._simplify_mime_type(content_type_header)
                        
                        if simplified_type_from_header != "unknown":
                            simplified_type = simplified_type_from_header
                        elif simplified_type == "unknown": # If header was also unhelpful, and extension was too
                            simplified_type = "html" # Default to HTML for generic web URLs if all else fails

                    except requests.RequestException as e:
                        print(f"ContentTypeDetectionTool (mimetypes): Error during HEAD request for {identifier}: {e}")
                        if simplified_type == "unknown": # If extension didn't help and HEAD failed
                             simplified_type = "error_url_fetch" 
                        # If extension gave a hint (e.g. .pdf but HEAD failed), we might stick with it or error
                        # For now, if ext gave a type, we keep it even if HEAD fails.
            
        except Exception as e:
            print(f"ContentTypeDetectionTool (mimetypes): Error during content type detection for {identifier}: {e}")
            simplified_type = "error_detection_failed"
        
        print(f"ContentTypeDetectionTool (mimetypes): Final simplified type: {simplified_type}")
        return simplified_type

    def _simplify_mime_type(self, mime_type: str) -> str:
        """Converts a full MIME type string to a simplified common type string."""
        if not mime_type: return "unknown"
        mime_type = mime_type.lower()
        if 'pdf' in mime_type: return 'pdf'
        elif 'vnd.openxmlformats-officedocument.wordprocessingml.document' in mime_type: return 'docx'
        elif 'msword' in mime_type: return 'docx' 
        elif 'html' in mime_type: return 'html'
        elif 'markdown' in mime_type or mime_type == 'text/md': return 'md'
        elif 'plain' in mime_type or 'text/text' in mime_type: return 'txt' # common for .txt
        elif 'text' in mime_type: return 'txt' # Broader catch for other text types as txt
        elif 'jpeg' in mime_type or 'jpg' in mime_type: return 'jpeg'
        elif 'png' in mime_type: return 'png'
        elif 'json' in mime_type: return 'json'
        return "unknown"

class DataStoreAccessToolInput(BaseModel):
    action: str = Field(description="Action to perform: 'put' or 'get'.")
    key: str = Field(description="The key to use for storing or retrieving data.")
    value: Optional[Any] = Field(default=None, description="The value to store (only for 'put' action).")

class DataStoreAccessTool(BaseTool):
    name: str = "Data Store Access Tool"
    description: str = "Allows storing and retrieving data from a shared crew data store. Use 'put' to store data with a key, and 'get' to retrieve data using a key."
    args_schema: Type[BaseModel] = DataStoreAccessToolInput
    data_store: Dict[str, Any]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(self, action: str, key: str, value: Optional[Any] = None) -> Any:
        print(f"DataStoreAccessTool: Action='{action}', Key='{key}', Value provided: {value is not None}")
        if action == "put":
            self.data_store[key] = value
            print(f"DataStoreAccessTool: Stored data under key '{key}'.")
            return f"Data successfully stored under key '{key}'."
        elif action == "get":
            retrieved_value = self.data_store.get(key)
            if retrieved_value is not None:
                print(f"DataStoreAccessTool: Retrieved data for key '{key}'.")
                return retrieved_value
            else:
                print(f"DataStoreAccessTool: No data found for key '{key}'.")
                return None
        else:
            return "Error: Invalid action. Must be 'put' or 'get'."

# Example Usage (not part of the tool, just for illustration during development)
if __name__ == '__main__':
    tool = ContentTypeDetectionTool()
    
    # Create dummy files for local testing
    dummy_files_created = []
    def create_dummy_file(name, content=""):
        with open(name, "w") as f: f.write(content)
        dummy_files_created.append(name)

    create_dummy_file("dummy.txt", "Hello text file")
    create_dummy_file("dummy.md", "# Hello Markdown")
    create_dummy_file("dummy.html", "<h1>Hello HTML</h1>")
    create_dummy_file("dummy.pdf", "") # Extension based
    create_dummy_file("dummy.docx", "")# Extension based
    create_dummy_file("no_ext_file", "some data")

    print(f"dummy.txt (file): {tool._run('dummy.txt')}")
    print(f"dummy.md (file): {tool._run('dummy.md')}") 
    print(f"dummy.html (file): {tool._run('dummy.html')}")
    print(f"dummy.pdf (file): {tool._run('dummy.pdf')}")
    print(f"dummy.docx (file): {tool._run('dummy.docx')}")
    print(f"no_ext_file (file): {tool._run('no_ext_file')}")
    print(f"https://www.google.com (url): {tool._run('https://www.google.com')}")
    print(f"http://example.com/document.pdf (url): {tool._run('http://example.com/document.pdf')}")
    print(f"http://example.com/image.png (url): {tool._run('http://example.com/image.png')}")
    print(f"http://example.com/data.json (url): {tool._run('http://example.com/data.json')}")
    print(f"non_existent_file.txt (file): {tool._run('non_existent_file.txt')}")
    print(f"http://nonexistenturl12345zzzz.com (url): {tool._run('http://nonexistenturl12345zzzz.com')}")
    print(f"example.com/somepage (url, no scheme): {tool._run('example.com/somepage')}")

    # Clean up dummy files
    for df_path in dummy_files_created:
        if os.path.exists(df_path): os.remove(df_path) 