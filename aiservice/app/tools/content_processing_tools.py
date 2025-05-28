import requests
from PIL import Image # Pillow for image metadata
from google.cloud import storage # Google Cloud Storage
from crewai.tools import BaseTool
import os
import uuid # For generating unique filenames
import io # For handling image bytes
from aiservice.app.config.settings import settings # New import for V2.5 settings

class ImageDownloaderTool(BaseTool):
    name: str = "Image Downloader from URL"
    description: str = (
        "Downloads an image from a given URL and saves it to a specified temporary local folder. "
        "Input: 'image_url' (string: the URL of the image to download), "
        "'output_folder' (string: local folder to save the downloaded image, defaults to 'temp_downloaded_images')."
        "Returns a dictionary with 'local_path' (string) to the saved image, 'original_url' (string), "
        "'filename' (string), 'content_type' (string) from response headers, and 'error' (string, if any)."
    )

    def _run(self, image_url: str, output_folder: str = "temp_downloaded_images") -> dict:
        """Downloads an image from a URL or confirms a local file path.

        Args:
            image_url: The URL of the image or a local file path.
            output_folder: Local folder to save the image if downloaded.

        Returns:
            A dictionary with image details or an error message.
        """
        # Check if image_url is a local path first
        if isinstance(image_url, str) and os.path.exists(image_url):
            print(f"ImageDownloaderTool: Identified '{image_url}' as an existing local file path.")
            # For local files, we don't download. We just confirm its existence and format the output.
            filename = os.path.basename(image_url)
            # Try to guess content type for local files, similar to GCSUploadTool
            ext = os.path.splitext(filename)[1].lower()
            content_type_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp',
                '.tiff': 'image/tiff'
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')
            return {
                "local_path": image_url, # It's already local
                "original_url": image_url, # Treat path as original identifier
                "filename": filename,
                "content_type": content_type,
                "error": None
            }

        if not isinstance(image_url, str) or not image_url.startswith(('http://', 'https://')):
            return {"error": "Invalid image URL or non-existent local path provided.", "local_path": None}

        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder, exist_ok=True)
            except OSError as e:
                return {"error": f"Could not create output folder {output_folder}: {e}", "local_path": None}
        
        try:
            response = requests.get(image_url, stream=True, timeout=20)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', 'application/octet-stream')
            # Basic check for image content types
            if not content_type.lower().startswith('image/'):
                return {"error": f"URL does not point to a recognized image type. Content-Type: {content_type}", "local_path": None, "original_url": image_url}

            # Generate a unique filename to avoid collisions
            file_extension = '.' + content_type.split('/')[-1].split(';')[0] # e.g., .jpeg, .png
            if file_extension == '.None' or len(file_extension) > 5 : # Basic sanity check for extension
                 # Try to guess from URL if content_type is too generic (e.g. application/octet-stream for a .png link)
                if image_url.lower().endswith('.png'): file_extension = '.png'
                elif image_url.lower().endswith(('.jpg', '.jpeg')): file_extension = '.jpeg'
                elif image_url.lower().endswith('.gif'): file_extension = '.gif'
                else: file_extension = '.img' # Fallback generic extension
            
            filename = str(uuid.uuid4()) + file_extension
            local_file_path = os.path.join(output_folder, filename)

            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return {
                "local_path": local_file_path,
                "original_url": image_url,
                "filename": filename,
                "content_type": content_type,
                "error": None
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Error downloading image {image_url}: {e}", "local_path": None, "original_url": image_url}
        except Exception as e_save:
            return {"error": f"Error saving image {image_url} to {local_file_path}: {e_save}", "local_path": None, "original_url": image_url}

class GCSUploadTool(BaseTool):
    name: str = "Google Cloud Storage (GCS) Image Uploader"
    description: str = (
        "Uploads a local image file to a specified Google Cloud Storage bucket. "
        "Input: 'local_file_path' (string: path to the local image file), "
        "'gcs_blob_name' (string: desired name for the image blob in GCS, should be unique, can include folders e.g., 'folder/image.png')."
        "An optional 'gcs_bucket_name' can be provided if not set during initialization. "
        "Returns a dictionary with 'gcs_url' (string) of the uploaded image and 'error' (string, if any). "
        "NOTE: Requires GCS credentials to be configured in the environment (GOOGLE_APPLICATION_CREDENTIALS)."
    )
    storage_client: storage.Client | None = None
    default_gcs_bucket_name: str | None = None

    def __init__(self, gcs_bucket_name_override: str = None, **kwargs):
        super().__init__(**kwargs)
        # Use override if provided, otherwise use settings, then None
        self.default_gcs_bucket_name = gcs_bucket_name_override or settings.gcs_bucket_name
        
        try:
            self.storage_client = storage.Client()
            current_desc = self.description # Store original description part
            if self.default_gcs_bucket_name:
                 self.description = f"{current_desc} Default bucket configured: {self.default_gcs_bucket_name}."
            else:
                self.description = f"{current_desc} GCS bucket name needs to be provided at runtime as it was not found in settings."
        except Exception as e:
            print(f"CRITICAL: Failed to initialize Google Cloud Storage client: {e}. GCSUploadTool will not work.")
            self.storage_client = None
            self.description += " ERROR: GCS Client not initialized."

    def _run(self, local_file_path: str, gcs_blob_name: str, gcs_bucket_name: str = None) -> dict:
        """Uploads an image to GCS.

        Args:
            local_file_path: Path to the local image file.
            gcs_blob_name: Desired name for the image blob in GCS (e.g., unique_id.png or images/unique_id.png).
            gcs_bucket_name: Optional. GCS bucket name if not set during initialization.

        Returns:
            A dictionary with the GCS URL of the image or an error.
        """
        bucket_name_to_use = gcs_bucket_name or self.default_gcs_bucket_name
        if not self.storage_client:
            return {"error": "GCS client not initialized. Check credentials and setup.", "gcs_url": None}
        if not bucket_name_to_use:
            return {"error": "GCS bucket name not provided (neither in call nor in config/env).", "gcs_url": None}
        if not isinstance(local_file_path, str) or not os.path.exists(local_file_path):
            return {"error": f"Local file not found or invalid path: {local_file_path}", "gcs_url": None}
        if not isinstance(gcs_blob_name, str) or not gcs_blob_name.strip():
            return {"error": "Invalid GCS blob name provided.", "gcs_url": None}

        try:
            bucket = self.storage_client.bucket(bucket_name_to_use)
            blob = bucket.blob(gcs_blob_name)
            
            # Determine content type from file extension for GCS metadata (basic)
            # More robust would be to use python-magic or get from ImageMetadataTool if available
            ext = os.path.splitext(local_file_path)[1].lower()
            content_type_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            gcs_content_type = content_type_map.get(ext, 'application/octet-stream')

            blob.upload_from_filename(local_file_path, content_type=gcs_content_type)
            # Making the blob public for this example; adjust permissions as needed for your application
            # blob.make_public() 
            # return {"gcs_url": blob.public_url, "error": None} 
            # Using a gs:// URI format is often more standard for internal references
            gs_uri = f"gs://{bucket_name_to_use}/{gcs_blob_name}"
            # Attempt to get a public URL if needed, but permissions might prevent this by default
            # For signed URLs, more complex logic is needed.
            public_url = None
            try:
                 # blob.make_public() # Requires specific GCS permissions; avoid by default
                 public_url = blob.public_url # This might error if not public or if permissions are wrong
            except Exception as e_public_url:
                print(f"Note: Could not retrieve public_url for GCS blob {gs_uri}: {e_public_url}. Blob might not be public.")

            return {"gcs_url": gs_uri, "public_url_available": public_url, "error": None}

        except Exception as e:
            return {"error": f"Error uploading {local_file_path} to GCS gs://{bucket_name_to_use}/{gcs_blob_name}: {e}", "gcs_url": None}

class ImageMetadataTool(BaseTool):
    name: str = "Image File Metadata Extractor"
    description: str = (
        "Extracts metadata (dimensions: width, height; format/MIME type) from a local image file using Pillow. "
        "Input: 'image_file_path' (string: path to the local image file)."
        "Returns a dictionary with 'width', 'height', 'format', 'mime_type', and 'error' (if any)."
    )

    def _run(self, image_file_path: str) -> dict:
        """Extracts metadata from a local image file.

        Args:
            image_file_path: Path to the local image file.

        Returns:
            A dictionary with image metadata or an error.
        """
        if not isinstance(image_file_path, str) or not os.path.exists(image_file_path):
            return {"error": f"Image file not found or invalid path: {image_file_path}"}

        try:
            with Image.open(image_file_path) as img:
                width, height = img.size
                img_format = img.format
                mime_type = Image.MIME.get(img_format.upper()) # Pillow provides common MIME types
            return {
                "width": width,
                "height": height,
                "format": img_format,
                "mime_type": mime_type,
                "error": None
            }
        except Exception as e:
            return {"error": f"Error extracting metadata from image {image_file_path}: {e}"}

# Example Usage:
if __name__ == '__main__':
    # ImageDownloaderTool Example
    print("--- ImageDownloaderTool Example ---")
    downloader = ImageDownloaderTool()
    # A small, publicly accessible image for testing
    test_image_url = "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
    download_result = downloader._run(image_url=test_image_url, output_folder="temp_downloads")
    print(download_result)
    if download_result["local_path"] and os.path.exists(download_result["local_path"]):
        downloaded_file_for_next_steps = download_result["local_path"]
        print(f"Downloaded to: {downloaded_file_for_next_steps}")

        # ImageMetadataTool Example
        print("\n--- ImageMetadataTool Example ---")
        meta_tool = ImageMetadataTool()
        metadata_result = meta_tool._run(downloaded_file_for_next_steps)
        print(metadata_result)

        # GCSUploadTool Example (Illustrative - Requires GCS Setup & Credentials)
        print("\n--- GCSUploadTool Example (Illustrative - requires GCS setup) ---")
        # The GCSUploadTool will now try to get bucket name from .env via config.py first
        # You can still override by passing gcs_bucket_name to _run or __init__
        gcs_uploader = GCSUploadTool() # Initialize, it will try to get bucket_name from config
        print(f"GCSUploader Tool Description: {gcs_uploader.description}")

        if gcs_uploader.storage_client and gcs_uploader.default_gcs_bucket_name:
            test_blob_name = f"test_uploads/{str(uuid.uuid4())}_{os.path.basename(downloaded_file_for_next_steps)}"
            upload_result = gcs_uploader._run(local_file_path=downloaded_file_for_next_steps, gcs_blob_name=test_blob_name)
            print(upload_result)
            if upload_result.get("gcs_url"):
                print(f"Uploaded to GCS: {upload_result['gcs_url']}")
                # Note: blob.public_url might not be available depending on GCS permissions.
                if upload_result.get("public_url_available"):
                    print(f"Public URL (if accessible): {upload_result['public_url_available']}")
        elif not gcs_uploader.storage_client:
            print("Skipping GCSUploadTool example: GCS client not initialized (check credentials).")
        else:
            print(f"Skipping GCSUploadTool example: Default GCS bucket name not configured (GCS_BUCKET_NAME in .env or passed to init). Current default: {gcs_uploader.default_gcs_bucket_name}")

        # Cleanup downloaded file
        if os.path.exists(downloaded_file_for_next_steps):
            os.remove(downloaded_file_for_next_steps)
        if os.path.exists("temp_downloads") and not os.listdir("temp_downloads"):
            try: os.rmdir("temp_downloads")
            except OSError: pass # Ignore if removal fails (e.g. still in use by another process quickly)
    else:
        print(f"Download failed, cannot proceed with further tool examples for {test_image_url}.") 