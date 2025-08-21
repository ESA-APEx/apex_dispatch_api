import logging
import os
import sys


from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Redirect standard logging (incl. uvicorn) to Loguru.
    """

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging():
    logger.remove()  # remove default handler
    env = os.getenv("APP_ENV", "development")

    if env == "production":
        # JSON logs for ELK
        logger.add(
            sys.stdout,
            serialize=True,
            backtrace=False,
            diagnose=False,
            level="INFO",
        )
    else:
        # Pretty logs for dev
        logger.add(
            sys.stdout,
            colorize=True,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "{message}"
            ),
            backtrace=True,
            diagnose=True,
            level="DEBUG",
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
