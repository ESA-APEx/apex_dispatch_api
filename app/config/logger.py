import logging
import os
import sys


from app.middleware.correlation_id import correlation_id_ctx
from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Redirect standard logging (incl. uvicorn) to Loguru.
    """

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
            corr_id = correlation_id_ctx.get()
        except ValueError:
            level = record.levelno
        except LookupError:
            corr_id = None

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )
        if corr_id:
            logger.bind(correlation_id=corr_id)


def correlation_id_filter(record):
    # Always inject the current correlation ID into the log record
    record["extra"]["correlation_id"] = correlation_id_ctx.get()
    return True


def setup_logging():
    logger.remove()  # remove default handler
    env = os.getenv("APP_ENV", "development")

    logger.configure(extra={"correlation_id": None})
    if env == "production":
        # JSON logs for ELK
        logger.add(
            sys.stdout,
            serialize=True,
            backtrace=False,
            diagnose=False,
            level="INFO",
            filter=correlation_id_filter,
        )
    else:
        # Pretty logs for dev
        logger.add(
            sys.stdout,
            colorize=True,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<i>{extra[correlation_id]}</i> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan> :<cyan>{line}</cyan> - "
                "{message}"
            ),
            backtrace=True,
            diagnose=True,
            level="DEBUG",
            filter=correlation_id_filter,
        )

    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "app.routers",
        "app.services",
        "app.platforms",
    ):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False

    return logger
