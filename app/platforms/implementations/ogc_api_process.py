from typing import List
from fastapi import Response
from app.platforms.base import BaseProcessingPlatform
from app.platforms.dispatcher import register_platform
from app.schemas.enum import OutputFormatEnum, ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.parameters import Parameter
from app.schemas.unit_job import ServiceDetails
from stac_pydantic import Collection
from ogc_api_client import Configuration
from ogc_api_client.api.execute_api import ExecuteApi
from ogc_api_client.api_client_wrapper import ApiClientWrapper
from ogc_api_client.rest import ApiException

@register_platform(ProcessTypeEnum.OGC_API_PROCESS)
class OGCAPIProcessPlatform(BaseProcessingPlatform):
    """
    OGC API Process processing platform implementation.
    This class handles the execution of processing jobs on the OGC API Process platform.
    """

    def _create_api_client_instance(
        self,
        details: ServiceDetails
    ) -> ApiClientWrapper:
        configuration: Configuration = Configuration(
            host = details.endpoint
        )
        return ApiClientWrapper(configuration)

    async def execute_job(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> str:
        api_client = self._create_api_client_instance(details)

        raise NotImplementedError("OGC API Process job execution not implemented yet.")

    async def execute_synchronous_job(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> Response:
        # This is currently not supported

        raise NotImplementedError("OGC API Process job execution not implemented yet.")

    async def get_job_status(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        api_client = self._create_api_client_instance(details)

        raise NotImplementedError(
            "OGC API Process job status retrieval not implemented yet."
        )

    async def get_job_results(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> Collection:
        api_client = self._create_api_client_instance(details)

        raise NotImplementedError(
            "OGC API Process job result retrieval not implemented yet."
        )

    async def get_service_parameters(
        self, user_token: str, details: ServiceDetails
    ) -> List[Parameter]:
        api_client = self._create_api_client_instance(details)

        raise NotImplementedError(
            "OGC API Process service parameter retrieval not implemented yet."
        )
