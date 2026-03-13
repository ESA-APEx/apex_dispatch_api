import datetime
import hashlib
from typing import List

from fastapi import Response
import jwt
import openeo
import requests
from dotenv import load_dotenv
from loguru import logger
from stac_pydantic import Collection

from app.auth import exchange_token
from app.config.schemas import AuthMethod
from app.config.settings import settings
from app.error import AuthException
from app.platforms.base import BaseProcessingPlatform
from app.platforms.dispatcher import register_platform
from app.schemas.enum import OutputFormatEnum, ProcessingStatusEnum, ProcessTypeEnum
from app.schemas.parameters import ParamTypeEnum, Parameter
from app.schemas.unit_job import ServiceDetails

from openeo.rest import OpenEoApiError

load_dotenv()


@register_platform(ProcessTypeEnum.OPENEO)
class OpenEOPlatform(BaseProcessingPlatform):
    """
    OpenEO processing platform implementation.
    This class handles the execution of processing jobs on the OpenEO platform.
    """

    _connection_cache: dict[str, openeo.Connection] = {}
    _token_expiry_buffer_seconds = 60

    def _build_connection_cache_key(self, user_token: str, url: str) -> str:
        token_fingerprint = hashlib.sha256(user_token.encode("utf-8")).hexdigest()
        return f"openeo_connection_{token_fingerprint}_{url}"

    def _is_auth_error(self, error: OpenEoApiError) -> bool:
        return error.http_status_code in (403, 401)

    def _connection_expired(self, connection: openeo.Connection) -> bool:
        """
        Check if the cached connection is still valid.
        This method can be used to determine if a new connection needs to be established.
        """
        bearer = getattr(getattr(connection, "auth", None), "bearer", None)
        if not bearer:
            logger.warning("No JWT bearer token found in connection.")
            return True

        jwt_bearer_token = bearer.split("/")[-1]
        if jwt_bearer_token:
            try:
                # Check if the token is still valid by decoding it
                payload = jwt.decode(
                    jwt_bearer_token, options={"verify_signature": False}
                )
                exp = payload.get("exp")
                if not exp:
                    logger.warning("JWT bearer token does not contain 'exp' field.")
                    return True
                now = datetime.datetime.now(datetime.timezone.utc).timestamp()
                if exp <= now + self._token_expiry_buffer_seconds:
                    logger.warning("JWT bearer token has expired.")
                    return True  # Token is expired
                else:
                    logger.debug("JWT bearer token is valid.")
                    return False  # Token is valid
            except Exception as e:
                logger.error(f"JWT token validation failed: {e}")
                return True  # Token is expired or invalid

        logger.warning("No JWT bearer token found in connection.")
        return True

    async def _authenticate_user(
        self, user_token: str, url: str, connection: openeo.Connection
    ) -> openeo.Connection:
        """
        Authenticate the connection using the user's token.
        This method can be used to set the user's token for the connection.
        """

        if url not in settings.backend_auth_config:
            raise ValueError(f"No OpenEO backend configuration found for URL: {url}")

        if settings.backend_auth_config[url].auth_method == AuthMethod.USER_CREDENTIALS:
            logger.debug("Using user credentials for OpenEO connection authentication")
            bearer_token = await exchange_token(user_token=user_token, url=url)
            connection.authenticate_bearer_token(bearer_token=bearer_token)
        elif (
            settings.backend_auth_config[url].auth_method
            == AuthMethod.CLIENT_CREDENTIALS
        ):
            logger.debug(
                "Using client credentials for OpenEO connection authentication"
            )
            provider_id, client_id, client_secret = self._get_client_credentials(url)

            connection.authenticate_oidc_client_credentials(
                provider_id=provider_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            raise ValueError(
                "Unsupported OpenEO authentication method: "
                f"{settings.backend_auth_config[url].auth_method}"
            )

        return connection

    async def _setup_connection(
        self, user_token: str, url: str, force_refresh: bool = False
    ) -> openeo.Connection:
        """
        Setup the connection to the OpenEO backend.
        This method can be used to initialize any required client or session.
        """
        cache_key = self._build_connection_cache_key(user_token, url)
        if (
            not force_refresh
            and cache_key in self._connection_cache
            and not self._connection_expired(self._connection_cache[cache_key])
        ):
            logger.debug(f"Reusing cached OpenEO connection to {url} (key: {cache_key})")
            return self._connection_cache[cache_key]

        logger.debug(f"Setting up OpenEO connection to {url}")
        connection = openeo.connect(url)
        connection = await self._authenticate_user(user_token, url, connection)
        self._connection_cache[cache_key] = connection
        return connection

    async def _refresh_connection(self, user_token: str, url: str) -> openeo.Connection:
        logger.info(f"Refreshing OpenEO connection for {url} after authentication error")
        return await self._setup_connection(user_token, url, force_refresh=True)

    async def _execute_job_once(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> str:
        service = await self._build_datacube(user_token, title, details, parameters)
        job = service.create_job(title=title, out_format=format)
        logger.info(f"Executing OpenEO batch job with title={title}")
        job.start()
        return job.job_id

    async def _execute_synchronous_job_once(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> Response:
        service = await self._build_datacube(user_token, title, details, parameters)
        logger.info("Executing synchronous OpenEO job")
        response = service.execute(auto_decode=False)
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response.headers.get("Content-Type"),
        )

    async def _get_job_status_once(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        connection = await self._setup_connection(user_token, details.endpoint)
        job = connection.job(job_id)
        return self._map_openeo_status(job.status())

    async def _get_job_results_once(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> Collection:
        connection = await self._setup_connection(user_token, details.endpoint)
        job = connection.job(job_id)
        return Collection(**job.get_results().get_metadata())

    def _get_client_credentials(self, url: str) -> tuple[str, str, str]:
        """
        Get client credentials for the OpenEO backend.
        This method retrieves the client credentials from environment variables.

        :param url: The URL of the OpenEO backend.
        :return: A tuple containing provider ID, client ID, and client secret.
        """
        credentials_str = settings.backend_auth_config[url].client_credentials

        if not credentials_str:
            raise ValueError(
                f"Client credentials not configured for OpenEO backend at {url}"
            )

        parts = credentials_str.split("/", 2)
        if len(parts) != 3:
            raise ValueError(
                f"Invalid client credentials format for {url},"
                "expected 'provider_id/client_id/client_secret'."
            )
        provider_id, client_id, client_secret = parts
        return provider_id, client_id, client_secret

    def _get_process_id(self, url: str) -> str:
        """
        Get the process ID from a JSON file hosted at the given URL.

        :param url: The URL of the JSON file.
        :return: The process ID extracted from the JSON file.
        """
        logger.debug(f"Fetching process ID from {url}")
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error fetching process ID from {url}: {e}")
            raise ValueError(f"Failed to fetch process ID from {url}")

        process_id = response.json().get("id")
        if not process_id:
            raise ValueError(f"No 'id' field found in process definition at {url}")

        return process_id

    async def _build_datacube(
        self, user_token: str, title: str, details: ServiceDetails, parameters: dict
    ) -> openeo.DataCube:
        process_id = self._get_process_id(details.application)

        logger.debug(
            f"Executing OpenEO job with title={title}, service={details}, "
            f"process_id={process_id}, parameters={parameters}"
        )

        connection = await self._setup_connection(user_token, details.endpoint)
        return connection.datacube_from_process(
            process_id=process_id, namespace=details.application, **parameters
        )

    async def execute_job(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> str:
        try:
            return await self._execute_job_once(
                user_token=user_token,
                title=title,
                details=details,
                parameters=parameters,
                format=format,
            )
        except OpenEoApiError as e:
            if self._is_auth_error(e):
                try:
                    await self._refresh_connection(user_token, details.endpoint)
                    return await self._execute_job_once(
                        user_token=user_token,
                        title=title,
                        details=details,
                        parameters=parameters,
                        format=format,
                    )
                except OpenEoApiError as retry_error:
                    if self._is_auth_error(retry_error):
                        raise AuthException(
                            retry_error.http_status_code,
                            f"Authentication error when executing: {retry_error.message}",
                        )
                    raise retry_error
            raise e
        except Exception as e:
            raise e

    async def execute_synchronous_job(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> Response:
        try:
            return await self._execute_synchronous_job_once(
                user_token=user_token,
                title=title,
                details=details,
                parameters=parameters,
                format=format,
            )
        except OpenEoApiError as e:
            if self._is_auth_error(e):
                try:
                    await self._refresh_connection(user_token, details.endpoint)
                    return await self._execute_synchronous_job_once(
                        user_token=user_token,
                        title=title,
                        details=details,
                        parameters=parameters,
                        format=format,
                    )
                except OpenEoApiError as retry_error:
                    if self._is_auth_error(retry_error):
                        raise AuthException(
                            retry_error.http_status_code,
                            f"Authentication error when executing: {retry_error.message}",
                        )
                    raise retry_error
            raise e
        except Exception as e:
            raise e

    def _map_openeo_status(self, status: str) -> ProcessingStatusEnum:
        """
        Map the status returned by openEO to a status known within the API.

        :param status: Status text returned by openEO.
        :return: ProcessingStatusEnum corresponding to the input.
        """

        logger.debug(f"Mapping openEO status {status} to ProcessingStatusEnum")

        mapping = {
            "created": ProcessingStatusEnum.CREATED,
            "queued": ProcessingStatusEnum.QUEUED,
            "running": ProcessingStatusEnum.RUNNING,
            "cancelled": ProcessingStatusEnum.CANCELED,
            "finished": ProcessingStatusEnum.FINISHED,
            "error": ProcessingStatusEnum.FAILED,
        }

        try:
            return mapping[status.lower()]
        except (AttributeError, KeyError):
            logger.warning("Mapping of unknown openEO status: %r", status)
            return ProcessingStatusEnum.UNKNOWN

    async def get_job_status(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        logger.debug(f"Fetching job status for openEO job with ID {job_id}")
        try:
            return await self._get_job_status_once(user_token, job_id, details)
        except OpenEoApiError as e:
            if self._is_auth_error(e):
                try:
                    await self._refresh_connection(user_token, details.endpoint)
                    return await self._get_job_status_once(
                        user_token, job_id, details
                    )
                except Exception as retry_error:
                    logger.error(
                        "Error occurred while fetching job status for "
                        f"job {job_id} after refresh: {retry_error}"
                    )
                    return ProcessingStatusEnum.UNKNOWN
            logger.error(f"Error occurred while fetching job status for job {job_id}: {e}")
            return ProcessingStatusEnum.UNKNOWN
        except Exception as e:
            logger.error(f"Error occurred while fetching job status for job {job_id}: {e}")
            return ProcessingStatusEnum.UNKNOWN

    async def get_job_results(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> Collection:
        try:
            logger.debug(f"Fetching job result for openEO job with ID {job_id}")
            return await self._get_job_results_once(user_token, job_id, details)
        except OpenEoApiError as e:
            if self._is_auth_error(e):
                try:
                    await self._refresh_connection(user_token, details.endpoint)
                    return await self._get_job_results_once(
                        user_token, job_id, details
                    )
                except OpenEoApiError as retry_error:
                    if self._is_auth_error(retry_error):
                        raise AuthException(
                            retry_error.http_status_code,
                            "Authentication error when fetching job "
                            f"results for job {job_id}: {retry_error.message}",
                        )
                    raise retry_error
            raise e
        except Exception as e:
            raise e

    async def get_service_parameters(
        self, user_token: str, details: ServiceDetails
    ) -> List[Parameter]:
        parameters = []
        logger.debug(
            f"Fetching service parameters for OpenEO service at {details.application}"
        )
        udp = requests.get(details.application)
        udp.raise_for_status()
        udp_params = udp.json().get("parameters", [])

        for param in udp_params:
            schemas = param.get("schema", {})
            if not isinstance(schemas, list):
                schemas = [schemas]
            parameters.append(
                Parameter(
                    name=param.get("name"),
                    description=param.get("description"),
                    default=param.get("default"),
                    optional=param.get("optional", False),
                    type=self._get_type_from_schemas(schemas),
                )
            )

        return parameters

    def _get_type_from_schemas(self, schemas: List[dict]) -> ParamTypeEnum:
        for schema in schemas:
            type = schema.get("type")
            subtype = schema.get("subtype")
            if type == "array" and subtype == "temporal-interval":
                return ParamTypeEnum.DATE_INTERVAL
            elif type == "array" and schema.get("items", {}).get("type") == "string":
                return ParamTypeEnum.ARRAY_STRING
            elif subtype == "bounding-box":
                return ParamTypeEnum.BOUNDING_BOX
            elif subtype == "geojson":
                return ParamTypeEnum.POLYGON
            elif type == "boolean":
                return ParamTypeEnum.BOOLEAN
            elif type == "string":
                return ParamTypeEnum.STRING
            elif type == "integer" or type == "number":
                return ParamTypeEnum.INTEGER

        # If no matching schema found, raise an error
        raise ValueError(f"Unsupported parameter schemas: {schemas}")
