
import logging
import os
import re
import urllib

import openeo
import requests
from dotenv import load_dotenv

from app.platforms.base import BaseProcessingPlatform
from app.platforms.dispatcher import register_processing_platform
from app.schemas import (
    ProcessingJobSummary,
    ProcessingStatusEnum,
    ProcessType,
    ServiceDetails,
)

load_dotenv()
logger = logging.getLogger(__name__)

# Constants
BACKEND_AUTH_ENV_MAP = {
    "openeo.dataspace.copernicus.eu": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED",
    "openeofed.dataspace.copernicus.eu": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED",
}


class OpenEOPlatform(BaseProcessingPlatform):
    """
    OpenEO processing platform implementation.
    This class handles the execution of processing jobs on the OpenEO platform.
    """
    
    def _setup_connection(self, url: str) -> None:
        """
        Setup the connection to the OpenEO backend.
        This method can be used to initialize any required client or session.
        """
        logger.debug(f"Setting up OpenEO connection to {url}")
        connection = openeo.connect(url)
        provider_id, client_id, client_secret = self._get_client_credentials(url)
        
        # @TODO: Remove the line below as this is only for local testing
        # connection.authenticate_oidc_device()  
                                     
        connection.authenticate_oidc_client_credentials(
                provider_id=provider_id,
                client_id=client_id,
                client_secret=client_secret,
        )
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
                f"Invalid client credentials format in {env_var}, expected 'provider_id/client_id/client_secret'."
            )
        return tuple(parts)
    
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

    def execute_job(self, title: str, details: ServiceDetails , parameters: dict) -> ProcessingJobSummary:
        """
        Execute a processing job on the OpenEO platform with the given service ID and parameters.

        :param title: The title of the job to be executed.
        :param details: The service details containing the service ID and application.
        :param parameters: The parameters required for the job execution.
        :return: A ProcessingJobSummary object containing the job details.
        """
        
        try:
            process_id = self._get_process_id(details.application)
            
            logger.debug(
                f"Executing OpenEO job with title={title}, service={details}, "
                f"process_id={process_id}, parameters={parameters}"
            )
            
            connection = self._setup_connection(details.service)
            service = connection.datacube_from_process(
                process_id=process_id,
                namespace=details.application,
                **parameters
            )
            job = service.create_job(title=title)
            job.start()
            
            return ProcessingJobSummary(
                id=job.job_id,
                title=title,
                status=ProcessingStatusEnum.CREATED
            )
        except Exception as e:
            logger.exception(f"Failed to execute openEO job: {e}")  
            raise SystemError("Failed to execute openEO job")


register_processing_platform(ProcessType.OPENEO, OpenEOPlatform)