import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
import requests

from app.config.settings import settings
from app.config.openeo.settings import OpenEOBackendConfig, OpenEOAuthMethod
from app.platforms.implementations.openeo import (
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
    settings.openeo_backend_config["https://openeo.dataspace.copernicus.eu"] = (
        OpenEOBackendConfig(
            client_credentials="cdse-provider123/cdse-client123/cdse-secret123",
            token_prefix="cdse-prefix",
            token_provider="cdse-provider",
        )
    )
    settings.openeo_backend_config["https://openeo.vito.be"] = OpenEOBackendConfig(
        client_credentials="vito-provider123/vito-client123/vito-secret123",
        token_prefix="vito-prefix",
        token_provider="vito-provider",
    )


@pytest.fixture
def service_details():
    return ServiceDetails(
        endpoint="https://openeo.dataspace.copernicus.eu",
        application="https://example.com/process.json",
    )


def test_get_client_credentials_success(platform):
    creds = platform._get_client_credentials("https://openeo.dataspace.copernicus.eu")
    assert creds == ("cdse-provider123", "cdse-client123", "cdse-secret123")


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


@patch("app.platforms.implementations.openeo.jwt.decode")
def test_connection_expired_exception(mock_decode, platform):
    mock_decode.side_effect = jwt.DecodeError("Invalid token")
    exp = int(
        (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        ).timestamp()
    )
    token = jwt.encode({"sub": "user", "exp": exp}, "secret", algorithm="HS256")
    conn = _make_conn_with_token(token)
    assert platform._connection_expired(conn) is True


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_authenticate_user_with_user_credentials(mock_exchange, platform):
    url = "https://openeo.vito.be"

    # enable user credentials path
    settings.openeo_backend_config[url].auth_method = OpenEOAuthMethod.USER_CREDENTIALS

    # set up a fake connection with the expected method
    conn = MagicMock()
    conn.authenticate_bearer_token = MagicMock()

    # prepare the exchange mock to return the exchanged token
    mock_exchange.return_value = {"access_token": "exchanged-token"}

    # choose a url that maps via BACKEND_PROVIDER_ID_MAP (hostname only)
    returned = await platform._authenticate_user("user-token", url, conn)

    # assertions
    mock_exchange.assert_awaited_once_with(
        initial_token="user-token", provider="vito-provider"
    )
    conn.authenticate_bearer_token.assert_called_once_with(
        bearer_token="vito-prefix/exchanged-token"
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
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.openeo_backend_config[url].auth_method = (
        OpenEOAuthMethod.CLIENT_CREDENTIALS
    )

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # ensure the exchange mock exists but is not awaited
    returned = await platform._authenticate_user("user-token", url, conn)

    # client creds path should be used
    conn.authenticate_oidc_client_credentials.assert_called_once_with(
        provider_id="vito-provider123",
        client_id="vito-client123",
        client_secret="vito-secret123",
    )
    # token-exchange should not be awaited
    mock_exchange.assert_not_awaited()
    assert returned is conn


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_authenticate_user_config_missing_url(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.foo.bar"

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # ensure the exchange mock exists but is not awaited
    with pytest.raises(
        ValueError, match="No OpenEO backend configuration found for URL"
    ):
        await platform._authenticate_user("user-token", url, conn)

    mock_exchange.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_authenticate_user_config_unsupported_method(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.openeo_backend_config[url].auth_method = "FOOBAR"

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # ensure the exchange mock exists but is not awaited
    with pytest.raises(
        ValueError, match="No OpenEO backend configuration found for URL"
    ):
        await platform._authenticate_user("user-token", url, conn)

    mock_exchange.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_authenticate_user_config_missing_credentials(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.openeo_backend_config[url].auth_method = (
        OpenEOAuthMethod.CLIENT_CREDENTIALS
    )
    settings.openeo_backend_config[url].client_credentials = None

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # ensure the exchange mock exists but is not awaited
    with pytest.raises(
        ValueError, match="Client credentials not configured for OpenEO backend"
    ):
        await platform._authenticate_user("user-token", url, conn)

    mock_exchange.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_authenticate_user_config_format_issue_credentials(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.openeo_backend_config[url].auth_method = (
        OpenEOAuthMethod.CLIENT_CREDENTIALS
    )
    settings.openeo_backend_config[url].client_credentials = "foobar"

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # ensure the exchange mock exists but is not awaited
    with pytest.raises(ValueError, match="Invalid client credentials format for"):
        await platform._authenticate_user("user-token", url, conn)

    mock_exchange.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_authenticate_user_config_missing_provider(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.openeo_backend_config[url].token_provider = None

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # ensure the exchange mock exists but is not awaited
    with pytest.raises(ValueError, match="must define"):
        await platform._authenticate_user("user-token", url, conn)

    mock_exchange.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_authenticate_user_config_missing_prefix(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.openeo_backend_config[url].token_prefix = None

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # ensure the exchange mock exists but is not awaited
    with pytest.raises(ValueError, match="must define"):
        await platform._authenticate_user("user-token", url, conn)

    mock_exchange.assert_not_awaited()


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


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(OpenEOPlatform, "_get_process_id", return_value="process123")
async def test_execute_sync_job_success(
    mock_pid, mock_connect, platform, service_details
):
    mock_response = MagicMock()
    mock_response.content = '{"id": "foobar"}'
    mock_response.status_code = 200
    mock_connection = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.datacube_from_process.return_value.execute.return_value = (
        mock_response
    )
    response = await platform.execute_synchronous_job(
        user_token="fake_token",
        title="Test Job",
        details=service_details,
        parameters={"param1": "value1"},
        format=OutputFormatEnum.GEOTIFF,
    )

    assert response.status_code == mock_response.status_code
    assert json.loads(response.body) == json.loads(mock_response.content)
    mock_connect.assert_called_once_with("fake_token", service_details.endpoint)
