import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
from fastapi import status

from app.auth import exchange_token, _exchange_token_for_provider
from app.config.settings import settings
from app.config.schemas import BackendAuthConfig, AuthMethod
from app.error import AuthException


# Tests for exchange_token function
@pytest.mark.asyncio
async def test_exchange_token_missing_provider():

    url = "https://openeo.vito.be"
    original_config = settings.backend_auth_config.get(url)

    try:
        # Create a config without token_provider
        settings.backend_auth_config[url] = BackendAuthConfig(
            auth_method=AuthMethod.USER_CREDENTIALS,
            token_provider=None,
            token_prefix="Bearer",
        )

        with pytest.raises(ValueError, match="must define"):
            await exchange_token("user-token", url)
    finally:
        # Restore original config
        if original_config:
            settings.backend_auth_config[url] = original_config


@pytest.mark.asyncio
async def test_exchange_token_missing_token_prefix():
    url = "https://openeo.vito.be"
    original_config = settings.backend_auth_config.get(url)

    try:
        # Create a config without token_prefix
        settings.backend_auth_config[url] = BackendAuthConfig(
            auth_method=AuthMethod.USER_CREDENTIALS,
            token_provider="openeo",
            token_prefix=None,
        )

        with pytest.raises(ValueError, match="must define"):
            await exchange_token("user-token", url)
    finally:
        # Restore original config
        if original_config:
            settings.backend_auth_config[url] = original_config


@pytest.mark.asyncio
@patch(
    "app.auth._exchange_token_for_provider",
    new_callable=AsyncMock,
)
async def test_exchange_token_success_with_prefix(mock_exchange):
    url = "https://openeo.vito.be"
    original_config = settings.backend_auth_config.get(url)

    try:
        settings.backend_auth_config[url] = BackendAuthConfig(
            auth_method=AuthMethod.USER_CREDENTIALS,
            token_provider="openeo",
            token_prefix="Bearer",
        )

        mock_exchange.return_value = {"access_token": "exchanged-token-123"}

        result = await exchange_token("user-token", url)

        assert result == "Bearer/exchanged-token-123"
        mock_exchange.assert_called_once_with(
            initial_token="user-token",
            provider="openeo",
        )
    finally:
        if original_config:
            settings.backend_auth_config[url] = original_config


# Tests for _exchange_token_for_provider function
@pytest.mark.asyncio
async def test_exchange_token_for_provider_missing_client_credentials():
    original_client_id = settings.keycloak_client_id
    original_client_secret = settings.keycloak_client_secret

    try:
        settings.keycloak_client_id = ""
        settings.keycloak_client_secret = ""

        with pytest.raises(AuthException) as exc_info:
            await _exchange_token_for_provider("token", "openeo")

        assert exc_info.value.http_status == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "not configured" in exc_info.value.message
    finally:
        settings.keycloak_client_id = original_client_id
        settings.keycloak_client_secret = original_client_secret


@pytest.mark.asyncio
@patch(
    "app.auth.httpx.AsyncClient",
)
async def test_exchange_token_for_provider_network_error(mock_client_class):
    original_client_id = settings.keycloak_client_id
    original_client_secret = settings.keycloak_client_secret

    try:
        settings.keycloak_client_id = "test-client"
        settings.keycloak_client_secret = "test-secret"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.RequestError("Network error")
        mock_client_class.return_value = mock_client

        with pytest.raises(AuthException) as exc_info:
            await _exchange_token_for_provider("token", "openeo")

        assert exc_info.value.http_status == status.HTTP_502_BAD_GATEWAY
        assert "Could not authenticate" in exc_info.value.message
    finally:
        settings.keycloak_client_id = original_client_id
        settings.keycloak_client_secret = original_client_secret


@pytest.mark.asyncio
@patch(
    "app.auth.httpx.AsyncClient",
)
async def test_exchange_token_for_provider_invalid_json_response(mock_client_class):
    original_client_id = settings.keycloak_client_id
    original_client_secret = settings.keycloak_client_secret

    try:
        settings.keycloak_client_id = "test-client"
        settings.keycloak_client_secret = "test-secret"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        # Mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(AuthException) as exc_info:
            await _exchange_token_for_provider("token", "openeo")

        assert exc_info.value.http_status == status.HTTP_502_BAD_GATEWAY
        assert "Could not authenticate" in exc_info.value.message
    finally:
        settings.keycloak_client_id = original_client_id
        settings.keycloak_client_secret = original_client_secret


@pytest.mark.asyncio
@patch(
    "app.auth.httpx.AsyncClient",
)
async def test_exchange_token_for_provider_token_exchange_failed(mock_client_class):
    original_client_id = settings.keycloak_client_id
    original_client_secret = settings.keycloak_client_secret

    try:
        settings.keycloak_client_id = "test-client"
        settings.keycloak_client_secret = "test-secret"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        # Mock response with 401 error
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": "unauthorized",
            "error_description": "Invalid credentials",
        }
        mock_response.text = "Unauthorized"
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(AuthException) as exc_info:
            await _exchange_token_for_provider("token", "openeo")

        assert exc_info.value.http_status == status.HTTP_401_UNAUTHORIZED
        assert "Could not authenticate" in exc_info.value.message
    finally:
        settings.keycloak_client_id = original_client_id
        settings.keycloak_client_secret = original_client_secret


@pytest.mark.asyncio
@patch(
    "app.auth.httpx.AsyncClient",
)
async def test_exchange_token_for_provider_account_not_linked(mock_client_class):
    original_client_id = settings.keycloak_client_id
    original_client_secret = settings.keycloak_client_secret

    try:
        settings.keycloak_client_id = "test-client"
        settings.keycloak_client_secret = "test-secret"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        # Mock response with not_linked error
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "not_linked",
            "error_description": "Account not linked",
        }
        mock_response.text = "Bad Request"
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(AuthException) as exc_info:
            await _exchange_token_for_provider("token", "openeo")

        assert exc_info.value.http_status == status.HTTP_401_UNAUTHORIZED
        assert "link your account" in exc_info.value.message
        assert "Account Dashboard" in exc_info.value.message
    finally:
        settings.keycloak_client_id = original_client_id
        settings.keycloak_client_secret = original_client_secret


@pytest.mark.asyncio
@patch(
    "app.auth.httpx.AsyncClient",
)
async def test_exchange_token_for_provider_success(mock_client_class):
    original_client_id = settings.keycloak_client_id
    original_client_secret = settings.keycloak_client_secret

    try:
        settings.keycloak_client_id = "test-client"
        settings.keycloak_client_secret = "test-secret"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-platform-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = await _exchange_token_for_provider("user-token", "openeo")

        assert result["access_token"] == "new-platform-token"
        assert result["expires_in"] == 3600
        assert result["token_type"] == "Bearer"
    finally:
        settings.keycloak_client_id = original_client_id
        settings.keycloak_client_secret = original_client_secret
