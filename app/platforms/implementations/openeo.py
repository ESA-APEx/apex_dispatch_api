import datetime

import jwt
import openeo
import requests
from dotenv import load_dotenv
from loguru import logger
from stac_pydantic import Collection

from app.auth import exchange_token_for_provider
from app.config.settings import OpenEOAuthMethod, settings
from app.platforms.base import BaseProcessingPlatform
from app.platforms.dispatcher import register_platform
from app.schemas.enum import OutputFormatEnum, ProcessingStatusEnum, ProcessTypeEnum
from app.schemas.unit_job import ServiceDetails

load_dotenv()


@register_platform(ProcessTypeEnum.OPENEO)
class OpenEOPlatform(BaseProcessingPlatform):
    """
    OpenEO processing platform implementation.
    This class handles the execution of processing jobs on the OpenEO platform.
    """

    _connection_cache: dict[str, openeo.Connection] = {}

    def _connection_expired(self, connection: openeo.Connection) -> bool:
        """
        Check if the cached connection is still valid.
        This method can be used to determine if a new connection needs to be established.
        """
        jwt_bearer_token = connection.auth.bearer.split("/")[-1]
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
                elif exp < datetime.datetime.now(datetime.timezone.utc).timestamp():
                    logger.warning("JWT bearer token has expired.")
                    return True  # Token is expired
                else:
                    logger.debug("JWT bearer token is valid.")
                    return False  # Token is valid
            except Exception as e:
                logger.error(f"JWT token validation failed: {e}")
                return True  # Token is expired or invalid
        else:
            logger.warning("No JWT bearer token found in connection.")
            return True

    async def _get_bearer_token(self, user_token: str, url: str) -> str:
        """
        Retrieve the bearer token for the OpenEO backend. This is done  by exchanging the user's
        token for a platform-specific token using the configured token provider.

        :param url: The URL of the OpenEO backend.
        :return: The bearer token as a string.
        """

        provider = settings.openeo_backend_config[url].token_provider
        token_prefix = settings.openeo_backend_config[url].token_prefix

        if not provider or not token_prefix:
            raise ValueError(
                f"Backend '{url}' must define 'token_provider' and 'token_prefix'"
            )

        platform_token = await exchange_token_for_provider(
            initial_token=user_token, provider=provider
        )
        return f"{token_prefix}/{platform_token['access_token']}"

    async def _authenticate_user(
        self, user_token: str, url: str, connection: openeo.Connection
    ) -> openeo.Connection:
        """
        Authenticate the connection using the user's token.
        This method can be used to set the user's token for the connection.
        """

        if url not in settings.openeo_backend_config:
            raise ValueError(f"No OpenEO backend configuration found for URL: {url}")

        if (
            settings.openeo_backend_config[url].auth_method
            == OpenEOAuthMethod.USER_CREDENTIALS
        ):
            logger.debug("Using user credentials for OpenEO connection authentication")
            bearer_token = await self._get_bearer_token(user_token, url)
            connection.authenticate_bearer_token(bearer_token=bearer_token)
        elif (
            settings.openeo_backend_config[url].auth_method
            == OpenEOAuthMethod.CLIENT_CREDENTIALS
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
                f"{settings.openeo_backend_config[url].auth_method}"
            )

        return connection

    async def _setup_connection(self, user_token: str, url: str) -> openeo.Connection:
        """
        Setup the connection to the OpenEO backend.
        This method can be used to initialize any required client or session.
        """
        if url in self._connection_cache and not self._connection_expired(
            self._connection_cache[url]
        ):
            logger.debug(f"Reusing cached OpenEO connection to {url}")
            return self._connection_cache[url]

        logger.debug(f"Setting up OpenEO connection to {url}")
        connection = openeo.connect(url)
        connection = await self._authenticate_user(user_token, url, connection)
        self._connection_cache[url] = connection
        return connection

    def _get_client_credentials(self, url: str) -> tuple[str, str, str]:
        """
        Get client credentials for the OpenEO backend.
        This method retrieves the client credentials from environment variables.

        :param url: The URL of the OpenEO backend.
        :return: A tuple containing provider ID, client ID, and client secret.
        """
        credentials_str = settings.openeo_backend_config[url].client_credentials

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

    async def execute_job(
        self,
        user_token: str,
        title: str,
        details: ServiceDetails,
        parameters: dict,
        format: OutputFormatEnum,
    ) -> str:
        process_id = self._get_process_id(details.application)

        logger.debug(
            f"Executing OpenEO job with title={title}, service={details}, "
            f"process_id={process_id}, parameters={parameters}"
        )

        connection = await self._setup_connection(user_token, details.endpoint)
        service = connection.datacube_from_process(
            process_id=process_id, namespace=details.application, **parameters
        )
        job = service.create_job(title=title, out_format=format)
        job.start()

        return job.job_id

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
        connection = await self._setup_connection(user_token, details.endpoint)
        job = connection.job(job_id)
        return self._map_openeo_status(job.status())

    async def get_job_results(
        self, user_token: str, job_id: str, details: ServiceDetails
    ) -> Collection:
        logger.debug(f"Fetching job result for openEO job with ID {job_id}")
        connection = await self._setup_connection(user_token, details.endpoint)
        job = connection.job(job_id)
        return Collection(**job.get_results().get_metadata())
