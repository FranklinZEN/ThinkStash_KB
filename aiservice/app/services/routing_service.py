from typing import Any, Dict, Literal
from aiservice.app.services.base import BaseService, ServiceResult
from pydantic import BaseModel

class RoutingInput(BaseModel):
    source_identifier: str # e.g., URL, file path
    source_type: Literal['url', 'pdf', 'docx', 'txt', 'md', 'generic_file'] # Extend as needed
    # Any other relevant input for routing

class RoutingOutput(BaseModel):
    determined_service: str # e.g., 'WebAcquisitionService', 'PDFAcquisitionService'
    # Any other data to pass to the next stage

class RoutingService(BaseService):
    """
    Determines the appropriate acquisition service based on input source.
    Replaces the V2.4 crew_router agent for deterministic routing.
    """

    async def execute(self, routing_input: RoutingInput) -> ServiceResult[RoutingOutput]:
        """
        Determines the target service based on source_identifier and source_type.
        """
        # Basic routing logic based on source_type and identifier patterns
        # This will be refined based on logic from V2.4's orchestration_agent_logic.execute_routing()
        # or new deterministic rules.

        if not routing_input or not routing_input.source_identifier or not routing_input.source_type:
            return ServiceResult.failure(error_message="Missing source_identifier or source_type for routing.")

        target_service_name: str = ""
        source_type = routing_input.source_type
        identifier = routing_input.source_identifier.lower()

        try:
            if source_type == 'url':
                # Add more specific URL pattern matching if needed (e.g., for specific domains)
                target_service_name = "WebAcquisitionService"
            elif source_type == 'pdf' or identifier.endswith('.pdf'):
                target_service_name = "PDFAcquisitionService"
            elif source_type == 'docx' or identifier.endswith(('.doc', '.docx')):
                target_service_name = "FileAcquisitionService" # Assuming a generic file service handles DOCX
            elif source_type == 'txt' or identifier.endswith('.txt'):
                target_service_name = "FileAcquisitionService"
            elif source_type == 'md' or identifier.endswith('.md'):
                target_service_name = "FileAcquisitionService"
            elif source_type == 'generic_file':
                 # Potentially more logic here to determine actual file type if not explicit
                target_service_name = "FileAcquisitionService"
            else:
                # Fallback or error for unknown types
                return ServiceResult.failure(error_message=f"Unsupported source_type: {source_type} or identifier: {identifier}")

            if not target_service_name:
                 return ServiceResult.failure(error_message=f"Could not determine service for: {identifier} ({source_type})")

            output = RoutingOutput(determined_service=target_service_name)
            return ServiceResult.success(data=output)

        except Exception as e:
            return ServiceResult.failure(error_message=f"Error during routing: {str(e)}", error_details=str(e)) 