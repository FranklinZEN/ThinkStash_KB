from abc import ABC, abstractmethod
from typing import Any, Literal, Optional, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T') # For generic result data

class ServiceResult(BaseModel, Generic[T]):
    status: Literal['success', 'error'] = Field(..., description="The status of the service operation.")
    data: Optional[T] = Field(None, description="The data returned by the service on success.")
    error_message: Optional[str] = Field(None, description="A descriptive error message if the operation failed.")
    error_details: Optional[Any] = Field(None, description="Additional details about the error.")

    @classmethod
    def success(cls, data: Optional[T] = None) -> 'ServiceResult[T]':
        return cls(status='success', data=data)

    @classmethod
    def failure(cls, error_message: str, error_details: Optional[Any] = None) -> 'ServiceResult[T]':
        return cls(status='error', error_message=error_message, error_details=error_details)

    def is_success(self) -> bool:
        """Check if the service operation was successful."""
        return self.status == 'success'

class BaseService(ABC):
    """
    Abstract base class for all services in the Thinkstash AI Service.
    Services are responsible for specific tasks within the processing pipeline.
    """

    def __init__(self, settings: Optional[Any] = None): # Placeholder for global settings
        self.settings = settings

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> ServiceResult[Any]:
        """
        Execute the core logic of the service.
        This method must be implemented by subclasses.
        """
        pass

    # Common utility methods for services could be added here later if needed. 