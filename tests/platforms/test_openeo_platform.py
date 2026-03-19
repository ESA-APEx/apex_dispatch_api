import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
import requests

from app.config.schemas import AuthMethod, BackendAuthConfig
from app.config.settings import settings
from app.error import AuthException
from app.platforms.implementations.openeo import (
    OpenEOPlatform,
)
from app.schemas.enum import OutputFormatEnum, ProcessingStatusEnum
from app.schemas.parameters import ParamTypeEnum, Parameter
from app.schemas.unit_job import ServiceDetails
from stac_pydantic import Collection

from openeo.rest import OpenEoApiError


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
    settings.backend_auth_config["https://openeo.dataspace.copernicus.eu"] = (
        BackendAuthConfig(
            client_credentials="cdse-provider123/cdse-client123/cdse-secret123",
            token_prefix="cdse-prefix",
            token_provider="cdse-provider",
        )
    )
    settings.backend_auth_config["https://openeo.vito.be"] = BackendAuthConfig(
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
@patch.object(
    OpenEOPlatform, "_transform_parameters", return_value={"param1": "value1"}
)
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(OpenEOPlatform, "_get_process_id", return_value="process123")
async def test_execute_job_success(
    mock_pid, mock_connect, mock_transform, platform, service_details
):
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
@patch.object(OpenEOPlatform, "_transform_parameters", return_value={})
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(
    OpenEOPlatform, "_get_process_id", side_effect=ValueError("Invalid process")
)
async def test_execute_job_process_id_failure(
    mock_pid, mock_connect, mock_transform, platform, service_details
):
    with pytest.raises(ValueError, match="Invalid process"):
        await platform.execute_job(
            user_token="fake_token",
            title="Test Job",
            details=service_details,
            parameters={},
            format=OutputFormatEnum.GEOTIFF,
        )


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_transform_parameters", return_value={})
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(
    OpenEOPlatform,
    "_build_datacube",
    side_effect=OpenEoApiError(message="Woops", code="Test", http_status_code=401),
)
async def test_execute_job_process_openeo_auth_error(
    mock_pid, mock_connect, mock_transform, platform, service_details
):
    with pytest.raises(AuthException, match="Authentication error"):
        await platform.execute_job(
            user_token="fake_token",
            title="Test Job",
            details=service_details,
            parameters={},
            format=OutputFormatEnum.GEOTIFF,
        )


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_transform_parameters", return_value={})
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(
    OpenEOPlatform,
    "_build_datacube",
    side_effect=OpenEoApiError(message="Woops", code="Test", http_status_code=500),
)
async def test_execute_job_process_openeo_error(
    mock_pid, mock_connect, mock_transform, platform, service_details
):
    with pytest.raises(OpenEoApiError, match="Woops"):
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
    result = await platform.get_job_status("foobar", "job123", details)
    assert result == ProcessingStatusEnum.UNKNOWN


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_refresh_connection", new_callable=AsyncMock)
@patch.object(OpenEOPlatform, "_setup_connection", new_callable=AsyncMock)
async def test_get_job_status_retries_after_auth_error(
    mock_setup_connection, mock_refresh_connection, platform
):
    first_job = MagicMock()
    first_job.status.side_effect = OpenEoApiError(
        message="expired", code="TokenExpired", http_status_code=401
    )

    second_job = MagicMock()
    second_job.status.return_value = "running"

    first_connection = MagicMock()
    first_connection.job.return_value = first_job
    second_connection = MagicMock()
    second_connection.job.return_value = second_job

    mock_setup_connection.side_effect = [first_connection, second_connection]
    mock_refresh_connection.return_value = second_connection

    details = ServiceDetails(endpoint="foo", application="bar")
    result = await platform.get_job_status("foobar", "job123", details)

    assert result == ProcessingStatusEnum.RUNNING
    assert mock_setup_connection.await_count == 2
    mock_refresh_connection.assert_awaited_once_with("foobar", details.endpoint)


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_refresh_connection", new_callable=AsyncMock)
@patch.object(OpenEOPlatform, "_setup_connection", new_callable=AsyncMock)
async def test_get_job_status_returns_unknown_when_refresh_fails(
    mock_setup_connection, mock_refresh_connection, platform
):
    first_job = MagicMock()
    first_job.status.side_effect = OpenEoApiError(
        message="expired", code="TokenExpired", http_status_code=401
    )

    first_connection = MagicMock()
    first_connection.job.return_value = first_job

    mock_setup_connection.return_value = first_connection
    mock_refresh_connection.side_effect = RuntimeError("refresh failed")

    details = ServiceDetails(endpoint="foo", application="bar")
    result = await platform.get_job_status("foobar", "job123", details)

    assert result == ProcessingStatusEnum.UNKNOWN
    mock_setup_connection.assert_awaited_once_with("foobar", details.endpoint)
    mock_refresh_connection.assert_awaited_once_with("foobar", details.endpoint)


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection", new_callable=AsyncMock)
async def test_get_job_status_non_auth_openeo_error_returns_unknown(
    mock_setup_connection, platform
):
    job = MagicMock()
    job.status.side_effect = OpenEoApiError(
        message="server-error", code="ServerError", http_status_code=500
    )
    connection = MagicMock()
    connection.job.return_value = job
    mock_setup_connection.return_value = connection

    details = ServiceDetails(endpoint="foo", application="bar")
    result = await platform.get_job_status("foobar", "job123", details)

    assert result == ProcessingStatusEnum.UNKNOWN


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


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
async def test_get_job_results_openeo_auth_error(
    mock_connection, platform, service_details
):
    mock_connection.side_effect = OpenEoApiError(
        message="Woops", code="Test", http_status_code=401
    )
    details = ServiceDetails(endpoint="foo", application="bar")
    with pytest.raises(AuthException, match="Authentication error"):
        await platform.get_job_results("foobar", "job123", details)


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
async def test_get_job_results_openeo_error(mock_connection, platform, service_details):
    mock_connection.side_effect = OpenEoApiError(
        message="Woops", code="Test", http_status_code=500
    )
    details = ServiceDetails(endpoint="foo", application="bar")
    with pytest.raises(OpenEoApiError, match="Woops"):
        await platform.get_job_results("foobar", "job123", details)


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
    "app.platforms.implementations.openeo.exchange_token",
    new_callable=AsyncMock,
)
async def test_authenticate_user_with_user_credentials(mock_exchange, platform):
    url = "https://openeo.vito.be"

    # enable user credentials path
    settings.backend_auth_config[url].auth_method = AuthMethod.USER_CREDENTIALS

    # set up a fake connection with the expected method
    conn = MagicMock()
    conn.authenticate_bearer_token = MagicMock()

    # prepare the exchange mock to return the exchanged token
    mock_exchange.return_value = "vito-prefix/exchanged-token"

    # choose a url that maps via BACKEND_PROVIDER_ID_MAP (hostname only)
    returned = await platform._authenticate_user("user-token", url, conn)

    # assertions
    mock_exchange.assert_awaited_once_with(user_token="user-token", url=url)
    conn.authenticate_bearer_token.assert_called_once_with(
        bearer_token="vito-prefix/exchanged-token"
    )
    assert returned is conn


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token",
    new_callable=AsyncMock,
)
async def test_authenticate_user_with_client_credentials(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.backend_auth_config[url].auth_method = AuthMethod.CLIENT_CREDENTIALS

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
    "app.platforms.implementations.openeo.exchange_token",
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
    "app.platforms.implementations.openeo.exchange_token",
    new_callable=AsyncMock,
)
async def test_authenticate_user_config_unsupported_method(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.backend_auth_config[url].auth_method = "FOOBAR"

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # ensure the exchange mock exists but is not awaited
    with pytest.raises(ValueError, match="Unsupported OpenEO authentication method"):
        await platform._authenticate_user("user-token", url, conn)

    mock_exchange.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "app.platforms.implementations.openeo.exchange_token",
    new_callable=AsyncMock,
)
async def test_authenticate_user_config_missing_credentials(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.backend_auth_config[url].auth_method = AuthMethod.CLIENT_CREDENTIALS
    settings.backend_auth_config[url].client_credentials = None

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
    "app.platforms.implementations.openeo.exchange_token",
    new_callable=AsyncMock,
)
async def test_authenticate_user_config_format_issue_credentials(
    mock_exchange, monkeypatch, platform
):
    url = "https://openeo.vito.be"
    # disable user credentials path -> use client credentials
    settings.backend_auth_config[url].auth_method = AuthMethod.CLIENT_CREDENTIALS
    settings.backend_auth_config[url].client_credentials = "foobar"

    # prepare fake connection and spy method
    conn = MagicMock()
    conn.authenticate_oidc_client_credentials = MagicMock()

    # ensure the exchange mock exists but is not awaited
    with pytest.raises(ValueError, match="Invalid client credentials format for"):
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
    cache_key = platform._build_connection_cache_key("user-token", url)
    assert platform._connection_cache[cache_key] is mock_conn


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_connection_expired", return_value=False)
@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_authenticate_user", new_callable=AsyncMock)
async def test_setup_connection_uses_cache_if_not_expired(
    mock_auth, mock_connect, mock_expired, platform
):
    platform._connection_cache = {}
    url = "https://example.backend"
    cached_conn = MagicMock()
    cache_key = platform._build_connection_cache_key("user-token", url)
    platform._connection_cache[cache_key] = cached_conn

    conn = await platform._setup_connection("user-token", url)

    # cache used, no new connect or authenticate calls
    assert conn is cached_conn
    mock_expired.assert_called_once_with(cached_conn)
    mock_connect.assert_not_called()
    mock_auth.assert_not_awaited()


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_connection_expired", return_value=True)
@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_authenticate_user", new_callable=AsyncMock)
async def test_setup_connection_recreates_if_expired(
    mock_auth, mock_connect, mock_expired, platform
):
    platform._connection_cache = {}
    url = "https://example.backend"
    old_conn = MagicMock()
    new_conn = MagicMock()
    cache_key = platform._build_connection_cache_key("user-token", url)
    platform._connection_cache[cache_key] = old_conn

    mock_connect.return_value = new_conn
    mock_auth.return_value = new_conn

    conn = await platform._setup_connection("user-token", url)

    mock_connect.assert_called_once_with(url)
    mock_auth.assert_awaited_once_with("user-token", url, new_conn)
    assert conn is new_conn
    assert platform._connection_cache[cache_key] is new_conn


@pytest.mark.asyncio
@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_authenticate_user", new_callable=AsyncMock)
async def test_setup_connection_force_refresh_bypasses_cache(
    mock_auth, mock_connect, platform
):
    platform._connection_cache = {}
    url = "https://example.backend"
    old_conn = MagicMock()
    new_conn = MagicMock()
    cache_key = platform._build_connection_cache_key("user-token", url)
    platform._connection_cache[cache_key] = old_conn

    mock_connect.return_value = new_conn
    mock_auth.return_value = new_conn

    conn = await platform._setup_connection("user-token", url, force_refresh=True)

    mock_connect.assert_called_once_with(url)
    mock_auth.assert_awaited_once_with("user-token", url, new_conn)
    assert conn is new_conn
    assert platform._connection_cache[cache_key] is new_conn


@pytest.mark.asyncio
@patch("app.platforms.implementations.openeo.openeo.connect")
@patch.object(OpenEOPlatform, "_authenticate_user", new_callable=AsyncMock)
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
    cache_key = platform._build_connection_cache_key("user-token", url)
    assert cache_key not in platform._connection_cache


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


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_transform_parameters", return_value={})
@patch.object(OpenEOPlatform, "_build_datacube", new_callable=AsyncMock)
@patch.object(OpenEOPlatform, "_refresh_connection", new_callable=AsyncMock)
async def test_execute_job_retries_after_auth_error(
    mock_refresh_connection,
    mock_build_datacube,
    mock_transform,
    platform,
    service_details,
):
    first_service = MagicMock()
    first_job = MagicMock()
    first_job.start.side_effect = OpenEoApiError(
        message="expired", code="TokenExpired", http_status_code=401
    )
    first_service.create_job.return_value = first_job

    second_service = MagicMock()
    second_job = MagicMock()
    second_job.job_id = "job-retried"
    second_service.create_job.return_value = second_job

    mock_build_datacube.side_effect = [first_service, second_service]

    job_id = await platform.execute_job(
        user_token="fake_token",
        title="Retry Job",
        details=service_details,
        parameters={},
        format=OutputFormatEnum.GEOTIFF,
    )

    assert job_id == "job-retried"
    assert mock_build_datacube.await_count == 2
    mock_refresh_connection.assert_awaited_once_with(
        "fake_token", service_details.endpoint
    )


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_refresh_connection", new_callable=AsyncMock)
async def test_get_job_results_retries_after_auth_error(
    mock_refresh_connection, platform, service_details, fake_result
):
    first_job = MagicMock()
    first_job.get_results.side_effect = OpenEoApiError(
        message="expired", code="TokenExpired", http_status_code=401
    )

    second_metadata = fake_result.model_dump()
    second_job = MagicMock()
    second_job.get_results.return_value.get_metadata.return_value = second_metadata

    first_conn = MagicMock()
    first_conn.job.return_value = first_job
    second_conn = MagicMock()
    second_conn.job.return_value = second_job

    with patch.object(
        OpenEOPlatform, "_setup_connection", new_callable=AsyncMock
    ) as mock_setup:
        mock_setup.side_effect = [first_conn, second_conn, second_conn]

        result = await platform.get_job_results("fake_token", "job-1", service_details)

    assert result == fake_result
    mock_refresh_connection.assert_awaited_once_with(
        "fake_token", service_details.endpoint
    )


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(
    OpenEOPlatform,
    "_build_datacube",
    side_effect=OpenEoApiError(message="Woops", code="Test", http_status_code=401),
)
async def test_execute_sync_job_openeo_auth_error(
    mock_pid, mock_connect, platform, service_details
):
    with pytest.raises(AuthException, match="Authentication error"):
        await platform.execute_synchronous_job(
            user_token="fake_token",
            title="Test Job",
            details=service_details,
            parameters={},
            format=OutputFormatEnum.GEOTIFF,
        )


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(
    OpenEOPlatform,
    "_build_datacube",
    side_effect=OpenEoApiError(message="Woops", code="Test", http_status_code=500),
)
async def test_execute_sync_job_openeo_error(
    mock_pid, mock_connect, platform, service_details
):
    with pytest.raises(OpenEoApiError, match="Woops"):
        await platform.execute_synchronous_job(
            user_token="fake_token",
            title="Test Job",
            details=service_details,
            parameters={},
            format=OutputFormatEnum.GEOTIFF,
        )


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "_setup_connection")
@patch.object(
    OpenEOPlatform,
    "_build_datacube",
    side_effect=RuntimeError("Woops"),
)
async def test_execute_sync_job_error(
    mock_pid, mock_connect, platform, service_details
):
    with pytest.raises(RuntimeError, match="Woops"):
        await platform.execute_synchronous_job(
            user_token="fake_token",
            title="Test Job",
            details=service_details,
            parameters={},
            format=OutputFormatEnum.GEOTIFF,
        )


@pytest.mark.asyncio
@patch("app.platforms.implementations.openeo.requests.get")
async def test_get_parameters_success(mock_udp_request, platform):

    udp_params = [
        {
            "name": "flag_test",
            "description": "Test for a boolean flag parameter",
            "schema": {"type": "boolean"},
        },
        {
            "name": "polygon_test",
            "description": "Test for a polygon parameter",
            "schema": {"type": "object", "subtype": "geojson"},
        },
        {
            "name": "bbox_test",
            "description": "Test for a bbox parameter",
            "schema": {"type": "object", "subtype": "bounding-box"},
        },
        {
            "name": "date_test",
            "description": "Test for a date parameter",
            "schema": {"type": "array", "subtype": "temporal-interval"},
            "optional": True,
            "default": ["2020-01-01", "2020-12-31"],
        },
        {
            "name": "string_test",
            "description": "Test for a string parameter",
            "schema": {"type": "string"},
        },
        {
            "name": "int_test",
            "description": "Test for a integer parameter",
            "schema": {"type": "integer"},
        },
        {
            "name": "array_string_test",
            "description": "Test for an array of strings parameter",
            "schema": {"type": "array", "items": {"type": "string"}},
        },
        {
            "name": "number_test",
            "description": "Test for a number parameter",
            "schema": {"type": "number"},
        },
    ]
    mock_udp_request.return_value.json.return_value = {
        "id": "process123",
        "parameters": udp_params,
    }
    mock_udp_request.return_value.raise_for_status.return_value = None
    result = await platform.get_service_parameters(
        user_token="fake_token",
        details=ServiceDetails(
            endpoint="https://openeo.dataspace.copernicus.eu",
            application="https://foo.bar/process.json",
        ),
    )
    parameters = [
        Parameter(
            name=udp_params[0]["name"],
            description=udp_params[0]["description"],
            type=ParamTypeEnum.BOOLEAN,
            optional=False,
        ),
        Parameter(
            name=udp_params[1]["name"],
            description=udp_params[1]["description"],
            type=ParamTypeEnum.POLYGON,
            optional=False,
        ),
        Parameter(
            name=udp_params[2]["name"],
            description=udp_params[2]["description"],
            type=ParamTypeEnum.BOUNDING_BOX,
            optional=False,
        ),
        Parameter(
            name=udp_params[3]["name"],
            description=udp_params[3]["description"],
            type=ParamTypeEnum.DATE_INTERVAL,
            optional=True,
            default=udp_params[3]["default"],
        ),
        Parameter(
            name=udp_params[4]["name"],
            description=udp_params[4]["description"],
            type=ParamTypeEnum.STRING,
            optional=False,
        ),
        Parameter(
            name=udp_params[5]["name"],
            description=udp_params[5]["description"],
            type=ParamTypeEnum.INTEGER,
            optional=False,
        ),
        Parameter(
            name=udp_params[6]["name"],
            description=udp_params[6]["description"],
            type=ParamTypeEnum.ARRAY_STRING,
            optional=False,
        ),
        Parameter(
            name=udp_params[7]["name"],
            description=udp_params[7]["description"],
            type=ParamTypeEnum.INTEGER,
            optional=False,
        ),
    ]
    assert result == parameters


@pytest.mark.asyncio
@patch("app.platforms.implementations.openeo.requests.get")
async def test_get_parameters_unsupported_type(mock_udp_request, platform):

    mock_udp_request.return_value.json.return_value = {
        "id": "process123",
        "parameters": [
            {
                "name": "foobar_test",
                "description": "Test for a foobar parameter",
                "schema": {"type": "foobar"},
            }
        ],
    }
    mock_udp_request.return_value.raise_for_status.return_value = None

    with pytest.raises(ValueError, match="Unsupported parameter schemas"):
        await platform.get_service_parameters(
            user_token="fake_token",
            details=ServiceDetails(
                endpoint="https://openeo.dataspace.copernicus.eu",
                application="https://foo.bar/process.json",
            ),
        )


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "get_service_parameters", new_callable=AsyncMock)
async def test_transform_parameters_bbox_polygon_to_bbox(
    mock_get_service_parameters, platform, service_details
):
    mock_get_service_parameters.return_value = [
        Parameter(
            name="area",
            description="Area of interest",
            type=ParamTypeEnum.BOUNDING_BOX,
            optional=False,
        )
    ]

    parameters = {
        "area": {
            "type": "Polygon",
            "coordinates": [
                [
                    [3.0, 50.0],
                    [5.0, 50.0],
                    [5.0, 52.0],
                    [3.0, 52.0],
                    [3.0, 50.0],
                ]
            ],
        },
        "other": "untouched",
    }

    result = await platform._transform_parameters(
        user_token="fake-token", details=service_details, parameters=parameters
    )

    assert result == {
        "area": {"west": 3.0, "south": 50.0, "east": 5.0, "north": 52.0},
        "other": "untouched",
    }
    assert parameters["area"]["type"] == "Polygon"


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "get_service_parameters", new_callable=AsyncMock)
async def test_transform_parameters_passthrough_when_not_applicable(
    mock_get_service_parameters, platform, service_details
):
    mock_get_service_parameters.return_value = [
        Parameter(
            name="date",
            description="Date interval",
            type=ParamTypeEnum.DATE_INTERVAL,
            optional=True,
        ),
        Parameter(
            name="bbox_param",
            description="Bounding box",
            type=ParamTypeEnum.BOUNDING_BOX,
            optional=False,
        ),
    ]

    parameters = {
        "date": ["2024-01-01", "2024-12-31"],
        "other": "unchanged",
    }

    result = await platform._transform_parameters(
        user_token="fake-token", details=service_details, parameters=parameters
    )

    assert result == parameters


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "get_service_parameters", new_callable=AsyncMock)
async def test_transform_parameters_raises_for_unsupported_geojson_type(
    mock_get_service_parameters, platform, service_details
):
    mock_get_service_parameters.return_value = [
        Parameter(
            name="area",
            description="Area of interest",
            type=ParamTypeEnum.BOUNDING_BOX,
            optional=False,
        )
    ]

    parameters = {
        "area": {
            "type": "Point",
            "coordinates": [4.0, 51.0],
        }
    }

    with pytest.raises(ValueError, match="Unsupported GeoJSON type"):
        await platform._transform_parameters(
            user_token="fake-token", details=service_details, parameters=parameters
        )


@pytest.mark.asyncio
@patch.object(OpenEOPlatform, "get_service_parameters", new_callable=AsyncMock)
async def test_transform_parameters_raises_for_invalid_polygon_coordinates(
    mock_get_service_parameters, platform, service_details
):
    mock_get_service_parameters.return_value = [
        Parameter(
            name="area",
            description="Area of interest",
            type=ParamTypeEnum.BOUNDING_BOX,
            optional=False,
        )
    ]

    parameters = {
        "area": {
            "type": "Polygon",
            "coordinates": [],
        }
    }

    with pytest.raises(ValueError, match="Invalid GeoJSON geometry"):
        await platform._transform_parameters(
            user_token="fake-token", details=service_details, parameters=parameters
        )
