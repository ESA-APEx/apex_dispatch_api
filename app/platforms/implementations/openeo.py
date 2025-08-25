import datetime
import os
import re
import urllib
import jwt

from loguru import logger
import openeo
import requests
from dotenv import load_dotenv

from app.platforms.base import BaseProcessingPlatform
from app.platforms.dispatcher import register_platform
from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.unit_job import ServiceDetails
from stac_pydantic import Collection

load_dotenv()

# Constants
BACKEND_AUTH_ENV_MAP = {
    "openeo.dataspace.copernicus.eu": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED",
    "openeofed.dataspace.copernicus.eu": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED",
    "openeo.vito.be": "OPENEO_AUTH_CLIENT_CREDENTIALS_OPENEO_VITO",
}


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

    def _setup_connection(self, url: str) -> openeo.Connection:
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
        provider_id, client_id, client_secret = self._get_client_credentials(url)

        connection.authenticate_oidc_client_credentials(
            provider_id=provider_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        self._connection_cache[url] = connection
        return connection

    def _get_client_credentials(self, url: str) -> tuple[str, str, str]:
        """
        Get client credentials for the OpenEO backend.
        This method retrieves the client credentials from environment variables.

        :param url: The URL of the OpenEO backend.
        :return: A tuple containing provider ID, client ID, and client secret.
        """
        env_var = self._get_client_credentials_env_var(url)
        credentials_str = os.getenv(env_var)

        if not credentials_str:
            raise ValueError(f"Environment variable {env_var} not set.")

        parts = credentials_str.split("/", 2)
        if len(parts) != 3:
            raise ValueError(
                f"Invalid client credentials format in {env_var},"
                "expected 'provider_id/client_id/client_secret'."
            )
        provider_id, client_id, client_secret = parts
        return provider_id, client_id, client_secret

    def _get_client_credentials_env_var(self, url: str) -> str:
        """
        Get client credentials env var name for a given backend URL.
        """
        if not re.match(r"https?://", url):
            url = f"https://{url}"

        hostname = urllib.parse.urlparse(url).hostname
        if not hostname or hostname not in BACKEND_AUTH_ENV_MAP:
            raise ValueError(f"Unsupported backend: {url} (hostname={hostname})")

        return BACKEND_AUTH_ENV_MAP[hostname]

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

    def execute_job(self, title: str, details: ServiceDetails, parameters: dict) -> str:
        try:
            process_id = self._get_process_id(details.application)

            logger.debug(
                f"Executing OpenEO job with title={title}, service={details}, "
                f"process_id={process_id}, parameters={parameters}"
            )

            connection = self._setup_connection(details.endpoint)
            service = connection.datacube_from_process(
                process_id=process_id, namespace=details.application, **parameters
            )
            job = service.create_job(title=title)
            job.start()

            return job.job_id
        except Exception as e:
            logger.exception("Failed to execute openEO job")
            raise SystemError("Failed to execute openEO job") from e

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

    def get_job_status(
        self, job_id: str, details: ServiceDetails
    ) -> ProcessingStatusEnum:
        try:
            logger.debug(f"Fetching job status for openEO job with ID {job_id}")
            connection = self._setup_connection(details.endpoint)
            job = connection.job(job_id)
            return self._map_openeo_status(job.status())
        except Exception as e:
            logger.exception(f"Failed to fetch status for openEO job with ID {job_id}")
            raise SystemError(
                f"Failed to fetch status openEO job with ID {job_id}"
            ) from e

    def get_job_results(self, job_id: str, details: ServiceDetails) -> Collection:
        try:
            logger.debug(f"Fetching job result for openEO job with ID {job_id}")
            connection = self._setup_connection(details.endpoint)
            job = connection.job(job_id)
            return Collection(**job.get_results().get_metadata())
        except Exception as e:
            logger.exception(
                f"Failed to fetch result url for for openEO job with ID {job_id}"
            )
            raise SystemError(
                f"Failed to fetch result url for openEO job with ID {job_id}"
            ) from e
