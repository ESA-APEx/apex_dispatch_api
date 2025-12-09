from typing import List
from fastapi import Response
from app.platforms.base import BaseProcessingPlatform
from app.platforms.dispatcher import register_platform
from app.schemas.enum import OutputFormatEnum, ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.parameters import Parameter
from app.schemas.unit_job import ServiceDetails
from stac_pydantic import Collection


@register_platform(ProcessTypeEnum.OGC_API_PROCESS)
class OGCAPIProcessPlatform(BaseProcessingPlatform):
    """
    OGC API Process processing platform implementation.
    This class handles the execution of processing jobs on the OGC API Process platform.
    """

    async def execute_job(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> str:
        raise NotImplementedError("OGC API Process job execution not implemented yet.")

    async def execute_synchronous_job(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> Response:
        raise NotImplementedError("OGC API Process job execution not implemented yet.")

    async def get_job_status(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        raise NotImplementedError(
            "OGC API Process job status retrieval not implemented yet."
        )

    async def get_job_results(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> Collection:
        raise NotImplementedError(
            "OGC API Process job result retrieval not implemented yet."
        )

    async def get_service_parameters(
        self, user_token: str, details: ServiceDetails
    ) -> List[Parameter]:
        raise NotImplementedError(
            "OGC API Process service parameter retrieval not implemented yet."
        )
