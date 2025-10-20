from abc import ABC, abstractmethod

from app.schemas.enum import OutputFormatEnum, ProcessingStatusEnum
from app.schemas.unit_job import ServiceDetails

from stac_pydantic import Collection


class BaseProcessingPlatform(ABC):
    """
    Abstract base class for processing platforms.
    Defines the interface for processing jobs and managing platform-specific configurations.
    """

    @abstractmethod
    async def execute_job(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> str:
        """
        Execute a processing job on the platform with the given service ID and parameters.

        :param user_token: The access token of the user executing the job.
        :param title: The title of the job to be executed.
        :param details: The service details containing the service ID and application.
        :param parameters: The parameters required for the job execution.
        :param format: Format of the output result.
        :return: Return the ID of the job that was created
        """
        pass

    @abstractmethod
    async def get_job_status(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        """
        Retrieve the job status of a processing job that is running on the platform.

        :param user_token: The access token of the user executing the job.
        :param job_id: The ID of the job on the platform
        :param details: The service details containing the service ID and application.
        :return: Return the processing status
        """
        pass

    @abstractmethod
    async def get_job_results(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> Collection:
        """
        Retrieve the job results of a processing job that is running on the platform.

        :param user_token: The access token of the user executing the job.
        :param job_id: The ID of the job on the platform
        :param details: The service details containing the service ID and application.
        :return: STAC collection representing the results.
        """
        pass
