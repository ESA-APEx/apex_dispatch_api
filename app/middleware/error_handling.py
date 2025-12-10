from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.error import DispatcherException, ErrorResponse
from app.middleware.correlation_id import correlation_id_ctx
from loguru import logger


def get_dispatcher_error_response(
    exc: DispatcherException, request_id: str
) -> ErrorResponse:
    return ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
    )


async def dispatch_exception_handler(request: Request, exc: DispatcherException):

    content = get_dispatcher_error_response(exc, correlation_id_ctx.get())
    logger.exception(f"DispatcherException raised: {exc.message}")
    return JSONResponse(status_code=exc.http_status, content=content.dict())


async def generic_exception_handler(request: Request, exc: Exception):

    # DO NOT expose internal exceptions to the client
    content = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred.",
        details=None,
        request_id=correlation_id_ctx.get(),
    )

    logger.exception(f"GenericException raised: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content.dict()
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):

    content = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed.",
        details={"errors": exc.errors()},
        request_id=correlation_id_ctx.get(),
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content.dict()
    )


def register_exception_handlers(app):
    """
    Call this in main.py after creating the FastAPI() instance.
    """

    app.add_exception_handler(DispatcherException, dispatch_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
