from typing import Any, Dict, Literal
from aiservice.app.services.base import BaseService, ServiceResult
from pydantic import BaseModel, Field
import os
from urllib.parse import urlparse

class RoutingInput(BaseModel):
    source_identifier: str # e.g., URL, file path, gs:// path
    source_type: str # Changed from Literal to str to accommodate varied outputs from get_source_type
    # Any other relevant input for routing

class RoutingOutput(BaseModel):
    determined_service: str # e.g., 'WebAcquisitionService', 'PDFAcquisitionService'
    determined_source_type: str # Added to pass the specific type like 'gcs_docx', 'pdf', etc.
    # Any other data to pass to the next stage

class RoutingService(BaseService):
    """
    Determines the appropriate acquisition service based on input source.
    Replaces the V2.4 crew_router agent for deterministic routing.
    """

    KNOWN_FILE_EXTENSIONS = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.doc': 'docx', # Treat .doc as .docx for acquisition
        '.txt': 'txt',
        '.md': 'md',
        # Add more common types as needed, e.g., images, audio, if they have direct acquisition paths
        # '.png': 'image', '.jpg': 'image', '.jpeg': 'image', 
    }
    
    UNSUPPORTED_TYPE = 'unsupported'
    URL_TYPE = 'url'
    GCS_PREFIX = 'gs://'

    @staticmethod
    def is_url(identifier: str) -> bool:
        """Checks if the identifier is a URL (http, https, ftp)."""
        if not identifier:
            return False
        try:
            result = urlparse(identifier)
            # Added ftp, consider if other schemes are needed or if it should be stricter (e.g. only http/https for WebAcq)
            return result.scheme in ['http', 'https', 'ftp'] and bool(result.netloc)
        except ValueError:
            return False

    @staticmethod
    def get_source_type(identifier: str) -> str:
        """
        Determines the source type from an identifier (URL, GCS path, or local file path).
        More robustly distinguishes URLs, GCS paths, and identifies common file extensions.
        """
        if not identifier:
            return RoutingService.UNSUPPORTED_TYPE

        identifier_lower = identifier.lower().strip()

        if identifier_lower.startswith(RoutingService.GCS_PREFIX):
            try:
                # Extract path part from gs://bucket/path/to/file.ext
                parsed_gcs_url = urlparse(identifier_lower) # Use urlparse for robustness
                gcs_path = parsed_gcs_url.path
                if gcs_path.startswith('/'): # urlparse.path might start with /
                    gcs_path = gcs_path[1:]
                
                _, ext = os.path.splitext(gcs_path) # Get extension from the path part
                if ext in RoutingService.KNOWN_FILE_EXTENSIONS:
                    return f"gcs_{RoutingService.KNOWN_FILE_EXTENSIONS[ext]}" # e.g., gcs_pdf
                elif ext: # If there's an extension but it's not in our known list
                    return f"gcs_file_ext_{ext.replace('.', '')}" # e.g. gcs_file_ext_zip
                else:
                    # If it's a GCS path with no discernible extension, route to generic file handler
                    return "gcs_generic_file" 
            except Exception:
                 # Problem parsing GCS path or extracting extension
                return f"gcs_{RoutingService.UNSUPPORTED_TYPE}"

        if RoutingService.is_url(identifier_lower):
            # Further checks for URL pointing to a specific file type (e.g. PDF)
            # will be handled by WebAcquisitionService or Orchestrator.
            # For now, RoutingService identifies it as a generic URL.
            # MODIFIED: Check for .pdf extension in URL path
            try:
                parsed_url = urlparse(identifier_lower)
                url_path = parsed_url.path
                _, ext = os.path.splitext(url_path.lower()) # Get extension from the path part
                if ext in RoutingService.KNOWN_FILE_EXTENSIONS and ext == '.pdf': # Specifically check for PDF
                    # If it's a URL pointing to a PDF file
                    return RoutingService.KNOWN_FILE_EXTENSIONS[ext] # Should return 'pdf'
            except Exception:
                # Problem parsing URL or extracting extension, fall through to generic URL
                pass # Ensure this doesn't accidentally suppress other logic
            return RoutingService.URL_TYPE

        # If not a GCS path or URL, assume it's a local file path
        try:
            # Check if it's a valid-looking file path that exists (optional, might be too strict for routing)
            # if not os.path.exists(identifier) and not os.path.isfile(identifier): # os.path.isfile implies exists
            #    # This check might be too aggressive if the file path is relative and CWD isn't what's expected,
            #    # or if the file is created later in the pipeline.
            #    # For routing, primarily rely on extension for now if not a URL.
            #    pass

            _, ext = os.path.splitext(identifier_lower)
            if ext in RoutingService.KNOWN_FILE_EXTENSIONS:
                return RoutingService.KNOWN_FILE_EXTENSIONS[ext]
            else:
                # Could add more sophisticated file type detection here if needed (e.g., python-magic)
                # For now, if extension is not known, mark as unsupported for specific acquisition.
                # The FileAcquisitionService might still attempt to process it as a generic binary/text if routed there.
                if ext: # If there's an extension but it's not in our known list
                    return f"file_ext_{ext.replace('.', '')}" # e.g. file_ext_zip, file_ext_csv
                return RoutingService.UNSUPPORTED_TYPE # No extension or unknown
        except Exception:
            # Any error during path processing might indicate an invalid path
            return RoutingService.UNSUPPORTED_TYPE
            
    async def execute(self, routing_input: RoutingInput) -> ServiceResult[RoutingOutput]:
        """
        Determines the target service based on source_identifier.
        Relies on the improved get_source_type static method.
        """
        if not routing_input or not routing_input.source_identifier:
            return ServiceResult.failure(error_message="Missing routing_input or source_identifier for routing.")

        determined_source_type = RoutingService.get_source_type(routing_input.source_identifier)
        target_service_name: str = ""

        try:
            if determined_source_type == RoutingService.URL_TYPE:
                target_service_name = "CorrectWebAcquisitionService"
            elif determined_source_type == 'pdf' or determined_source_type == 'gcs_pdf':
                target_service_name = "PDFAcquisitionService"
            elif determined_source_type in ['docx', 'txt', 'md'] or \
                 determined_source_type.startswith('file_ext_') or \
                 determined_source_type == 'gcs_docx' or \
                 determined_source_type == 'gcs_txt' or \
                 determined_source_type == 'gcs_md' or \
                 determined_source_type.startswith('gcs_file_ext_') or \
                 determined_source_type == 'gcs_generic_file':
                # Route all known text-based files, other files with extensions,
                # and GCS equivalents (including generic GCS files) to FileAcquisitionService
                target_service_name = "FileAcquisitionService"
            # Add more specific routing based on determined_source_type if other services are added
            # For example, if there was a dedicated ImageAcquisitionService for local image files:
            # elif determined_source_type == 'image':
            # target_service_name = "ImageAcquisitionService"
            else: # Handles UNSUPPORTED_TYPE and gcs_unsupported
                return ServiceResult.failure(
                    error_message=f"Unsupported or unrecognized source type: '{determined_source_type}' for identifier: {routing_input.source_identifier}"
                )

            if not target_service_name: # Should be caught by the else above, but as a safeguard
                 return ServiceResult.failure(error_message=f"Could not determine service for: {routing_input.source_identifier} (Type: {determined_source_type})")

            output = RoutingOutput(determined_service=target_service_name, determined_source_type=determined_source_type)
            return ServiceResult.success(data=output)

        except Exception as e:
            return ServiceResult.failure(error_message=f"Error during routing: {str(e)}", error_details=str(e)) 