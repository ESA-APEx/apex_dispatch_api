import re
from typing import List
from app.auth import exchange_token
from fastapi import Response
from loguru import logger

from app.platforms.base import BaseProcessingPlatform
from app.platforms.dispatcher import register_platform
from app.schemas.enum import OutputFormatEnum, ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.parameters import ParamTypeEnum, Parameter
from app.schemas.unit_job import ServiceDetails
from stac_pydantic import Collection
from stac_pydantic.collection import Extent, SpatialExtent, TimeInterval
from ogc_api_processes_client import Configuration
from ogc_api_processes_client.api_client_wrapper import ApiClientWrapper
from ogc_api_processes_client.models.status_info import StatusCode
from pystac import ItemCollection

@register_platform(ProcessTypeEnum.OGC_API_PROCESS)
class OGCAPIProcessPlatform(BaseProcessingPlatform):
    input_type_map = {
        "date-interval": ParamTypeEnum.DATE_INTERVAL,
        "bounding-box": ParamTypeEnum.BOUNDING_BOX,
        "boolean": ParamTypeEnum.BOOLEAN,
        "integer": ParamTypeEnum.INTEGER,
        "double": ParamTypeEnum.DOUBLE,
    }

    application_path_regex = re.compile(
        r"(?P<namespace>.+)/processes/(?P<process_id>[^/]+)$"
    )

    """
    OGC API Process processing platform implementation.
    This class handles the execution of processing jobs on the OGC API Process platform.
    """

    def _split_job_id(self, job_id):
        parts = job_id.split(":", 1)
        if len(parts) != 2:
            return (None, job_id)
        return tuple(parts)

    async def _create_api_client_instance(
        self,
        endpoint: str,
        namespace: str | None = None,
        user_token: str | None = None,
    ) -> ApiClientWrapper:
        configuration: Configuration = Configuration(
            host=f"{endpoint}/{namespace}" if namespace else endpoint
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

        # Exchanging token
        logger.debug("Exchanging user token for OGC API Process execution...")
        exchanged_token = await exchange_token(
            user_token=user_token, url=details.endpoint
        )

        # Output format omitted from request
        api_client = await self._create_api_client_instance(
            details.endpoint, details.namespace, exchanged_token
        )

        headers = {
            "accept": "*/*",
            # "Prefer": "respond-async;return=representation",
            "Content-Type": "application/json",
        }
        if exchanged_token:
            headers["Authorization"] = f"Bearer {exchanged_token}"

        data = {"inputs": {key: value for key, value in parameters.items()}}

        content = api_client.execute_simple(
            process_id=details.application, execute=data, _headers=headers
        )

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
            return mapping[StatusCode(ogcapi_status)]
        except (AttributeError, KeyError):
            logger.warning("Mapping of unknown OGC API status: %r", ogcapi_status)
            return ProcessingStatusEnum.UNKNOWN

    async def get_job_status(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        logger.debug(f"Fetching job status for OGC API job with ID {job_id}")

        logger.debug("Exchanging user token for OGC API Process execution...")
        exchanged_token = await exchange_token(
            user_token=user_token, url=details.endpoint
        )

        # Job ID is composed of namespace and internal job id
        namespace, internal_job_id = self._split_job_id(job_id)
        api_client = await self._create_api_client_instance(
            details.endpoint, namespace, exchanged_token
        )

        status_info = api_client.get_status(job_id=internal_job_id)
        return self._map_ogcapi_status(status_info.status)

    async def get_job_results(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> Collection:
        logger.debug(f"Fetching job result for opfenEO job with ID {job_id}")

        logger.debug("Exchanging user token for OGC API Process execution...")
        exchanged_token = await exchange_token(
            user_token=user_token, url=details.endpoint
        )

        # Job ID is composed of namespace and internal job id
        namespace, internal_job_id = self._split_job_id(job_id)
        api_client = await self._create_api_client_instance(
            details.endpoint, namespace, exchanged_token
        )

        result = api_client.get_result_simple(job_id=internal_job_id)
        if isinstance(result, ItemCollection):
            result_dict = result.to_dict()
        else:
            result_dict = dict(result)

        # Convert pystac ItemCollection (GeoJSON FeatureCollection) to a STAC Collection.
        collection = Collection(
            id=f"{details.application}-{internal_job_id}",
            title=f"Results for {details.application}",
            description=(
                f"OGC API process result items for job '{internal_job_id}' "
                f"of application '{details.application}'."
            ),
            type="Collection",
            license="proprietary",
            links=result_dict.get("links", []),
            extent=Extent(
                spatial=SpatialExtent(bbox=[(-180.0, -90.0, 180.0, 90.0)]),
                temporal=TimeInterval(interval=[[None, None]]),
            ),
            features=result_dict.get("features", []),
        )

        return collection

    async def get_service_parameters(
        self, user_token: str, details: ServiceDetails
    ) -> List[Parameter]:

        parameters = []
        logger.debug(
            f"Fetching service parameters for OGC API process with ID {details.application}"
        )

        logger.debug("Exchanging user token for OGC API Process execution...")
        exchanged_token = await exchange_token(
            user_token=user_token, url=details.endpoint
        )

        api_client = await self._create_api_client_instance(
            details.endpoint, details.namespace, exchanged_token
        )
        process_description = api_client.get_process_description(details.application)

        for input_id, input_details in (process_description.inputs or {}).items():
            input_type: tuple | str | None = (
                input_id,
                input_details.model_dump()
                .get("var_schema", {})
                .get("actual_instance", {})
                .get("type", ""),
            )
            if isinstance(input_type, tuple):
                input_type = next(
                    (
                        t
                        for t in input_type
                        if t
                        in [
                            "date-interval",
                            "bounding-box",
                            "boolean",
                            "integer",
                            "double",
                        ]
                    ),
                    None,
                )
            if isinstance(input_type, str):
                input_type = self.__class__.input_type_map.get(input_type)

            if not input_type:
                input_type = ParamTypeEnum.STRING
                input_types = (
                    input_details.model_dump()
                    .get("var_schema", {})
                    .get("actual_instance", {})
                    .get("required")
                    or []
                )
                if "bbox" in input_types:
                    input_type = ParamTypeEnum.BOUNDING_BOX

            input_options = (
                input_details.model_dump()
                .get("var_schema", {})
                .get("actual_instance", {})
                .get("enum")
                or []
            )
            parameters.append(
                Parameter(
                    name=input_id,
                    description=input_details.description or input_id,
                    default=None,
                    optional=(input_details.min_occurs == 0),
                    type=input_type,
                    options=input_options,
                )
            )

        return parameters
