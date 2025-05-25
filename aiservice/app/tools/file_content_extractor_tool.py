# File: aiservice/app/tools/file_content_extractor_tool.py
"""Tool to extract content from various local file types."""

import io
import fitz  # PyMuPDF
import docx
import mistune # For Markdown
import locale  # For text decoding fallback
import os
import magic # For MIME type detection
import re # For markdown image regex
import ftfy # Added for robust text sanitization
import base64 # Ensure base64 is imported

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Type, Any # HttpUrl needed for MD image link validation

from crewai.tools import BaseTool

# --- Pydantic Models for FileContentExtractorTool Output ---
# As per TS-AI-4 & TS-AI-4.5 Development Plan - V1.2, TS-AI-4.2 (Tool Output)

class ExtractedFileImage(BaseModel):
    """Represents an image embedded and extracted directly from a file, with data as Base64."""
    data_base64_string: str # Changed from data_bytes: bytes
    filename_hint: Optional[str] = None
    mime_type_hint: Optional[str] = None # e.g., image/png
    alt_text: Optional[str] = None # Rarely available from file embeds directly, but field exists
    caption: Optional[str] = None # Even rarer from file embeds

class FileContent(BaseModel):
    """Structured output for content extracted from a local file."""
    # Status values based on V1.2 plan for the tool's direct output
    status: str  # Expected: "success", "unsupported_file_type", "parse_error", "password_protected_pdf"
    original_filename: str
    page_title: Optional[str] = None      # From document properties if available
    extracted_text: Optional[str] = None
    # For images embedded directly in the file (e.g., in DOCX, PDF)
    images: Optional[List[ExtractedFileImage]] = None 
    # For image URLs found in Markdown files ![]()
    linked_markdown_images: Optional[List[Dict[str, Optional[str]]]] = None # List of {"url": str, "alt_text": Optional[str]}
    error_message: Optional[str] = None


# --- Tool Input Schema ---
class FileContentExtractorToolInput(BaseModel):
    """Input schema for the FileContentExtractorTool."""
    file_content: bytes = Field(..., description="The byte content of the file.")
    filename: str = Field(..., description="The original name of the file, used for type inference and as a fallback identifier.")
    mime_type: str = Field(..., description="The provided MIME type of the file, used for type dispatch. Can be refined by python-magic.")


# --- FileContentExtractorTool Implementation ---
class FileContentExtractorTool(BaseTool):
    """
    A tool to extract text and image data/references from various file types.
    Supports .txt, .docx, .md, and .pdf files.
    Uses python-magic for robust MIME type detection.
    Output is a FileContent Pydantic model.
    """
    name: str = "File Content Extractor Tool"
    description: str = (
        "Extracts text and image data/references from .txt, .docx, .md, and .pdf files. "
        "Uses MIME type and file extension for dispatch, with python-magic for fallback MIME detection."
    )
    args_schema: Type[BaseModel] = FileContentExtractorToolInput

    def _remove_null_bytes(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        return text.replace('\x00', '')

    def _sanitize_for_utf8(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        # Remove null bytes first, as they can interfere with other cleaning
        text_no_nulls = self._remove_null_bytes(text)
        if text_no_nulls is None: # Should not happen if input wasn't None, but defensive
            return None
        
        cleaned_text = text_no_nulls
        try:
            # ftfy can fix many common encoding issues and normalize Unicode
            cleaned_text = ftfy.fix_text(text_no_nulls)
        except Exception:
            # If ftfy fails (e.g., on severely mangled binary-like strings), 
            # proceed with byte-level encode/decode sanitization on the no_nulls version.
            pass # cleaned_text remains text_no_nulls

        # Final pass: ensure it's valid UTF-8 by encoding and decoding with error replacement
        return cleaned_text.encode('utf-8', 'replace').decode('utf-8')

    def _run(self, file_content: bytes, filename: str, mime_type: str) -> FileContent:
        """The main execution method for the tool."""
        
        file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
        normalized_mime_type = mime_type.lower().strip() if mime_type else ''

        # 1. MIME Type Inference using python-magic (TS-AI-4.2 V1.2, Step 2.a)
        unreliable_mime_types = {'', 'application/octet-stream', 'application/unknown', 'binary/octet-stream'}
        if normalized_mime_type in unreliable_mime_types:
            try:
                inferred_mime_type = magic.from_buffer(file_content, mime=True)
                if inferred_mime_type and inferred_mime_type.lower().strip() not in unreliable_mime_types:
                    normalized_mime_type = inferred_mime_type.lower().strip()
            except ImportError: # python-magic not available
                pass # Proceed with original/extension
            except magic.MagicException: # libmagic issue or other magic error
                pass # Proceed with original/extension
            except Exception: # Catch any other unexpected error from magic
                pass # Proceed with original/extension

        # 2. File Type Dispatcher Logic (TS-AI-4.2 V1.2, Step 2.b)
        try:
            if normalized_mime_type == 'text/plain' or (not normalized_mime_type and file_extension == 'txt'):
                return self._parse_txt(file_content, filename)
            elif normalized_mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or \
                 (not normalized_mime_type and file_extension == 'docx'):
                return self._parse_docx(file_content, filename)
            elif normalized_mime_type == 'text/markdown' or \
                 (not normalized_mime_type and file_extension == 'md'):
                return self._parse_md(file_content, filename)
            elif normalized_mime_type == 'application/pdf' or \
                 (not normalized_mime_type and file_extension == 'pdf'):
                return self._parse_pdf(file_content, filename)
            else:
                error_msg = f"Unsupported file type. Original MIME: '{mime_type}', Ext: '{file_extension}', Processed MIME: '{normalized_mime_type}'"
                return FileContent(status="unsupported_file_type", original_filename=filename, error_message=error_msg)
        except Exception as e:
            return FileContent(status="parse_error", original_filename=filename, error_message=f"An unexpected error occurred during file processing: {str(e)}")

    # 3. Plain Text Parsing (TS-AI-4.2 V1.2, Step 2.c)
    def _parse_txt(self, file_content: bytes, filename: str) -> FileContent:
        try:
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = file_content.decode(locale.getpreferredencoding(do_setlocale=True))
            except (UnicodeDecodeError, TypeError, locale.Error):
                try:
                    text = file_content.decode('latin-1')
                except UnicodeDecodeError as e_latin:
                    return FileContent(status="parse_error", original_filename=filename, error_message=f"Could not decode .txt file with UTF-8, preferred system encoding, or Latin-1: {str(e_latin)}")
        return FileContent(status="success", original_filename=filename, extracted_text=text)

    # 4. DOCX Parsing (TS-AI-4.2 V1.2, Step 2.d)
    def _parse_docx(self, file_content: bytes, filename: str) -> FileContent:
        try:
            doc = docx.Document(io.BytesIO(file_content))
            text_parts = [p.text for p in doc.paragraphs if p.text]
            extracted_text = "\n\n".join(text_parts).strip()
            
            page_title = doc.core_properties.title if doc.core_properties.title else None
            
            images_data: List[ExtractedFileImage] = []
            for rel_id, rel in doc.part.rels.items():
                if "image" in rel.target_ref:
                    try:
                        image_part = rel.target_part
                        image_bytes = image_part.blob
                        image_filename_hint = os.path.basename(image_part.partname)
                        # Python-docx doesn't directly give alt text for images in general content easily.
                        # Alt text for docx images is complex (drawingml, vml, etc.) and often not straightforwardly available.
                        images_data.append(ExtractedFileImage(
                            data_base64_string=base64.b64encode(image_bytes).decode('ascii'),
                            filename_hint=image_filename_hint,
                            mime_type_hint=image_part.content_type
                        ))
                    except Exception: # Skip if a particular image extraction fails
                        continue 
            return FileContent(
                status="success", original_filename=filename, extracted_text=extracted_text or None, 
                page_title=page_title, images=images_data if images_data else None
            )
        except Exception as e:
            return FileContent(status="parse_error", original_filename=filename, error_message=f"Error parsing .docx file: {str(e)}")

    # 5. Markdown Parsing (TS-AI-4.2 V1.2, Step 2.e)
    def _parse_md(self, file_content: bytes, filename: str) -> FileContent:
        try:
            raw_md_text = file_content.decode('utf-8')
            html_output = mistune.html(raw_md_text)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_output, 'html.parser')
            extracted_text = soup.get_text(separator="\n", strip=True)

            # Regex for ![alt_text](url) or ![alt_text](url "title")
            markdown_image_regex = r"!\[([^\]]*)\]\(([^\s\)\"]+)(?:\s*\"(.*)\")?\)"
            linked_images: List[Dict[str, Optional[str]]] = []
            for match in re.finditer(markdown_image_regex, raw_md_text):
                alt = match.group(1).strip() if match.group(1) else None
                url = match.group(2).strip()
                if url.startswith("http://") or url.startswith("https://"):
                    try:
                        HttpUrl(url) # Validate URL
                        linked_images.append({"url": url, "alt_text": alt})
                    except ValueError: # Pydantic validation failed
                        pass # Skip invalid HttpUrl
            
            return FileContent(
                status="success", original_filename=filename, extracted_text=extracted_text or None,
                linked_markdown_images=linked_images if linked_images else None,
                page_title=None # MD files don't have standard metadata title
            )
        except Exception as e:
            return FileContent(status="parse_error", original_filename=filename, error_message=f"Error parsing .md file: {str(e)}")

    # 6. PDF Parsing (TS-AI-4.2 V1.2, Step 2.f)
    def _parse_pdf(self, file_content: bytes, filename: str) -> FileContent:
        page_title_final: Optional[str] = None
        images_data: List[ExtractedFileImage] = []
        extracted_text_final: Optional[str] = None
        pdf_error_message: Optional[str] = None
        overall_status = "success"
        doc = None # Initialize doc

        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            if doc.is_encrypted and doc.needs_pass:
                if not doc.authenticate(""):
                    # doc.close() # doc might not be closable if auth failed early
                    return FileContent(status="password_protected_pdf", original_filename=filename, error_message="PDF is password protected.")
            try:
                text_parts = []
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    page_text = page.get_text("text", sort=True)
                    if page_text: text_parts.append(page_text)
                raw_extracted_text = "\n\n".join(text_parts).strip()
                extracted_text_final = self._sanitize_for_utf8(raw_extracted_text) if raw_extracted_text else None
            except Exception as text_e:
                extracted_text_final = None
                pdf_error_message = f"Error during PDF text extraction/sanitization: {str(text_e)}"
            
            raw_page_title = doc.metadata.get('title')
            page_title_final = self._sanitize_for_utf8(str(raw_page_title)) if raw_page_title else None
            if not page_title_final and doc.metadata.get('producer'):
                 raw_producer = doc.metadata.get('producer', '')
                 producer_sanitized = self._sanitize_for_utf8(str(raw_producer))
                 page_title_final = f"PDF Document (Producer: {producer_sanitized})"
            elif not page_title_final:
                 page_title_final = self._sanitize_for_utf8(filename)

            # Image Extraction - now storing as Base64 string
            for page_num in range(len(doc)):
                try:
                    image_list = doc.get_page_images(page_num, full=True)
                    for img_info in image_list:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        if base_image and base_image.get("image"):
                            image_byte_content = base_image["image"]
                            # Encode bytes to Base64 string (ASCII)
                            base64_encoded_string = base64.b64encode(image_byte_content).decode('ascii')
                            
                            raw_img_fname = f"page{page_num+1}_img{img_info[1]}.{base_image['ext']}"
                            filename_hint_utf8_safe = self._sanitize_for_utf8(raw_img_fname)
                            
                            images_data.append(ExtractedFileImage(
                                data_base64_string=base64_encoded_string, # Store base64 string
                                filename_hint=filename_hint_utf8_safe,
                                mime_type_hint=f"image/{base_image['ext']}"
                            ))
                except Exception: continue 
            
            if doc: doc.close()

            final_error_message = pdf_error_message
            if extracted_text_final is None and not pdf_error_message and text_parts:
                final_error_message = (final_error_message + "; " if final_error_message else "") + "PDF text was present but could not be reliably decoded/sanitized."
                overall_status = "parse_error"
            elif extracted_text_final is None and not images_data and not page_title_final:
                overall_status = "parse_error"
                final_error_message = (final_error_message + "; " if final_error_message else "") + "Failed to extract any meaningful content from PDF."

            return FileContent(
                status=overall_status, original_filename=filename, 
                extracted_text=extracted_text_final,
                page_title=page_title_final, 
                images=images_data if images_data else None,
                linked_markdown_images= None, # Ensure this is explicitly set if not handled elsewhere for PDF
                error_message=final_error_message
            )
        except Exception as e:
            if doc: doc.close() # Ensure doc is closed even if fitz.open succeeded but later part failed
            err_msg = f"Error parsing .pdf file: {str(e)}"
            if "cannot open broken document" in str(e).lower():
                 err_msg = f"Cannot open broken PDF file: {str(e)}"
            return FileContent(status="parse_error", original_filename=filename, error_message=self._sanitize_for_utf8(err_msg))

# Note: __main__ block for testing would go here. It's omitted for brevity in this step,
# but should be added based on previous versions for direct tool testing. 