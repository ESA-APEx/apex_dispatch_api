import logging

from app.platforms.base import BaseProcessingPlatform
from app.platforms.dispatcher import register_processing_platform
from app.schemas import ProcessType, ProcessingJobSummary, ServiceDetails


logger = logging.getLogger(__name__)


class OGCAPIProcessPlatform(BaseProcessingPlatform):
    """
    OGC API Process processing platform implementation.
    This class handles the execution of processing jobs on the OGC API Process platform.
    """

    def execute_job(self, title: str, details: ServiceDetails, parameters: dict) -> str:
        """
        Execute a processing job on the platform with the given service ID and parameters.

        :param title: The title of the job to be executed.
        :param details: The service details containing the service ID and application.
        :param parameters: The parameters required for the job execution.
        :return: Return the ID of the job that was created
        """

        raise NotImplementedError("OGC API Process job execution not implemented yet.")


register_processing_platform(ProcessType.OGC_API_PROCESS, OGCAPIProcessPlatform)
