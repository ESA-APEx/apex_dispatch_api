
from app.platforms.base import BaseProcessingPlatform
from app.platforms.ogc_api_process import OGCAPIProcessPlatform
from app.platforms.openeo import OpenEOPlatform 
from app.schemas import ProcessType


def get_processing_platform(service_type: ProcessType) -> BaseProcessingPlatform:
    """
    Factory function to get the appropriate processing platform based on the service type.
    
    :param service_type: The type of service for which to get the processing platform.
    :return: An instance of a class that implements BaseProcessingPlatform.
    """
    if service_type == ProcessType.OPENEO:
        return OpenEOPlatform()
    elif service_type == ProcessType.OGC_API_PROCESS:
        return OGCAPIProcessPlatform()
    else:
        raise ValueError(f"Unsupported service type: {service_type}")