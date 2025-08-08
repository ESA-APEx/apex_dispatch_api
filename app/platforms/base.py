from abc import ABC, abstractmethod

from app.schemas import ProcessingJobSummary


class BaseProcessingPlatform(ABC):
    """
    Abstract base class for processing platforms.
    Defines the interface for processing jobs and managing platform-specific configurations.
    """

    @abstractmethod
    def execute_job(self, service_id: str, parameters: dict) -> ProcessingJobSummary:
        """
        Execute a processing job on the platform with the given service ID and parameters.

        :param service_id: The ID of the service to execute.
        :param parameters: The parameters required for the job execution.
        :return: A ProcessingJobSummary object containing the job details.
        """
        pass