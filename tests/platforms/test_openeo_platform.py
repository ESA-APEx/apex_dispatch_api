import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
import requests

from app.config.settings import settings
from app.platforms.implementations.openeo import (
    BACKEND_AUTH_ENV_MAP,
    BACKEND_PROVIDER_ID_MAP,
    OpenEOPlatform,
)
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
    env_var = platform._get_backend_config(
        BACKEND_AUTH_ENV_MAP, "https://openeo.dataspace.copernicus.eu"
    )
    assert env_var == "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED"


def test_get_client_credentials_env_var_unsupported_backend(platform):
    with pytest.raises(ValueError, match="Unsupported backend"):
        platform._get_backend_config(
            BACKEND_AUTH_ENV_MAP, "https://unsupported.example.com"
        )


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


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(OpenEOPlatform, "_get_process_id", return_value="process123")
async def test_execute_job_success(mock_pid, mock_connect, platform, service_details):
    mock_connection = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.datacube_from_process.return_value.create_job.return_value.job_id = (
        "job123"
    )

    job_id = await platform.execute_job(
        user_token="fake_token",
        title="Test Job",
        details=service_details,
        parameters={"param1": "value1"},
        format=OutputFormatEnum.GEOTIFF,
    )

    assert job_id == "job123"
    mock_connect.assert_called_once_with("fake_token", service_details.endpoint)


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(
    OpenEOPlatform, "_get_process_id", side_effect=ValueError("Invalid process")
)
async def test_execute_job_process_id_failure(
    mock_pid, mock_connect, platform, service_details
):
    with pytest.raises(ValueError, match="Invalid process"):
        await platform.execute_job(
            user_token="fake_token",
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


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
async def test_get_job_status_success(mock_connection, platform):
    mock_connection.return_value = DummyOpenEOClient()

    details = ServiceDetails(endpoint="foo", application="bar")
    result = await platform.get_job_status("foobar", "job123", details)

    assert result == ProcessingStatusEnum.RUNNING


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
async def test_get_job_status_error(mock_connection, platform):
    mock_connection.side_effect = RuntimeError("Connection error")

    details = ServiceDetails(endpoint="foo", application="bar")
    with pytest.raises(RuntimeError) as exc_info:
        await platform.get_job_status("foobar", "job123", details)

    assert "Connection error" in str(exc_info.value)


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
async def test_get_job_results_success(mock_connection, platform, fake_result):
    mock_connection.return_value = DummyOpenEOClient(result=fake_result)

    details = ServiceDetails(endpoint="foo", application="bar")
    result = await platform.get_job_results("foobar", "job123", details)

    assert result == fake_result


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
async def test_get_job_results_error(mock_connection, platform):
    mock_connection.side_effect = RuntimeError("Connection error")

    details = ServiceDetails(endpoint="foo", application="bar")
    with pytest.raises(RuntimeError) as exc_info:
        await platform.get_job_results("foobar", "job123", details)

    assert "Connection error" in str(exc_info.value)


def _make_conn_with_token(token: str):
    # openeo.Connection-like object with auth.bearer that the implementation splits on '/'
    return SimpleNamespace(auth=SimpleNamespace(bearer=f"prefix/{token}"))


def test_connection_expired_no_exp(platform):
    # token with no 'exp' claim
    token = jwt.encode({"sub": "user"}, "secret", algorithm="HS256")
    conn = _make_conn_with_token(token)
    assert platform._connection_expired(conn) is True


def test_connection_expired_future_exp(platform):
    exp = int(
        (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        ).timestamp()
    )
    token = jwt.encode({"sub": "user", "exp": exp}, "secret", algorithm="HS256")
    conn = _make_conn_with_token(token)
    assert platform._connection_expired(conn) is False


def test_connection_expired_past_exp(platform):
    exp = int(
        (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        ).timestamp()
    )
    token = jwt.encode({"sub": "user", "exp": exp}, "secret", algorithm="HS256")
    conn = _make_conn_with_token(token)
    assert platform._connection_expired(conn) is True


def test_connection_expired_no_bearer(platform):
    conn = SimpleNamespace(auth=SimpleNamespace(bearer=""))
    assert platform._connection_expired(conn) is True


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_authenticate_user_with_user_credentials(
    mock_exchange, platform, monkeypatch
):
    # enable user credentials path
    monkeypatch.setattr(settings, "openeo_enable_user_credentials", True)

    # set up a fake connection with the expected method
    conn = MagicMock()
    conn.authenticate_bearer_token = MagicMock()

    # prepare the exchange mock to return the exchanged token
    mock_exchange.return_value = {"access_token": "exchanged-token"}

    # choose a url that maps via BACKEND_PROVIDER_ID_MAP (hostname only)
    url = "https://openeo.vito.be/some/path"
    returned = await platform._authenticate_user("user-token", url, conn)

    # assertions
    mock_exchange.assert_awaited_once_with(
        initial_token="user-token", provider=BACKEND_PROVIDER_ID_MAP["openeo.vito.be"]
    )
    conn.authenticate_bearer_token.assert_called_once_with(
        bearer_token="exchanged-token"
    )
    assert returned is conn


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_authenticate_user_with_client_credentials(
    mock_exchange, monkeypatch, platform
):
    # disable user credentials path -> use client credentials
    monkeypatch.setattr(settings, "openeo_enable_user_credentials", False)

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # patch _get_client_credentials to avoid env dependency
    monkeypatch.setattr(
        OpenEOPlatform,
        "_get_client_credentials",
        lambda self, url: ("prov-id", "client-id", "client-secret"),
    )

    # ensure the exchange mock exists but is not awaited
    url = "https://openeo.vito.be"
    returned = await platform._authenticate_user("user-token", url, conn)

    # client creds path should be used
    conn.authenticate_oidc_client_credentials.assert_called_once_with(
        provider_id="prov-id", client_id="client-id", client_secret="client-secret"
    )
    # token-exchange should not be awaited
    mock_exchange.assert_not_awaited()
    assert returned is conn


@pytest.mark.asyncio
@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_authenticate_user", new_callable=AsyncMock)
async def test_setup_connection_creates_and_caches(mock_auth, mock_connect, platform):
    platform._connection_cache = {}
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    mock_auth.return_value = mock_conn

    url = "https://example.backend"
    conn = await platform._setup_connection("user-token", url)

    mock_connect.assert_called_once_with(url)
    mock_auth.assert_awaited_once_with("user-token", url, mock_conn)
    assert conn is mock_conn
    assert platform._connection_cache[url] is mock_conn


@patch.object(OpenEOPlatform, "_connection_expired", return_value=False)
@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_authenticate_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_setup_connection_uses_cache_if_not_expired(
    mock_auth, mock_connect, mock_expired, platform
):
    platform._connection_cache = {}
    url = "https://example.backend"
    cached_conn = MagicMock()
    platform._connection_cache[url] = cached_conn

    conn = await platform._setup_connection("user-token", url)

    # cache used, no new connect or authenticate calls
    assert conn is cached_conn
    mock_expired.assert_called_once_with(cached_conn)
    mock_connect.assert_not_called()
    mock_auth.assert_not_awaited()


@patch.object(OpenEOPlatform, "_connection_expired", return_value=True)
@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_authenticate_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_setup_connection_recreates_if_expired(
    mock_auth, mock_connect, mock_expired, platform
):
    platform._connection_cache = {}
    url = "https://example.backend"
    old_conn = MagicMock()
    new_conn = MagicMock()
    platform._connection_cache[url] = old_conn

    mock_connect.return_value = new_conn
    mock_auth.return_value = new_conn

    conn = await platform._setup_connection("user-token", url)

    mock_connect.assert_called_once_with(url)
    mock_auth.assert_awaited_once_with("user-token", url, new_conn)
    assert conn is new_conn
    assert platform._connection_cache[url] is new_conn


@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_authenticate_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_setup_connection_propagates_auth_error(
    mock_auth, mock_connect, platform
):
    platform._connection_cache = {}
    url = "https://example.backend"
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    mock_auth.side_effect = RuntimeError("authentication failed")

    with pytest.raises(RuntimeError, match="authentication failed"):
        await platform._setup_connection("user-token", url)

    # authenticate failed, connection must not be cached
    assert url not in platform._connection_cache
