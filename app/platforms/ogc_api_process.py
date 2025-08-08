
import logging

from app.platforms.base import BaseProcessingPlatform
from app.schemas import ProcessingJobSummary, ServiceDetails


logger = logging.getLogger(__name__)

class OGCAPIProcessPlatform(BaseProcessingPlatform):
    """
    OGC API Process processing platform implementation.
    This class handles the execution of processing jobs on the OGC API Process platform.
    """

    def execute_job(self, title: str, details: ServiceDetails, parameters: dict) -> ProcessingJobSummary:
        """
        Execute a processing job on the OGC API Process platform with the given service ID and parameters.

        :param title: The title of the job to be executed.
        :param details: The service details containing the service ID and application.
        :param parameters: The parameters required for the job execution.
        :return: A ProcessingJobSummary object containing the job details.
        """
        raise NotImplementedError("OGC API Process job execution not implemented yet.")