
import logging
import os
import openeo
import re

import urllib

import requests

from app.platforms.base import BaseProcessingPlatform
from app.schemas import ProcessingJobSummary, ProcessingStatusEnum, ServiceDetails

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

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
        
        connection.authenticate_oidc_device()
                                    
        # connection.authenticate_oidc_client_credentials(
        #         provider_id=provider_id,
        #         client_id=client_id,
        #         client_secret=client_secret,
        # )
        return connection
        
    def _get_client_credentials(self, url: str) -> tuple[str, str, str]:
        """
        Get client credentials for the OpenEO backend.
        This method retrieves the client credentials from environment variables.
        
        :param url: The URL of the OpenEO backend.
        :return: A tuple containing provider ID, client ID, and client secret.
        """
        auth_env_var = self._get_client_credentials_env_var(url)
        if auth_env_var not in os.environ:
            raise ValueError(f"Environment variable {auth_env_var} not set.")
        
        client_credentials = os.environ[auth_env_var]
        return client_credentials.split("/", 2)
    
    def _get_client_credentials_env_var(self, url: str) -> str:
        """
        Get client credentials env var name for a given backend URL.
        """
        if not re.match(r"https?://", url):
            url = f"https://{url}"
        parsed = urllib.parse.urlparse(url)

        hostname = parsed.hostname
        if hostname in {
            "openeo.dataspace.copernicus.eu",
            "openeofed.dataspace.copernicus.eu",
        }:
            return "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED"
        else:
            raise ValueError(f"Unsupported backend: {url=} ({hostname=})")

    def _get_process_id(self, url: str) -> str:
        """        
        Get the process ID from a JSON file hosted at the given URL.
        
        :param url: The URL of the JSON file.
        :return: The process ID extracted from the JSON file.
        """
        logger.debug(f"Fetching process ID from {url}")
        response = requests.get(url).json()
        return response.get("id")

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
            if not process_id:
                raise ValueError(f"Process ID not found for service: {details.service}")
            
            logger.debug(f"Executing OpenEO job with title={title}, service={details}, process_id={process_id} and parameters={parameters}")
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
            raise Exception("Failed to execute openEO job")
