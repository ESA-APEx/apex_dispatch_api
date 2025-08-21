import importlib

from loguru import logger
import app.platforms.implementations
import pkgutil
from typing import Dict, Type
from app.platforms.base import BaseProcessingPlatform
from app.schemas.enum import ProcessTypeEnum

PROCESSING_PLATFORMS: Dict[ProcessTypeEnum, Type[BaseProcessingPlatform]] = {}


def register_platform(service_type: ProcessTypeEnum):
    def decorator(cls: Type[BaseProcessingPlatform]):
        logger.debug(
            f"Registering processing platform with class {cls} for service type: {service_type}"
        )
        PROCESSING_PLATFORMS[service_type] = cls
        return cls

    return decorator


def load_processing_platforms():
    """Dynamically load all processing platform implementations."""
    for _, module_name, _ in pkgutil.iter_modules(
        app.platforms.implementations.__path__
    ):
        importlib.import_module(f"app.platforms.implementations.{module_name}")


def get_processing_platform(service_type: ProcessTypeEnum) -> BaseProcessingPlatform:
    """
    Factory function to get the appropriate processing platform based on the service type.

    :param service_type: The type of service for which to get the processing platform.
    :return: An instance of a class that implements BaseProcessingPlatform.
    """
    try:
        return PROCESSING_PLATFORMS[service_type]()
    except KeyError:
        logger.error(f"Processing platform for service type {service_type} not found.")
        raise ValueError(f"Unsupported service type: {service_type}")
