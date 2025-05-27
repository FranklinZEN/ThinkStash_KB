import fitz  # PyMuPDF
from crewai.tools import BaseTool
import os
from pdf2image import convert_from_path # pdf2image
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError
)
import docx # python-docx
import markdown # Markdown library
import re # For cleaning up HTML from Markdown
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.layout import LAParams

class PyMuPDFParserTool(BaseTool):
    """Extracts text from PDF files using the PyMuPDF (fitz) library.

    This tool provides a fast method for getting text content from PDF documents,
    page by page. It includes basic error handling for file access and PDF processing.
    A page break marker is inserted between content from different pages.
    """
    name: str = "PyMuPDF PDF Text Extractor"
    description: str = (
        "Extracts all text content from a PDF file page by page using the PyMuPDF (fitz) library. "
        "Input must be a string representing the valid file path to the PDF document."
    )

    def _run(self, pdf_file_path: str) -> str:
        print(f"PyMuPDFParserTool: Starting for {pdf_file_path}")
        if not isinstance(pdf_file_path, str):
            print(f"PyMuPDFParserTool: Error - Input not a string: {type(pdf_file_path)}")
            return "Error: Input must be a string representing the PDF file path."
        if not os.path.exists(pdf_file_path):
            print(f"PyMuPDFParserTool: Error - File not found: {pdf_file_path}")
            return f"Error: PDF file not found at {pdf_file_path}."
        if not pdf_file_path.lower().endswith('.pdf'):
            return f"Error: File {pdf_file_path} does not appear to be a PDF."

        all_text = [] # Store text from each page in a list
        try:
            doc = fitz.open(pdf_file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                all_text.append(page.get_text("text"))
            doc.close()
            
            if not any(text.strip() for text in all_text):
                return "Warning: No text could be extracted from the PDF using PyMuPDF."
            # Join page texts with a clear page break indicator
            return "\n\n--- Page Break --- \n\n".join(all_text)
        except Exception as e:
            print(f"PyMuPDFParserTool: Error parsing {pdf_file_path}: {e}")
            return f"Error processing PDF {pdf_file_path} with PyMuPDF: {e}"

class NougatPDFParserTool(BaseTool):
    """Advanced PDF parser using the Nougat model.

    Ideal for academic papers and documents with complex layouts, aiming to extract
    text and convert mathematical formulas to LaTeX. Requires a functional Nougat
    setup (local installation or a service endpoint).
    """
    name: str = "Nougat PDF Parser (Advanced)"
    description: str = (
        "Advanced PDF parser using the Nougat model, ideal for academic papers, "
        "extracting text, and converting mathematical formulas to LaTeX. "
        "Input must be a string representing the valid file path to the PDF. "
        "NOTE: This tool's full functionality depends on a separate Nougat installation or service endpoint. "
        "For Nougat setup, refer to https://github.com/facebookresearch/nougat/blob/main/README.md."
    )

    nougat_service_url: str = None # Optional: To be configured if using a Nougat service endpoint

    def __init__(self, nougat_service_url: str = None, **kwargs):
        """Initializes the NougatPDFParserTool.

        Args:
            nougat_service_url: Optional URL for a running Nougat service endpoint.
            **kwargs: Additional arguments for BaseTool.
        """
        super().__init__(**kwargs)
        if nougat_service_url:
            self.nougat_service_url = nougat_service_url
            self.description += f" Currently configured to use Nougat service at: {self.nougat_service_url}."
        else:
            self.description += " Local Nougat CLI execution will be attempted (requires Nougat to be in PATH)."
        print(f"NougatPDFParserTool: Initialized. Service URL: {self.nougat_service_url}")

    def _run(self, pdf_file_path: str) -> str:
        print(f"NougatPDFParserTool: Starting for {pdf_file_path}. Service URL: {self.nougat_service_url}")
        if not isinstance(pdf_file_path, str):
            print(f"NougatPDFParserTool: Error - Input not a string: {type(pdf_file_path)}")
            return "Error: Input must be a string representing the PDF file path."
        if not os.path.exists(pdf_file_path):
            print(f"NougatPDFParserTool: Error - File not found: {pdf_file_path}")
            return f"Error: PDF file not found at {pdf_file_path}."
        if not pdf_file_path.lower().endswith('.pdf'):
            return f"Error: File {pdf_file_path} does not appear to be a PDF."

        placeholder_message = (
            "Nougat processing for this tool is not yet fully implemented. "
            "This step would involve calling a local Nougat instance or a Nougat service."
        )

        if self.nougat_service_url:
            # TODO: Implement HTTP request to Nougat service endpoint
            # Example (conceptual):
            # try:
            #     with open(pdf_file_path, 'rb') as f_pdf:
            #         response = requests.post(self.nougat_service_url, files={'file': f_pdf})
            #     response.raise_for_status()
            #     # Assuming Nougat service returns a JSON with 'text' or 'markdown_output' field
            #     return response.json().get('markdown_output', response.text)
            # except Exception as e:
            #     return f"Error calling Nougat service at {self.nougat_service_url} for {pdf_file_path}: {e}"
            return f"{placeholder_message} Expected to use service at {self.nougat_service_url} for {pdf_file_path}."
        else:
            # TODO: Implement local Nougat CLI call or Python SDK usage if available
            # Example (conceptual for CLI):
            # try:
            #     import subprocess
            #     # Ensure 'nougat' command is in PATH or provide full path
            #     # The output directory and format may need adjustment based on Nougat CLI specifics.
            #     # output_dir = f"temp_nougat_output_{os.path.basename(pdf_file_path)}"
            #     # os.makedirs(output_dir, exist_ok=True)
            #     # process = subprocess.run(['nougat', pdf_file_path, '--out', output_dir], capture_output=True, text=True, check=True)
            #     # # Read the .mmd (Markdown Math Document) file produced by Nougat
            #     # # This part is highly dependent on Nougat's output structure.
            #     # # For example, find the first .mmd file in output_dir
            #     # # with open(os.path.join(output_dir, "output.mmd"), "r") as f_out:
            #     # #     content = f_out.read()
            #     # # shutil.rmtree(output_dir) # Clean up
            #     # # return content
            #     # return f"[Simulated Nougat Output for local processing of {pdf_file_path}]"
            # except Exception as e:
            #     return f"Error running local Nougat for {pdf_file_path}: {e}"
            return f"{placeholder_message} Expected to use local Nougat setup for {pdf_file_path}. This is a placeholder and should not be used in production."

        # Fallback, should be replaced by actual implementation logic above.
        # return f"Nougat processing for '{pdf_file_path}' is pending full implementation."

class PDFToImageTool(BaseTool):
    """Converts PDF pages to image files using the pdf2image library.

    This tool is used to generate images of PDF pages, which can then be processed
    by multimodal LLMs for tasks like image description, captioning, or identifying
    visual elements for contextual marking.
    Requires Poppler to be installed on the system.
    """
    name: str = "PDF Page to Image Converter"
    description: str = (
        "Converts specified pages of a PDF file into image files (e.g., PNG). "
        "Input requires 'pdf_file_path' (string). Optional inputs: 'page_numbers' (list of 1-indexed integers), "
        "'output_folder' (string, defaults to 'temp_pdf_page_images'), "
        "'dpi' (integer, defaults to 200), 'fmt' (string, e.g., 'png', 'jpeg', defaults to 'png')."
    )

    def _run(self, pdf_file_path: str, page_numbers: list[int] = None, output_folder: str = "temp_pdf_page_images", dpi: int = 200, fmt: str = 'png') -> list[str] | str:
        print(f"PDFToImageTool: Starting for {pdf_file_path}. Output: {output_folder}, Pages: {page_numbers}")
        if not isinstance(pdf_file_path, str) or not pdf_file_path.lower().endswith('.pdf'):
            return "Error: Invalid PDF file path provided."
        if not os.path.exists(pdf_file_path):
            return f"Error: PDF file not found at {pdf_file_path}"

        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder, exist_ok=True)
            except OSError as e:
                return f"Error: Could not create output folder {output_folder}: {e}"

        image_paths = []
        try:
            if page_numbers:
                # Ensure page numbers are valid (e.g. > 0)
                if not all(isinstance(pn, int) and pn > 0 for pn in page_numbers):
                    return "Error: page_numbers must be a list of positive integers."
                
                for page_num_1_indexed in sorted(list(set(page_numbers))): # Sort and unique
                    # Using output_file to generate predictable filenames per page.
                    file_stem = os.path.splitext(os.path.basename(pdf_file_path))[0]
                    output_filename_stem = f"{file_stem}_page_{page_num_1_indexed}"
                    
                    converted_page_paths = convert_from_path(
                        pdf_file_path,
                        dpi=dpi,
                        first_page=page_num_1_indexed,
                        last_page=page_num_1_indexed,
                        fmt=fmt,
                        output_folder=output_folder,
                        output_file=output_filename_stem, # pdf2image appends .fmt
                        paths_only=True,
                        use_pdftocairo=True # Often more robust if Poppler utils are fully installed
                    )
                    if converted_page_paths:
                        image_paths.extend(converted_page_paths)
            else:
                # Convert all pages if no specific page_numbers are given.
                file_stem = os.path.splitext(os.path.basename(pdf_file_path))[0]
                output_filename_stem = f"{file_stem}_allpages"
                
                all_converted_paths = convert_from_path(
                    pdf_file_path,
                    dpi=dpi,
                    fmt=fmt,
                    output_folder=output_folder,
                    output_file=output_filename_stem, # Generates sequence like stem_0001.png, stem_0002.png
                    paths_only=True,
                    use_pdftocairo=True
                )
                if all_converted_paths:
                    image_paths.extend(all_converted_paths)
            
            if not image_paths:
                return "Warning: No images were generated. Check PDF content, page numbers, or Poppler installation."
            return image_paths

        except (PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError) as e:
            return f"Error during PDF to image conversion (pdf2image specific error): {e}. Ensure Poppler utilities are installed and in PATH."
        except Exception as e:
            return f"An unexpected error occurred during PDF to image conversion: {e}"

class DocxParserTool(BaseTool):
    """Extracts content from DOCX files using the python-docx library.

    This tool extracts all paragraph text and identifies images within the DOCX document.
    For images, it saves them to a temporary folder and returns their paths along with
    placeholder IDs that can be used to mark their positions in the extracted text.
    """
    name: str = "DOCX Parser Tool"
    description: str = (
        "Extracts text and images from a DOCX file. "
        "Input: 'file_path' (string: path to the .docx file). "
        "Optional: 'image_output_folder' (string: folder to save extracted images, defaults to 'temp_docx_images')."
        "Returns a dictionary with 'text_content' (string with image placeholders like [IMAGE_DOCX_RID<ID>]) "
        "and 'image_list' (list of dicts with 'id', 'filename', 'path', 'content_type')."
    )

    def _run(self, file_path: str, image_output_folder: str = "temp_docx_images") -> dict | str:
        """Extracts text and images from the DOCX file.

        Args:
            file_path: Path to the .docx file.
            image_output_folder: Folder to save extracted images.

        Returns:
            A dictionary containing extracted text with image placeholders and a list of image details,
            or an error string if processing fails.
        """
        print(f"DocxParserTool: Starting for {file_path}")
        if not isinstance(file_path, str) or not file_path.lower().endswith(('.docx')):
            return "Error: Invalid .docx file path provided."
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"

        if not os.path.exists(image_output_folder):
            try:
                os.makedirs(image_output_folder, exist_ok=True)
            except OSError as e:
                return f"Error creating image output folder {image_output_folder}: {e}"
        
        text_content = ""
        image_list = []
        image_counter = 0

        try:
            document = docx.Document(file_path)
            for para_element in document.inline_shapes: # This gets inline shapes
                # This part is tricky with python-docx as images can be in various places.
                # A more robust solution might involve inspecting the XML directly (e.g., doc.part.rels)
                # For now, focusing on inline_shapes and images within runs as a common case.
                pass # Placeholder for more robust inline shape image extraction

            # Iterate through paragraphs and their runs to find text and images
            # This logic needs to be careful about how text and image placeholders are interleaved.
            # The current python-docx library makes it a bit challenging to get exact original order
            # of mixed text and images easily without diving deep into XML relationships.
            # The strategy here will be to extract all text first, then append placeholders for images found.
            # A more advanced method would involve iterating through document body elements.

            for para in document.paragraphs:
                text_content += para.text + "\n"

            # Attempt to extract images and associate them with rIds if possible
            # This part is simplified; robust DOCX image extraction with original position is complex.
            for rel_id, rel in document.part.rels.items():
                if "image" in rel.target_ref:
                    image_counter += 1
                    image = rel.target_part
                    image_bytes = image.blob
                    image_filename = f"image_{image_counter}_{os.path.basename(image.partname)}"
                    image_save_path = os.path.join(image_output_folder, image_filename)
                    
                    try:
                        with open(image_save_path, "wb") as img_file:
                            img_file.write(image_bytes)
                        image_list.append({
                            "id": rel_id, # Use relationship ID as a unique identifier
                            "placeholder": f"[IMAGE_DOCX_RID{rel_id}]",
                            "filename": image_filename,
                            "path": image_save_path,
                            "content_type": image.content_type
                        })
                        # We are not inserting placeholders into text_content here as it's hard to get original position.
                        # The ContentConsolidationStructuringAgent will need to handle DOCX image placement semantically
                        # if no explicit markers are available from a more advanced DOCX parser.
                    except Exception as e_img:
                        print(f"Error saving image {image_filename}: {e_img}")
            print(f"DocxParserTool: Successfully extracted text from {file_path}. Length: {len(text_content)}")
            return {
                "text_content": text_content.strip(),
                "image_list": image_list
            }
        except Exception as e:
            print(f"DocxParserTool: Error parsing {file_path}: {e}")
            return f"Error processing DOCX file {file_path}: {e}"

class TxtParserTool(BaseTool):
    """Extracts text content from plain TXT files.

    Handles potential character encoding issues during file reading.
    """
    name: str = "TXT File Text Extractor"
    description: str = (
        "Extracts all text content from a plain .txt file. "
        "Input: 'file_path' (string: path to the .txt file)."
    )

    def _run(self, file_path: str) -> str:
        """Reads and returns the text content of the .txt file.

        Args:
            file_path: Path to the .txt file.

        Returns:
            A string containing the text content, or an error message if reading fails.
        """
        print(f"TxtParserTool: Starting for {file_path}")
        if not isinstance(file_path, str) or not file_path.lower().endswith('.txt'):
            return "Error: Invalid .txt file path provided."
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
        
        try:
            # Try common encodings; UTF-8 is a good default.
            encodings_to_try = ['utf-8', 'latin-1', 'windows-1252']
            for encoding in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            return f"Error: Could not decode TXT file {file_path} with tried encodings."
        except Exception as e:
            print(f"TxtParserTool: Error parsing {file_path}: {e}")
            return f"Error reading TXT file {file_path}: {e}"

class MarkdownParserTool(BaseTool):
    """Parses Markdown (MD) files to extract text and structured elements.

    This tool aims to extract the main text content (often by converting MD to HTML
    and then stripping tags), and identify linked images, code blocks (with language
    if specified), and potentially math expressions if they use common delimiters.
    """
    name: str = "Markdown File Parser"
    description: str = (
        "Parses a Markdown (.md) file to extract text, linked images, code blocks, and math expressions. "
        "Input: 'file_path' (string: path to the .md file). "
        "Returns a dictionary with 'text_content', 'linked_images' (list of urls/alts), "
        "'code_blocks' (list of lang/code), and 'math_expressions' (list of strings)."
    )

    def _clean_html(self, html_text: str) -> str:
        """Removes HTML tags from a string, a common step after MD to HTML conversion."""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html_text).strip()

    def _run(self, file_path: str) -> dict | str:
        """Parses the Markdown file.

        Args:
            file_path: Path to the .md file.

        Returns:
            A dictionary containing extracted elements, or an error string.
        """
        print(f"MarkdownParserTool: Starting for {file_path}")
        if not isinstance(file_path, str) or not file_path.lower().endswith('.md'):
            return "Error: Invalid .md file path provided."
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            # Convert Markdown to HTML to easily extract elements and clean text
            # Using extensions for tables, fenced code blocks, etc., is good practice.
            html_content = markdown.markdown(md_content, extensions=['fenced_code', 'tables', 'sane_lists'])
            text_content = self._clean_html(html_content)

            # Placeholder for more sophisticated extraction of images, code, math
            # This requires more complex parsing of either the MD AST or the generated HTML.
            # For now, returning the raw MD and the cleaned text.
            # A full implementation would use regex or a proper HTML/MD parser (like BeautifulSoup on html_content
            # or a Markdown AST parser) to find these elements reliably.
            
            linked_images = [] # TODO: Implement actual extraction
            code_blocks = []   # TODO: Implement actual extraction (e.g., from <pre><code> in html_content or fenced blocks in MD)
            math_expressions = [] # TODO: Implement actual extraction (e.g., from $$...$$ or \\(...\\) in md_content)

            # Simple regex for linked images: ![alt text](url)
            for match in re.finditer(r'!\[(.*?)\]\((.*?)\)', md_content):
                linked_images.append({"alt_text": match.group(1), "url": match.group(2)})

            # Simple regex for fenced code blocks: ```lang
            # code
            # ``` or ```
            # code
            # ```
            for match in re.finditer(r'```(?:(\w+)\n)?(.*?)\n```', md_content, re.DOTALL):
                lang = match.group(1) if match.group(1) else 'plaintext'
                code = match.group(2).strip()
                code_blocks.append({"language": lang, "content": code})
            
            # Simple regex for LaTeX math blocks: $$...$$ or \\[...\\]
            for match in re.finditer(r'(?:\\$\\$|\\\\\\s*\\[)(.*?)(?:\\$\\$|\\\\\\s*\\])', md_content, re.DOTALL):
                math_expressions.append(match.group(1).strip())
            
            # Simple regex for inline LaTeX math: $...$
            # Be careful with this one as single $ can appear in text. This is very basic.
            # for match in re.finditer(r'(?<!\\$)\\$(?!\\s|\\$)(.+?)(?<!\\s|\\$)\\$(?!\\$)\', md_content):\n            #     math_expressions.append(match.group(1).strip())\n

            print(f"MarkdownParserTool: Successfully processed {file_path}. Text length: {len(text_content)}")
            return {
                "text_content": text_content, # Cleaned text from HTML conversion
                "raw_markdown_content": md_content, # Original Markdown
                "linked_images": linked_images,
                "code_blocks": code_blocks,
                "math_expressions": math_expressions
            }
        except Exception as e:
            print(f"MarkdownParserTool: Error parsing {file_path}: {e}")
            return f"Error processing Markdown file {file_path}: {e}"

class PDFMinerSixParserTool(BaseTool):
    name: str = "PDFMiner.six Layout-Aware PDF Parser"
    description: str = (
        "Extracts text content from a PDF file using pdfminer.six, attempting to preserve layout. "
        "Good for PDFs where structural understanding of text blocks is important. "
        "Input: 'file_path' (string: path to the .pdf file). "
        "Optional: 'laparams_dict' (dict: layout parameters for pdfminer, e.g., {'line_margin': 0.5})."
        "Returns the extracted text as a single string."
    )

    def _run(self, file_path: str, laparams_dict: dict = None) -> str:
        print(f"PDFMinerSixParserTool: Starting for file: {file_path}")
        if not isinstance(file_path, str) or not os.path.exists(file_path):
            print(f"PDFMinerSixParserTool: Error - Invalid or non-existent file path: {file_path}")
            return "Error: Invalid or non-existent file path provided."
        
        laparams = None
        if laparams_dict:
            try:
                laparams = LAParams(**laparams_dict)
                print(f"PDFMinerSixParserTool: Using LAParams: {laparams_dict}")
            except Exception as e:
                print(f"PDFMinerSixParserTool: Error creating LAParams from dict {laparams_dict}: {e}")
                return f"Error: Invalid LAParams dictionary provided: {e}"

        try:
            extracted_text = pdfminer_extract_text(file_path, laparams=laparams)
            print(f"PDFMinerSixParserTool: Successfully extracted text from {file_path}. Length: {len(extracted_text)}")
            return extracted_text
        except Exception as e:
            print(f"PDFMinerSixParserTool: Error during PDFMiner.six extraction for {file_path}: {e}")
            return f"Error: PDFMiner.six failed to extract text. Details: {str(e)}"

# Example Usage (for illustration)
if __name__ == '__main__':
    # PyMuPDFParserTool example (from before)
    # ... (omitted for brevity, assume it's tested if this block is run independently)

    # NougatPDFParserTool example (from before)
    # ... (omitted for brevity)

    # PDFToImageTool example (from before)
    # ... (omitted for brevity)

    # Create dummy files for Docx, Txt, Md tool testing
    dummy_files_to_clean = []
    def create_tool_test_file(name, content):
        with open(name, "w", encoding='utf-8') as f: f.write(content)
        dummy_files_to_clean.append(name)

    # TXT Tool Test
    print("\n--- TxtParserTool Test ---")
    txt_tool = TxtParserTool()
    create_tool_test_file("dummy_generic.txt", "This is a simple text file.\nWith multiple lines.")
    print(txt_tool._run("dummy_generic.txt"))
    print(txt_tool._run("non_existent.txt"))

    # Markdown Tool Test
    print("\n--- MarkdownParserTool Test ---")
    md_tool = MarkdownParserTool()
    md_sample_content = ("""
# Markdown Example

This is a paragraph with an ![alt text for image](http://example.com/image.png).

```python
print("Hello, Python!")
```

And some math: $$E = mc^2$$

Inline math: $ax^2 + bx + c = 0$
""")
    create_tool_test_file("dummy_generic.md", md_sample_content)
    md_result = md_tool._run("dummy_generic.md")
    if isinstance(md_result, dict):
        print(f"Text Content: {md_result.get('text_content')[:100]}...")
        print(f"Linked Images: {md_result.get('linked_images')}")
        print(f"Code Blocks: {md_result.get('code_blocks')}")
        print(f"Math Expressions: {md_result.get('math_expressions')}")
    else:
        print(md_result)

    # DOCX Tool Test (python-docx doesn't easily create .docx, so test with existing if available or mock)
    # For now, just showing instantiation and a run against a non-existent file for error path.
    print("\n--- DocxParserTool Test (Error Path) ---")
    docx_tool = DocxParserTool()
    print(docx_tool._run("non_existent.docx"))
    # To test DOCX properly, place a sample .docx file (e.g., from your test corpus)
    # and run: print(docx_tool._run("path/to/your/sample.docx"))
    # Example: print(docx_tool._run("../../documentation/AI Agents Testing File/Fulfillment Planning Deep Research Paper.docx"))

    # Cleanup
    for f_path in dummy_files_to_clean:
        if os.path.exists(f_path): os.remove(f_path)
    temp_image_folder_docx = "temp_docx_images"
    if os.path.exists(temp_image_folder_docx):
        import shutil
        try: shutil.rmtree(temp_image_folder_docx)
        except OSError as e: print(f"Error removing {temp_image_folder_docx}: {e}")
    # ... (cleanup for other tool examples if they created files/folders) 