from typing import Any, Dict, Literal
from aiservice.app.services.base import BaseService, ServiceResult
from pydantic import BaseModel
import os
from urllib.parse import urlparse

class RoutingInput(BaseModel):
    source_identifier: str # e.g., URL, file path
    source_type: str # Changed from Literal to str to accommodate varied outputs from get_source_type
    # Any other relevant input for routing

class RoutingOutput(BaseModel):
    determined_service: str # e.g., 'WebAcquisitionService', 'PDFAcquisitionService'
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

    @staticmethod
    def is_url(identifier: str) -> bool:
        """Checks if the identifier is a URL."""
        if not identifier:
            return False
        try:
            result = urlparse(identifier)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    @staticmethod
    def get_source_type(identifier: str) -> str:
        """
        Determines the source type from an identifier (URL or file path).
        More robustly distinguishes URLs and identifies common file extensions.
        """
        if not identifier:
            return RoutingService.UNSUPPORTED_TYPE

        identifier_lower = identifier.lower().strip()

        if RoutingService.is_url(identifier_lower):
            # Further checks for URL pointing to a specific file type (e.g. PDF)
            # will be handled by WebAcquisitionService or Orchestrator.
            # For now, RoutingService identifies it as a generic URL.
            # We could add a quick check here for .pdf, .docx etc. in URL path if desired,
            # but Content-Type header check is more reliable (done later).
            # Example quick check (optional, can be less reliable):
            # parsed_url = urlparse(identifier_lower)
            # path_lower = parsed_url.path.lower()
            # for ext, type_name in RoutingService.KNOWN_FILE_EXTENSIONS.items():
            #     if path_lower.endswith(ext):
            #         # Could return type_name here, or a special 'url_file' type
            #         return type_name # Or 'url_pdf', 'url_docx'
            return RoutingService.URL_TYPE

        # If not a URL, assume it's a file path
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
                target_service_name = "WebAcquisitionService"
            elif determined_source_type == 'pdf':
                target_service_name = "PDFAcquisitionService"
            elif determined_source_type in ['docx', 'txt', 'md'] or determined_source_type.startswith('file_ext_'):
                # Route all known text-based files and other files with extensions to FileAcquisitionService
                target_service_name = "FileAcquisitionService"
            # Add more specific routing based on determined_source_type if other services are added
            # For example, if there was a dedicated ImageAcquisitionService for local image files:
            # elif determined_source_type == 'image':
            # target_service_name = "ImageAcquisitionService"
            else: # Handles UNSUPPORTED_TYPE
                return ServiceResult.failure(
                    error_message=f"Unsupported or unrecognized source type: '{determined_source_type}' for identifier: {routing_input.source_identifier}"
                )

            if not target_service_name: # Should be caught by the else above, but as a safeguard
                 return ServiceResult.failure(error_message=f"Could not determine service for: {routing_input.source_identifier} (Type: {determined_source_type})")

            output = RoutingOutput(determined_service=target_service_name)
            return ServiceResult.success(data=output)

        except Exception as e:
            return ServiceResult.failure(error_message=f"Error during routing: {str(e)}", error_details=str(e)) 