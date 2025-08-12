import importlib
import logging
import app.platforms.implementations
import pkgutil
from typing import Dict, Type
from app.platforms.base import BaseProcessingPlatform
from app.schemas import ProcessTypeEnum

PROCESSING_PLATFORMS: Dict[ProcessTypeEnum, Type[BaseProcessingPlatform]] = {}

logger = logging.getLogger(__name__)


def load_processing_platforms():
    """Dynamically load all processing platform implementations."""
    for _, module_name, _ in pkgutil.iter_modules(
        app.platforms.implementations.__path__
    ):
        importlib.import_module(f"app.platforms.implementations.{module_name}")


def register_processing_platform(
    service_type: ProcessTypeEnum, cls: Type[BaseProcessingPlatform]
):
    """ "Register a new processing platform class for a specific service type.

    :param service_type: The type of service for which to register the platform.
    :param cls: The class that implements BaseProcessingPlatform.
    """
    logger.debug(
        f"Registering processing platform with class {cls} for service type: {service_type}"
    )
    PROCESSING_PLATFORMS[service_type] = cls


def get_processing_platform(service_type: ProcessTypeEnum) -> BaseProcessingPlatform:
    """
    Factory function to get the appropriate processing platform based on the service type.

    :param service_type: The type of service for which to get the processing platform.
    :return: An instance of a class that implements BaseProcessingPlatform.
    """
    try:
        return PROCESSING_PLATFORMS[service_type]()
    except KeyError:
        raise ValueError(f"Unsupported service type: {service_type}")
