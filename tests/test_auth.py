import time

import jwt
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
from fastapi import status

from app.auth import (
    KEYCLOAK_BASE_URL,
    exchange_token,
    _retrieve_broker_token,
    get_current_user_claims,
    get_current_user_id,
)
from app.config.settings import settings
from app.config.schemas import BackendAuthConfig, AuthMethod
from app.error import AuthException


# Tests for exchange_token function
@patch("app.auth._decode_token")
def test_get_current_user_claims(mock_decode_token):
    mock_decode_token.return_value = {
        "sub": "user-123",
        "preferred_username": "alice",
    }

    result = get_current_user_claims("token")

    assert result == {
        "sub": "user-123",
        "preferred_username": "alice",
    }
    mock_decode_token.assert_called_once_with("token")


@patch("app.auth._decode_token")
def test_get_current_user_id(mock_decode_token):
    mock_decode_token.return_value = {
        "sub": "user-123",
        "preferred_username": "alice",
    }

    result = get_current_user_id("token")

    assert result == "user-123"
    mock_decode_token.assert_called_once_with("token")


@patch("app.auth.jwks_client")
def test_decode_token_accepts_audience_claim(mock_jwks_client):
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    mock_jwks_client.get_signing_key_from_jwt.return_value.key = key.public_key()
    token = jwt.encode(
        {
            "iss": KEYCLOAK_BASE_URL,
            "sub": "user-123",
            "aud": ["broker", "account"],
            "exp": int(time.time()) + 300,
        },
        key,
        algorithm="RS256",
    )

    assert get_current_user_claims(token)["sub"] == "user-123"


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
@patch(
    "app.auth._retrieve_broker_token",
    new_callable=AsyncMock,
)
async def test_exchange_token_success_with_prefix(mock_retrieve):
    url = "https://openeo.vito.be"
    original_config = settings.backend_auth_config.get(url)

    try:
        settings.backend_auth_config[url] = BackendAuthConfig(
            auth_method=AuthMethod.USER_CREDENTIALS,
            token_provider="openeo",
            token_prefix="Bearer",
        )

        mock_retrieve.return_value = "exchanged-token-123"

        result = await exchange_token("user-token", url)

        assert result == "Bearer/exchanged-token-123"
        mock_retrieve.assert_called_once_with(
            user_token="user-token",
            provider="openeo",
        )
    finally:
        if original_config:
            settings.backend_auth_config[url] = original_config


# Tests for _retrieve_broker_token (Keycloak broker token endpoint)
USER_TOKEN = "apex-user-token"
EXTERNAL_ISSUER = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"


def _jwt(exp_offset: int = 3600, iss: str = EXTERNAL_ISSUER) -> str:
    return jwt.encode(
        {"iss": iss, "sub": "user", "exp": int(time.time()) + exp_offset},
        "test-signing-key-for-unit-tests-only",
        algorithm="HS256",
    )


def _response(status_code: int, body=None, invalid_json: bool = False) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    if invalid_json:
        resp.json.side_effect = ValueError("Invalid JSON")
    else:
        resp.json.return_value = body
    return resp


def _mock_client(mock_client_class, response=None, side_effect=None) -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    if side_effect is not None:
        mock_client.get.side_effect = side_effect
    else:
        mock_client.get.return_value = response
    mock_client_class.return_value = mock_client
    return mock_client


def _assert_no_token_leak(message: str, *tokens: str) -> None:
    for token in tokens:
        assert token not in message


@pytest.mark.asyncio
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_success_uses_stored_expiration(mock_client_class):
    external = _jwt(exp_offset=-10)  # JWT exp ignored when accessTokenExpiration is present
    client = _mock_client(
        mock_client_class,
        _response(
            200,
            {
                "access_token": external,
                "expires_in": 600,
                "refresh_token": "external-refresh-token",
                "token_type": "Bearer",
                "accessTokenExpiration": int(time.time()) + 600,
            },
        ),
    )

    result = await _retrieve_broker_token(USER_TOKEN, "cdse")

    assert result == external
    client.get.assert_called_once_with(
        f"{KEYCLOAK_BASE_URL}/broker/cdse/token",
        headers={"Authorization": f"Bearer {USER_TOKEN}", "Accept": "application/json"},
    )
    client.post.assert_not_called()


@pytest.mark.asyncio
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_success_uses_jwt_exp(mock_client_class):
    external = _jwt(exp_offset=600)
    _mock_client(mock_client_class, _response(200, {"access_token": external}))

    assert await _retrieve_broker_token(USER_TOKEN, "cdse") == external


@pytest.mark.asyncio
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_opaque_token_without_expiry(mock_client_class):
    _mock_client(mock_client_class, _response(200, {"access_token": "opaque-token"}))

    assert await _retrieve_broker_token(USER_TOKEN, "cdse") == "opaque-token"


@pytest.mark.asyncio
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_encodes_provider_alias(mock_client_class):
    client = _mock_client(mock_client_class, _response(200, {"access_token": _jwt()}))

    await _retrieve_broker_token(USER_TOKEN, "a/b c")

    assert client.get.call_args.args[0] == f"{KEYCLOAK_BASE_URL}/broker/a%2Fb%20c/token"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"access_token": "opaque-token-1", "accessTokenExpiration": int(time.time()) - 5},
        {"access_token": "opaque-token-2", "accessTokenExpiration": int(time.time()) + 5},
        {"access_token": _jwt(exp_offset=-60)},
    ],
)
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_expired(mock_client_class, body):
    _mock_client(mock_client_class, _response(200, body))

    with pytest.raises(AuthException) as exc_info:
        await _retrieve_broker_token(USER_TOKEN, "cdse")

    assert exc_info.value.http_status == status.HTTP_401_UNAUTHORIZED
    assert "expired" in exc_info.value.message
    assert "Account Dashboard" in exc_info.value.message
    _assert_no_token_leak(exc_info.value.message, USER_TOKEN, body["access_token"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code,body,expected_status,expected_text",
    [
        (
            400,
            {"errorMessage": "User [u] is not associated with identity provider [cdse]."},
            status.HTTP_401_UNAUTHORIZED,
            "Please link your account with cdse",
        ),
        (
            404,
            {"errorMessage": "No token stored for user [u] with associated identity provider"},
            status.HTTP_401_UNAUTHORIZED,
            "unlink and link your cdse account again",
        ),
        (
            502,
            {"errorMessage": "Unable to refresh token"},
            status.HTTP_401_UNAUTHORIZED,
            "session has expired",
        ),
        (
            400,
            {"errorMessage": "Invalid token."},
            status.HTTP_401_UNAUTHORIZED,
            "retry signing in",
        ),
        (
            403,
            {"errorMessage": "Client [c] not authorized to retrieve tokens from identity provider"},
            status.HTTP_403_FORBIDDEN,
            "not permitted",
        ),
        (
            400,
            {"errorMessage": "Identity Provider [cdse] does not support this operation."},
            status.HTTP_502_BAD_GATEWAY,
            "contact APEx support",
        ),
        (500, {"errorMessage": "boom"}, status.HTTP_502_BAD_GATEWAY, "contact APEx support"),
    ],
)
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_upstream_errors(
    mock_client_class, status_code, body, expected_status, expected_text
):
    _mock_client(mock_client_class, _response(status_code, body))

    with pytest.raises(AuthException) as exc_info:
        await _retrieve_broker_token(USER_TOKEN, "cdse")

    assert exc_info.value.http_status == expected_status
    assert expected_text in exc_info.value.message
    assert body["errorMessage"] not in exc_info.value.message
    _assert_no_token_leak(exc_info.value.message, USER_TOKEN)


@pytest.mark.asyncio
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_html_error_page(mock_client_class):
    # Keycloak renders an HTML error page (502) e.g. for an unknown provider alias
    _mock_client(mock_client_class, _response(502, invalid_json=True))

    with pytest.raises(AuthException) as exc_info:
        await _retrieve_broker_token(USER_TOKEN, "unknown")

    assert exc_info.value.http_status == status.HTTP_502_BAD_GATEWAY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        _response(200, invalid_json=True),
        _response(200, ["not", "a", "dict"]),
        _response(200, {"token_type": "Bearer"}),
        _response(200, {"access_token": ""}),
        _response(200, {"access_token": 123}),
    ],
)
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_malformed_response(mock_client_class, response):
    _mock_client(mock_client_class, response)

    with pytest.raises(AuthException) as exc_info:
        await _retrieve_broker_token(USER_TOKEN, "cdse")

    assert exc_info.value.http_status == status.HTTP_502_BAD_GATEWAY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,expected_status",
    [
        (httpx.ReadTimeout("timeout"), status.HTTP_504_GATEWAY_TIMEOUT),
        (httpx.ConnectError("refused"), status.HTTP_502_BAD_GATEWAY),
    ],
)
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_transport_errors(mock_client_class, error, expected_status):
    _mock_client(mock_client_class, side_effect=error)

    with pytest.raises(AuthException) as exc_info:
        await _retrieve_broker_token(USER_TOKEN, "cdse")

    assert exc_info.value.http_status == expected_status
    assert "Could not authenticate with cdse" in exc_info.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "access_token",
    [USER_TOKEN, _jwt(iss=KEYCLOAK_BASE_URL)],
)
@patch("app.auth.httpx.AsyncClient")
async def test_retrieve_broker_token_rejects_apex_token(mock_client_class, access_token):
    _mock_client(mock_client_class, _response(200, {"access_token": access_token}))

    with pytest.raises(AuthException) as exc_info:
        await _retrieve_broker_token(USER_TOKEN, "cdse")

    assert exc_info.value.http_status == status.HTTP_502_BAD_GATEWAY
    _assert_no_token_leak(exc_info.value.message, USER_TOKEN, access_token)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token_prefix,expected_prefix",
    [("oidc/CDSE", "oidc/CDSE/"), (None, "")],
)
@patch("app.auth.httpx.AsyncClient")
async def test_exchange_token_formats_broker_token(
    mock_client_class, token_prefix, expected_prefix
):
    url = "https://openeo.dataspace.copernicus.eu"
    original_config = settings.backend_auth_config.get(url)
    external = _jwt()
    _mock_client(mock_client_class, _response(200, {"access_token": external}))

    try:
        settings.backend_auth_config[url] = BackendAuthConfig(
            auth_method=AuthMethod.USER_CREDENTIALS,
            token_provider="cdse",
            token_prefix=token_prefix,
        )

        result = await exchange_token(USER_TOKEN, url)

        assert result == f"{expected_prefix}{external}"
        assert USER_TOKEN not in result
    finally:
        if original_config:
            settings.backend_auth_config[url] = original_config
        else:
            settings.backend_auth_config.pop(url, None)
