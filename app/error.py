from typing import Any, Dict, Optional
from fastapi import status
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    status: str = "error"
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class DispatcherException(Exception):
    """
    Base domain exception for the APEx Dispatch API.
    """

    http_status: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "APEX_ERROR"
    message: str = "An error occurred."
    details: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        http_status: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if message:
            self.message = message
        if error_code:
            self.error_code = error_code
        if http_status:
            self.http_status = http_status
        if details:
            self.details = details

    def __str__(self):
        return f"{self.error_code}: {self.message}"


class AuthException(DispatcherException):
    def __init__(
        self,
        http_status: Optional[int] = status.HTTP_401_UNAUTHORIZED,
        message: Optional[Dict[str, Any]] = "Authentication failed.",
    ):
        super().__init__(message, "AUTHENTICATION_FAILED", http_status)


class JobNotFoundException(DispatcherException):
    http_status: int = status.HTTP_404_NOT_FOUND
    error_code: str = "JOB_NOT_FOUND"
    message: str = "The requested job was not found."


class TaskNotFoundException(DispatcherException):
    http_status: int = status.HTTP_404_NOT_FOUND
    error_code: str = "TASK_NOT_FOUND"
    message: str = "The requested task was not found."


class InternalException(DispatcherException):
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "An internal server error occurred."
