import json

import re
from typing import List
from fastapi import Response
from loguru import logger

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
from ogc_api_client.models.status_info import StatusInfo, StatusCode

@register_platform(ProcessTypeEnum.OGC_API_PROCESS)
class OGCAPIProcessPlatform(BaseProcessingPlatform):

    application_path_regex = re.compile(r"(?P<namespace>.+)/processes/(?P<process_id>[^/]+)$")

    """
    OGC API Process processing platform implementation.
    This class handles the execution of processing jobs on the OGC API Process platform.
    """

    def _split_job_id(self, job_id):
        parts = job_id.split(":", 1)
        if len(parts) != 2:
            return (None, job_id)
        return tuple(parts)

    
    def _create_api_client_instance(
        self,
        endpoint: str,
        namespace: str,
        user_token: str = None,
    ) -> ApiClientWrapper:
        configuration: Configuration = Configuration(
            host = f"{endpoint}/{namespace}" if namespace else endpoint
        )

        additional_args = {}
        if user_token:
            additional_args["header_name"] = "Authorization"
            additional_args["header_value"] = f"Bearer {user_token}"

        return ApiClientWrapper(configuration, **additional_args)

    async def execute_job(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> str:
        logger.info(f"Executing OGC API job with title={title}")
        # Output format omitted from request

        api_client = self._create_api_client_instance(details.endpoint, details.namespace, user_token)

        headers = {
            "accept": "*/*",
            #"Prefer": "respond-async;return=representation",
            "Content-Type": "application/json"
        }
        if user_token:
            headers["Authorization"] = f"Bearer {user_token}"

        data = {
            "inputs": {key: value for key, value in parameters.items()}
        }
        
        content = api_client.execute_simple(process_id=details.application, execute=data, _headers=headers)

        job_id = content.job_id
        
        # Return the namespace along with the job ID if needed
        if details.namespace:
            return f"{details.namespace}:{job_id}"
        return job_id


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

    
    def _map_ogcapi_status(self, ogcapi_status: str) -> ProcessingStatusEnum:
        """
        Map the status returned by OGC API to a status known within the API.

        :param status: Status text returned by OGC API.
        :return: ProcessingStatusEnum corresponding to the input.
        """

        logger.debug(f"Mapping OGC API status {ogcapi_status} to ProcessingStatusEnum")

        mapping = {
            StatusCode.ACCEPTED: ProcessingStatusEnum.CREATED,
            StatusCode.RUNNING: ProcessingStatusEnum.RUNNING,
            StatusCode.DISMISSED: ProcessingStatusEnum.CANCELED,
            StatusCode.SUCCESSFUL: ProcessingStatusEnum.FINISHED,
            StatusCode.FAILED: ProcessingStatusEnum.FAILED,
        }

        try:
            return mapping[ogcapi_status]
        except (AttributeError, KeyError):
            logger.warning("Mapping of unknown OGC API status: %r", ogcapi_status)
            return ProcessingStatusEnum.UNKNOWN


    
    async def get_job_status(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        logger.debug(f"Fetching job status for OGC API job with ID {job_id}")
        
        # Job ID is composed of namespace and internal job id
        namespace, internal_job_id = self._split_job_id(job_id)
        api_client = self._create_api_client_instance(details.endpoint, namespace, user_token)

        status_info = api_client.get_status(job_id=internal_job_id)
        return self._map_ogcapi_status(status_info.status)


    async def get_job_results(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> Collection:
        logger.debug(f"Fetching job result for opfenEO job with ID {job_id}")

        # Job ID is composed of namespace and internal job id
        namespace, internal_job_id = self._split_job_id(job_id)
        api_client = self._create_api_client_instance(details.endpoint, namespace, user_token)

        result = api_client.get_result(job_id=internal_job_id)
        return Collection(result[0])


    async def get_service_parameters(
        self, user_token: str, details: ServiceDetails
    ) -> List[Parameter]:

        parameters = []
        logger.debug(
            f"Fetching service parameters for OGC API process with ID {details.application}"
        )

        api_client = self._create_api_client_instance(details.endpoint, details.namespace, user_token)
        process_description = api_client.get_process_description(details.application)

        for input_id, input_details in process_description.inputs.items():
            input_type = input_id, input_details.model_dump().get("var_schema", {}).get("actual_instance", {}).get("type", "string")
            if isinstance(input_type, tuple):
                input_type = next((t for t in input_type if t in ["date-interval", "bounding-box", "boolean"]), "string")

            parameters.append(
                Parameter(
                    name=input_id,
                    description=input_details.description,
                    default=None,
                    optional=(input_details.min_occurs == 0),
                    type="string",
                )
            )

        return parameters
