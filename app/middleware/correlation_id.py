import uuid
import contextvars
from fastapi import Request
from loguru import logger

# Context var to store correlation ID per request
correlation_id_ctx = contextvars.ContextVar("correlation_id", default="-")


async def add_correlation_id(request: Request, call_next):
    # Try to reuse correlation ID from client headers, else generate one
    corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    token = correlation_id_ctx.set(corr_id)

    # Log at start
    logger.bind(correlation_id=corr_id).info(
        f"Incoming request: {request.method} - {request.url.path}",
        method=request.method,
        path=request.url.path,
    )

    response = await call_next(request)

    # Add correlation ID to response headers
    response.headers["X-Correlation-ID"] = corr_id

    # Log at end
    logger.bind(correlation_id=corr_id).info(
        f"Request completed with status code {response.status_code}",
        status_code=response.status_code,
    )
    correlation_id_ctx.reset(token)  # Reset after request
    return response
