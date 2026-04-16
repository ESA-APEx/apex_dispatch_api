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
from httpx import get as http_get, Response as HTTPXResponse
from stac_pydantic.collection import Collection, Extent, SpatialExtent, TimeInterval
from stac_pydantic.links import Links
from stac_pydantic.version import STAC_VERSION
from ogc_api_processes_client.api_client_wrapper import ApiClientWrapper
from ogc_api_processes_client.configuration import Configuration
from ogc_api_processes_client.models.inline_or_ref_data import InlineOrRefData
from ogc_api_processes_client.models.input_value_no_object import InputValueNoObject
from ogc_api_processes_client.models.link import Link as OgcLink
from ogc_api_processes_client.models.qualified_input_value import QualifiedInputValue
from ogc_api_processes_client.models.status_code import StatusCode
from ogc_api_processes_client.models.status_info import StatusInfo
from typing import Dict

STAC_COLLECTION_SCHEMA = (
    "https://schemas.stacspec.org/v1.0.0/collection-spec/json-schema/collection.json"
)

GEOJSON_FEATURECOLLECTION_SCHEMA = "https://schemas.opengis.net/ogcapi/" \
    "features/part1/1.0/openapi/schemas/featureCollectionGeoJSON.yaml"


@register_platform(ProcessTypeEnum.OGC_API_PROCESS)
class OGCAPIProcessPlatform(BaseProcessingPlatform):
    input_type_map = {
        "date-interval": ParamTypeEnum.DATE_INTERVAL,
        "bounding-box": ParamTypeEnum.BOUNDING_BOX,
        "boolean": ParamTypeEnum.BOOLEAN,
        "integer": ParamTypeEnum.INTEGER,
        "double": ParamTypeEnum.DOUBLE,
    }

    status_mapping = {
        StatusCode.ACCEPTED: ProcessingStatusEnum.CREATED,
        StatusCode.RUNNING: ProcessingStatusEnum.RUNNING,
        StatusCode.DISMISSED: ProcessingStatusEnum.CANCELED,
        StatusCode.SUCCESSFUL: ProcessingStatusEnum.FINISHED,
        StatusCode.FAILED: ProcessingStatusEnum.FAILED,
    }

    application_path_regex = re.compile(
        r"(?P<namespace>.+)/processes/(?P<process_id>[^/]+)$"
    )

    """
    OGC API Process processing platform implementation.
    This class handles the execution of processing jobs on the OGC API Process platform.
    """

    def _split_job_id(self, job_id) -> tuple[str, ...]:
        parts = job_id.split(":", 1)
        if len(parts) != 2:
            return ("", job_id)
        return tuple(parts)

    async def _create_api_client_instance(
        self,
        endpoint: str,
        namespace: str,
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
            details.endpoint,
            details.namespace if details.namespace else "",
            exchanged_token,
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

    def _map_ogcapi_status(self, ogcapi_status: StatusCode) -> ProcessingStatusEnum:
        """
        Map the status returned by OGC API to a status known within the API.

        :param status: Status text returned by OGC API.
        :return: ProcessingStatusEnum corresponding to the input.
        """

        logger.debug(f"Mapping OGC API status {ogcapi_status} to ProcessingStatusEnum")

        try:
            return self.__class__.status_mapping[ogcapi_status]
        except (AttributeError, KeyError):
            logger.warning(f"Mapping of unknown OGC API status: {ogcapi_status}")
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

        status_info: StatusInfo = api_client.get_status(job_id=internal_job_id)
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

        result: Dict[str, InlineOrRefData] = api_client.get_result(
            job_id=internal_job_id
        )

        # results are obtained, we can now build the returning Collection
        for result_name, result_value in result.items():
            if not result_value.actual_instance:
                logger.debug(f"Ignoring result '{result_name}' with None value")
                continue

            if isinstance(
                result_value.actual_instance, InputValueNoObject
            ) or isinstance(result_value.actual_instance, OgcLink):
                logger.debug(
                    f"Ignoring result '{result_name}' of unmanaged type {type(result_value)}"
                )
                continue

            qualified_value: QualifiedInputValue = result_value.actual_instance

            if (
                qualified_value.var_schema
                and qualified_value.var_schema.actual_instance
            ):
                schema_reference = qualified_value.var_schema.actual_instance
                logger.debug(
                    f"Processing result\n* Name: '{result_name}'\n"
                    "* media type: {qualified_value.media_type}\n"
                    "* Python type: {type(qualified_value.value)}\n"
                    "* schema {qualified_value.var_schema}..."
                )

                if not isinstance(schema_reference, str):
                    logger.warning(
                        f"Processing result name: '{result_name}' can not be processed, "
                        "schema of type {type(schema_reference)} not recognized"
                    )
                    continue

                if STAC_COLLECTION_SCHEMA == schema_reference:
                    logger.success(f"STAC Collection found in results: '{result_name}'")
                    return Collection.model_validate(
                        qualified_value.value.actual_instance
                    )
                elif GEOJSON_FEATURECOLLECTION_SCHEMA == schema_reference:
                    logger.success(
                        f"GeoJSON FeatureCollection found in results: '{result_name}'"
                    )
                    feature_collection = qualified_value.value.oneof_schema_2_validator or {}
                    for feature in feature_collection.get("features", []):
                        for link in feature.get("links", []):
                            if "collection" == link.get("rel") and link.get("href"):
                                collection_link: str = link.get("href")
                                logger.success(
                                    f"GeoJSON FeatureCollection results: '{result_name}' "
                                    "points to a valid collection URL: {collection_link}"
                                )

                                response: HTTPXResponse = http_get(
                                    collection_link,
                                    follow_redirects=True,
                                    headers={
                                        "Authorization": f"Bearer {exchanged_token}"
                                    },
                                )
                                response.raise_for_status()
                                return Collection.model_validate(response.json())
                else:
                    logger.warning(
                        f"Processing result: '{result_name}' can not be processed, "
                        "schema {schema_reference} not yet managed"
                    )

        # result not found, send back an empty collection

        return Collection(
            id=f"{details.namespace}-{internal_job_id}",
            stac_version=STAC_VERSION,
            title=f"Results for {details.application}",
            description=(
                f"OGC API process result items for job '{internal_job_id}' "
                f"of application '{details.application}'."
            ),
            type="Collection",
            license="proprietary",
            links=Links([]),
            extent=Extent(
                spatial=SpatialExtent(bbox=[(-180.0, -90.0, 180.0, 90.0)]),
                temporal=TimeInterval(interval=[[None, None]]),
            ),
        )

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
            details.endpoint,
            details.namespace if details.namespace else "",
            exchanged_token,
        )
        process_description = api_client.get_process_description(details.application)

        if process_description.inputs:
            for input_id, input_details in process_description.inputs.items():
                input_type = (
                    input_id,
                    input_details.model_dump()
                    .get("var_schema", {})
                    .get("actual_instance", {})
                    .get("type", ""),
                )
                if isinstance(input_type, tuple):
                    input_type_str = next(
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
                else:
                    input_type_str = None

                if input_type_str:
                    input_type_str = self.__class__.input_type_map.get(input_type_str)

                if not input_type_str:
                    input_type_str = ParamTypeEnum.STRING
                    input_types = (
                        input_details.model_dump()
                        .get("var_schema", {})
                        .get("actual_instance", {})
                        .get("required")
                        or []
                    )
                    if "bbox" in input_types:
                        input_type_str = ParamTypeEnum.BOUNDING_BOX

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
                        description=input_details.description
                        if input_details.description
                        else f"Parameter: {input_id}",
                        default=None,
                        optional=(input_details.min_occurs == 0),
                        type=input_type_str,
                        options=input_options,
                    )
                )

        return parameters
