from abc import ABC, abstractmethod

from app.schemas.enum import ProcessingStatusEnum
from app.schemas.unit_job import ServiceDetails


class BaseProcessingPlatform(ABC):
    """
    Abstract base class for processing platforms.
    Defines the interface for processing jobs and managing platform-specific configurations.
    """

    @abstractmethod
    def execute_job(self, title: str, details: ServiceDetails, parameters: dict) -> str:
        """
        Execute a processing job on the platform with the given service ID and parameters.

        :param title: The title of the job to be executed.
        :param details: The service details containing the service ID and application.
        :param parameters: The parameters required for the job execution.
        :return: Return the ID of the job that was created
        """
        pass

    @abstractmethod
    def get_job_status(
        self, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        """
        Retrieve the job status of a processing job that is running on the platform.

        :param job_id: The ID of the job on the platform
        :param details: The service details containing the service ID and application.
        :return: Return the processing status
        """
        pass
