import logging
import logging.config


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,  # keeps Uvicorn's loggers
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {  # applies to all loggers unless overridden
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "uvicorn": {"level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"level": "INFO"},
        # custom API loggers
        "routers": {"level": "DEBUG"},      # all your routers
        "services": {"level": "DEBUG"},     # all your services
    },
}

def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)