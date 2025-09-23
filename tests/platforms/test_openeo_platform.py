from unittest.mock import MagicMock, patch

import pytest
import requests

from app.platforms.implementations.openeo import OpenEOPlatform
from app.schemas.enum import OutputFormatEnum, ProcessingStatusEnum
from app.schemas.unit_job import ServiceDetails
from stac_pydantic import Collection


class DummyOpenEOClient:

    def __init__(self, result: Collection = None):
        self.fake_result = result

    def job(self, job_id):
        job = MagicMock()
        job.status.return_value = ProcessingStatusEnum.RUNNING
        job.get_results.return_value.get_metadata.return_value = (
            self.fake_result.model_dump() if self.fake_result else None
        )
        return job


@pytest.fixture
def platform():
    return OpenEOPlatform()


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    # Default environment variable for CDSEFED credentials
    monkeypatch.setenv(
        "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED", "provider123/client123/secret123"
    )


@pytest.fixture
def service_details():
    return ServiceDetails(
        endpoint="https://openeo.dataspace.copernicus.eu",
        application="https://example.com/process.json",
    )


def test_get_client_credentials_success(platform):
    creds = platform._get_client_credentials("https://openeo.dataspace.copernicus.eu")
    assert creds == ("provider123", "client123", "secret123")


def test_get_client_credentials_missing_env(platform, monkeypatch):
    monkeypatch.delenv("OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED")
    with pytest.raises(ValueError, match="not set"):
        platform._get_client_credentials("https://openeo.dataspace.copernicus.eu")


def test_get_client_credentials_invalid_format(platform, monkeypatch):
    monkeypatch.setenv("OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED", "invalid_format")
    with pytest.raises(ValueError, match="Invalid client credentials format"):
        platform._get_client_credentials("https://openeo.dataspace.copernicus.eu")


def test_get_client_credentials_env_var_success(platform):
    env_var = platform._get_client_credentials_env_var(
        "https://openeo.dataspace.copernicus.eu"
    )
    assert env_var == "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED"


def test_get_client_credentials_env_var_unsupported_backend(platform):
    with pytest.raises(ValueError, match="Unsupported backend"):
        platform._get_client_credentials_env_var("https://unsupported.example.com")


@patch("app.platforms.implementations.openeo.requests.get")
def test_get_process_id_success(mock_get, platform):
    mock_get.return_value.json.return_value = {"id": "process123"}
    mock_get.return_value.raise_for_status.return_value = None

    process_id = platform._get_process_id("https://example.com/process.json")
    assert process_id == "process123"


@patch("app.platforms.implementations.openeo.requests.get")
def test_get_process_id_no_id(mock_get, platform):
    mock_get.return_value.json.return_value = {}
    mock_get.return_value.raise_for_status.return_value = None

    with pytest.raises(ValueError, match="No 'id' field"):
        platform._get_process_id("https://example.com/process.json")


@patch("app.platforms.implementations.openeo.requests.get")
def test_get_process_id_http_error(mock_get, platform):
    mock_get.side_effect = requests.RequestException("Network error")
    with pytest.raises(ValueError, match="Failed to fetch process ID"):
        platform._get_process_id("https://example.com/process.json")


@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_get_process_id", return_value="process123")
def test_execute_job_success(mock_pid, mock_connect, platform, service_details):
    mock_connection = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.datacube_from_process.return_value.create_job.return_value.job_id = (
        "job123"
    )

    job_id = platform.execute_job(
        title="Test Job",
        details=service_details,
        parameters={"param1": "value1"},
        format=OutputFormatEnum.GEOTIFF,
    )

    assert job_id == "job123"
    mock_connect.assert_called_once_with(service_details.endpoint)


@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(
    OpenEOPlatform, "_get_process_id", side_effect=ValueError("Invalid process")
)
def test_execute_job_process_id_failure(
    mock_pid, mock_connect, platform, service_details
):
    with pytest.raises(SystemError, match="Failed to execute openEO job"):
        platform.execute_job(
            title="Test Job",
            details=service_details,
            parameters={},
            format=OutputFormatEnum.GEOTIFF,
        )


@pytest.mark.parametrize(
    "openeo_status, expected_enum",
    [
        ("created", ProcessingStatusEnum.CREATED),
        ("queued", ProcessingStatusEnum.QUEUED),
        ("running", ProcessingStatusEnum.RUNNING),
        ("cancelled", ProcessingStatusEnum.CANCELED),
        ("finished", ProcessingStatusEnum.FINISHED),
        ("error", ProcessingStatusEnum.FAILED),
        ("CrEaTeD", ProcessingStatusEnum.CREATED),  # Case insensitivity
        ("unknown_status", ProcessingStatusEnum.UNKNOWN),
        (None, ProcessingStatusEnum.UNKNOWN),
    ],
)
def test_map_openeo_status(openeo_status, expected_enum):
    platform = OpenEOPlatform()
    result = platform._map_openeo_status(openeo_status)
    assert result == expected_enum


@patch.object(OpenEOPlatform, "_setup_connection")
def test_get_job_status_success(mock_connection, platform):
    mock_connection.return_value = DummyOpenEOClient()

    details = ServiceDetails(endpoint="foo", application="bar")
    result = platform.get_job_status("job123", details)

    assert result == ProcessingStatusEnum.RUNNING


@patch.object(OpenEOPlatform, "_setup_connection")
def test_get_job_status_error(mock_connection, platform):
    mock_connection.side_effect = RuntimeError("Connection error")

    details = ServiceDetails(endpoint="foo", application="bar")
    with pytest.raises(SystemError) as exc_info:
        platform.get_job_status("job123", details)

    assert "Failed to fetch status" in str(exc_info.value)


@patch.object(OpenEOPlatform, "_setup_connection")
def test_get_job_results_success(mock_connection, platform, fake_result):
    mock_connection.return_value = DummyOpenEOClient(result=fake_result)

    details = ServiceDetails(endpoint="foo", application="bar")
    result = platform.get_job_results("job123", details)

    assert result == fake_result


@patch.object(OpenEOPlatform, "_setup_connection")
def test_get_job_results_error(mock_connection, platform):
    mock_connection.side_effect = RuntimeError("Connection error")

    details = ServiceDetails(endpoint="foo", application="bar")
    with pytest.raises(SystemError) as exc_info:
        platform.get_job_results("job123", details)

    assert "Failed to fetch result url" in str(exc_info.value)


@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_get_process_id", return_value="process123")
def test_execute_sync_job_success(
    mock_pid, mock_connect, fake_sync_job_response, platform, service_details
):
    mock_connection = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.datacube_from_process.return_value.execute.return_value = (
        fake_sync_job_response
    )

    result = platform.execute_synchronous_job(
        title="Test Job",
        details=service_details,
        parameters={"param1": "value1"},
        format=OutputFormatEnum.GEOTIFF,
    )

    assert result == fake_sync_job_response
    mock_connect.assert_called_once_with(service_details.endpoint)


@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(
    OpenEOPlatform, "_get_process_id", side_effect=ValueError("Invalid process")
)
def test_execute_sync_job_process_id_failure(
    mock_pid, mock_connect, platform, service_details
):
    with pytest.raises(SystemError, match="Failed to execute openEO sync request"):
        platform.execute_synchronous_job(
            title="Test Job",
            details=service_details,
            parameters={},
            format=OutputFormatEnum.GEOTIFF,
        )
