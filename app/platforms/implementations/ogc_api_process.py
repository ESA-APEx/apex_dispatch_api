import re
from typing import List
from app.auth import exchange_token, get_current_user_claims
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

GEOJSON_FEATURECOLLECTION_SCHEMA = (
    "https://schemas.opengis.net/ogcapi/"
    "features/part1/1.0/openapi/schemas/featureCollectionGeoJSON.yaml"
)


@register_platform(ProcessTypeEnum.OGC_API_PROCESS)
class OGCAPIProcessPlatform(BaseProcessingPlatform):
    input_type_map = {
        "date-time": ParamTypeEnum.DATETIME,
        "date-interval": ParamTypeEnum.DATE_INTERVAL,
        "bounding-box": ParamTypeEnum.BOUNDING_BOX,
        "boolean": ParamTypeEnum.BOOLEAN,
        "integer": ParamTypeEnum.INTEGER,
        "double": ParamTypeEnum.DOUBLE,
        "number": ParamTypeEnum.DOUBLE,
        "string": ParamTypeEnum.STRING,
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

    geojson_schema_references = {
        GEOJSON_FEATURECOLLECTION_SCHEMA,
        "https://geojson.org/schema/FeatureCollection.json",
        "https://geojson.org/schema/Feature.json",
    }

    """
    OGC API Process processing platform implementation.
    This class handles the execution of processing jobs on the OGC API Process platform.
    """

    def _split_job_id(self, job_id) -> tuple[str, ...]:
        parts = job_id.split(":", 1)
        if len(parts) != 2:
            return ("", job_id)
        return tuple(parts)

    def _get_type_from_schema(
        self, schema: dict | str | None, input_id: str = ""
    ) -> ParamTypeEnum:
        if isinstance(schema, str):
            if schema in self.__class__.geojson_schema_references:
                return ParamTypeEnum.POLYGON
            return self.__class__.input_type_map.get(schema, ParamTypeEnum.STRING)

        if not isinstance(schema, dict):
            return ParamTypeEnum.STRING

        schema_type = str(schema.get("type"))
        schema_format = schema.get("format")
        schema_subtype = schema.get("subtype")

        if schema_type == "array" and schema_subtype == "date-interval":
            return ParamTypeEnum.DATE_INTERVAL
        if schema_type == "array" and schema.get("items", {}).get("type") == "string":
            return ParamTypeEnum.ARRAY_STRING
        if schema_subtype == "geojson":
            return ParamTypeEnum.POLYGON
        if schema_subtype == "bounding-box":
            return ParamTypeEnum.BOUNDING_BOX
        if schema_format == "geojson":
            return ParamTypeEnum.POLYGON
        if schema_format == "date-time":
            return ParamTypeEnum.DATETIME
        if schema_type == "object":
            required = schema.get("required") or []
            if "type" in required and "coordinates" in required:
                type_properties = schema.get("properties", {}).get("type", {})
                type_instance = type_properties
                while "actual_instance" in type_instance:
                    type_instance = type_instance["actual_instance"]
                if "Polygon" in type_instance.get("enum", []):
                    return ParamTypeEnum.POLYGON
                if "Point" in type_instance.get("enum", []):
                    return ParamTypeEnum.POINT
            elif "bbox" in required:
                return ParamTypeEnum.BOUNDING_BOX

        if isinstance(schema.get("$ref"), str):
            return self._get_type_from_schema(schema.get("$ref"), input_id)

        for variant_key in ("oneOf", "anyOf", "allOf"):
            variants = schema.get(variant_key) or []
            if not isinstance(variants, list):
                continue
            for variant in variants:
                detected_type = self._get_type_from_schema(variant, input_id)
                if detected_type != ParamTypeEnum.STRING:
                    return detected_type

        properties = schema.get("properties") or {}
        if (
            schema.get("title") == "GeoJSON"
            or "geometry" in properties
            or "features" in properties
            or input_id.lower() in {"aoi", "geometry", "geom", "geojson"}
        ):
            return ParamTypeEnum.POLYGON

        return self.__class__.input_type_map.get(schema_type, ParamTypeEnum.STRING)

    def _get_options_from_schema(self, schema: dict | str | None) -> list:
        if not isinstance(schema, dict):
            return []
        options = schema.get("enum")
        return options if isinstance(options, list) else []

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

        parameters = await self._transform_parameters(user_token, details, parameters)

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

        user_claims = get_current_user_claims(user_token)
        properties = {
            "title": title,
            "application": details.application,
        }
        if user_claims.get("sub"):
            properties["user_id"] = user_claims["sub"]
        if user_claims.get("preferred_username"):
            properties["username"] = user_claims["preferred_username"]
        if user_claims.get("email"):
            properties["email"] = user_claims["email"]

        data = {
            "inputs": parameters,
            "properties": properties,
        }

        content = api_client.execute_simple(
            process_id=details.application, execute=data, _headers=headers
        )

        job_id = content.job_id

        # Return the namespace along with the job ID if needed
        if details.namespace:
            return f"{details.namespace}:{job_id}"
        return job_id

    def _transform_bbox_parameter(self, param_name: str, value) -> list[float]:
        if isinstance(value, (list, tuple)) and len(value) == 4:
            return [float(coord) for coord in value]

        if isinstance(value, dict):
            if ["east", "north", "south", "west"] == sorted(value.keys()):
                return [
                    float(value["west"]),
                    float(value["south"]),
                    float(value["east"]),
                    float(value["north"]),
                ]

        raise ValueError(
            f"Unsupported bounding box value for parameter {param_name}: {value}"
        )

    async def _transform_parameters(
        self, user_token: str, details: ServiceDetails, parameters: dict
    ) -> dict:
        service_params = await self.get_service_parameters(user_token, details)

        modifiers = {
            ParamTypeEnum.BOUNDING_BOX: self._transform_bbox_parameter,
        }

        transformed_parameters = parameters.copy()
        for param in service_params:
            if param.name not in parameters:
                continue

            modifier = modifiers.get(param.type)

            if modifier:
                transformed_parameters[param.name] = modifier(
                    param.name, parameters[param.name]
                )

        logger.debug(
            f"Transformed parameters for OGC API Process: {transformed_parameters}"
        )
        return transformed_parameters

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

    def _extract_download_link_from_asset(self, asset: dict) -> str | None:
        """
        Extracts the download link from an asset dictionary. Checks if the `href` field is present and contains an HTTPS URL.
        If this is not the case, look for an alternative link in `alternate` field. If no valid link is found, return None.

        Args:
            asset (dict): The asset dictionary.

        Returns:
            str | None: The download link if available, otherwise None.
        """
        refs = [
            asset.get("href"),
            asset.get("alternate", {}).get("https", {}).get("href"),
        ]
        for href in refs:
            if href and href.startswith("https://"):
                return href
        return None

    def _generate_signed_url(self, href: str, user_token: str) -> str:
        """
        Generate a signed URL for the given href using the provided user token.
        This is a placeholder implementation and should be replaced with actual logic to generate signed URLs.

        Args:
            href (str): The original href.
            user_token (str): The user token to be used for signing.
        """
        # TODO - Add implementation
        logger.debug(f"Generating signed URL for href: {href} with user token.")
        return href
    
    def _update_assets_hrefs(self, assets: dict, user_token: str) -> dict:
        """
        Update the hrefs of the assets to be HTTPS URLs. If the current href is an S3 URL, the code will look into 
        `alternate` links to find an HTTPS URL. If no HTTPS URL is found, the original href will be kept.
        """
        updated_assets = {}
        for asset_name, asset in assets.items():
            updated_asset = asset.copy()
            href = self._extract_download_link_from_asset(asset)
            if not href:
                logger.warning(
                    f"No valid HTTPS download link found for asset '{asset_name}'. Keeping original href. "
                    "Skipping asset..."
                )
            else:
                href = self._generate_signed_url(href, user_token)
                updated_asset["href"] = href
                updated_assets[asset_name] = updated_asset

        return updated_assets

    def _extract_assets_from_feature_collection(
        self, feature_collection: dict, *, result_name: str, user_token: str
    ) -> dict:
        assets: dict = {}
        for feature in feature_collection.get("features", []):
            feature_assets = feature.get("assets")
            if isinstance(feature_assets, dict):
                assets.update(feature_assets)
                continue

            # Some providers expose assets through an item link instead of inlining them in the feature.
            for link in feature.get("links", []):
                if "collection" == link.get("rel") and link.get("href"):
                    collection_link: str = link.get("href")
                    logger.debug(
                        f"GeoJSON FeatureCollection results: '{result_name}' "
                        f"points to a valid collection URL: {collection_link}"
                    )

                    response: HTTPXResponse = http_get(
                        collection_link,
                        follow_redirects=True,
                        headers={"Authorization": f"Bearer {user_token}"},
                    )
                    response.raise_for_status()
                    collection = Collection.model_validate(response.json())
                    logger.debug(
                        f"Extracted collection '{collection.id}' with assets: {list(collection.assets.keys())}"
                    )
                    assets.update(collection.to_dict().get("assets", {}))
                    break
        return assets

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
        assets: dict = {}
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
                    f"* media type: {qualified_value.media_type}\n"
                    f"* Python type: {type(qualified_value.value)}\n"
                    f"* schema {qualified_value.var_schema}..."
                )

                if not isinstance(schema_reference, str):
                    logger.warning(
                        f"Processing result name: '{result_name}' can not be processed, "
                        f"schema of type {type(schema_reference)} not recognized"
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
                    feature_collection = (
                        qualified_value.value.oneof_schema_2_validator or {}
                    )
                    assets.update(
                        self._extract_assets_from_feature_collection(
                            feature_collection,
                            result_name=result_name,
                            user_token=user_token,
                        )
                    )
                else:
                    logger.warning(
                        f"Processing result: '{result_name}' can not be processed, "
                        f"schema {schema_reference} not yet managed"
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
            assets=self._update_assets_hrefs(assets, exchanged_token),
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
                schema = (
                    input_details.model_dump()
                    .get("var_schema", {})
                    .get("actual_instance")
                )
                parameters.append(
                    Parameter(
                        name=input_id,
                        description=input_details.description
                        if input_details.description
                        else f"Parameter: {input_id}",
                        default=None,
                        optional=(input_details.min_occurs == 0),
                        type=self._get_type_from_schema(schema, input_id),
                        options=self._get_options_from_schema(schema),
                    )
                )

        return parameters
