import logging

from app.platforms.base import BaseProcessingPlatform
from app.platforms.dispatcher import register_processing_platform
from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.unit_job import ServiceDetails

logger = logging.getLogger(__name__)


class OGCAPIProcessPlatform(BaseProcessingPlatform):
    """
    OGC API Process processing platform implementation.
    This class handles the execution of processing jobs on the OGC API Process platform.
    """

    def execute_job(self, title: str, details: ServiceDetails, parameters: dict) -> str:
        raise NotImplementedError("OGC API Process job execution not implemented yet.")

    def get_job_status(
        self, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        raise NotImplementedError(
            "OGC API Process job status retrieval not implemented yet."
        )


register_processing_platform(ProcessTypeEnum.OGC_API_PROCESS, OGCAPIProcessPlatform)
