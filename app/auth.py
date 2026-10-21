import datetime
from typing import Any, Dict
from urllib.parse import quote

import httpx
import jwt
from fastapi import Depends, WebSocket, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jwt import PyJWKClient
from loguru import logger

from app.error import AuthException, DispatcherException
from app.schemas.websockets import WSStatusMessage

from .config.settings import settings

# Keycloak OIDC info
KEYCLOAK_BASE_URL = f"{settings.keycloak_host}/realms/{settings.keycloak_realm}"
JWKS_URL = f"{KEYCLOAK_BASE_URL}/protocol/openid-connect/certs"
ALGORITHM = "RS256"

BROKER_TOKEN_TIMEOUT_SECONDS = 10.0
EXTERNAL_TOKEN_MIN_VALIDITY_SECONDS = 30


# Keycloak OIDC endpoints
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{settings.keycloak_host}/realms/{settings.keycloak_realm}/"
    "protocol/openid-connect/auth",
    tokenUrl=f"{settings.keycloak_host}/realms/{settings.keycloak_realm}/"
    "protocol/openid-connect/token",
)

# PyJWT helper to fetch and cache keys
jwks_client = PyJWKClient(JWKS_URL, cache_keys=True)


def _decode_token(token: str):
    try:
        logger.debug(f"Decoding token for user authentication with issuer {KEYCLOAK_BASE_URL}")
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[ALGORITHM],
            issuer=KEYCLOAK_BASE_URL,
            # No audience is configured; Keycloak adds aud=broker once broker/read-token is mapped.
            options={"verify_aud": False},
        )
        return payload
    except Exception as e:
        logger.warning(f"User token validation failed: {type(e).__name__}")
        raise AuthException(
            http_status=status.HTTP_401_UNAUTHORIZED,
            message="Could not validate credentials. Please retry signing in.",
        )


def get_current_user_id(token: str = Depends(oauth2_scheme)):
    return get_current_user_claims(token)["sub"]


def get_current_user_claims(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    return _decode_token(token)


async def websocket_authenticate(websocket: WebSocket) -> str | None:
    """
    Authenticate a WebSocket connection using a JWT token from query params.
    Returns the token of the authenticated user payload if valid, otherwise closes the connection.
    """
    logger.debug("Authenticating websocket")
    token = websocket.query_params.get("token")

    if not token:
        logger.error("Token is missing from websocket authentication")
        await websocket.close(code=1008, reason="Missing token")
        return None

    try:
        await websocket.accept()
        return token
    except DispatcherException as ae:
        logger.error(f"Dispatcher exception detected: {ae.message}")
        await websocket.send_json(
            WSStatusMessage(type="error", message=ae.message).model_dump()
        )
        await websocket.close(code=1008, reason=ae.error_code)
        return None
    except Exception as e:
        logger.error(f"Unexpected error occurred during websocket authentication: {e}")
        await websocket.send_json(
            WSStatusMessage(
                type="error",
                message="Something went wrong during authentication. Please try again.",
            ).model_dump()
        )
        await websocket.close(code=1008, reason="INTERNAL_ERROR")
        return None


async def exchange_token(user_token: str, url: str) -> str:
    """
    Retrieve the external identity-provider token for accessing an external backend. The token
    is read from the Keycloak broker endpoint for the backend's configured `token_provider`.

    :param url: The URL of the backend for which to retrieve the token. This URL should be
    configured in the BACKENDS environment variable.
    :return: The bearer token as a string, prefixed with `token_prefix` when configured.
    """

    provider = settings.backend_auth_config[url].token_provider
    token_prefix = settings.backend_auth_config[url].token_prefix

    if not provider:
        raise ValueError(
            f"Backend '{url}' must define 'token_provider'"
        )

    external_token = await _retrieve_broker_token(user_token=user_token, provider=provider)
    return f"{token_prefix}/{external_token}" if token_prefix else external_token


def _account_url() -> str:
    return f"{settings.keycloak_host}/realms/{settings.keycloak_realm}/account"


def _support_message(provider: str) -> str:
    return (
        f"Could not authenticate with {provider}. Please contact APEx support or reach out "
        "through the <a href='https://forum.apex.esa.int/'>APEx User Forum</a>."
    )


def _relink_message(provider: str, reason: str) -> str:
    return (
        f"{reason} Please unlink and link your {provider} account again in your "
        f"<a href='{_account_url()}'>Account Dashboard</a>."
    )


def _keycloak_error_message(resp: httpx.Response) -> str:
    """Extract Keycloak's error text for classification only; never surfaced or logged."""
    try:
        body = resp.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    message = body.get("errorMessage") or body.get("error_description") or body.get("error")
    return message.lower() if isinstance(message, str) else ""


def _broker_error(resp: httpx.Response, provider: str) -> AuthException:
    """
    Map a non-200 response of the Keycloak broker token endpoint to an AuthException.
    Keycloak returns `{"errorMessage": "..."}` for these errors (HTML for unknown providers).
    """
    upstream = resp.status_code
    error_message = _keycloak_error_message(resp)

    if upstream == 400 and "not associated with identity provider" in error_message:
        reason = "not_linked"
        exc = AuthException(
            http_status=status.HTTP_401_UNAUTHORIZED,
            message=(
                f"Please link your account with {provider} in your "
                f"<a href='{_account_url()}'>Account Dashboard</a>."
            ),
        )
    elif upstream == 404 and "no token stored" in error_message:
        reason = "no_stored_token"
        exc = AuthException(
            http_status=status.HTTP_401_UNAUTHORIZED,
            message=_relink_message(
                provider, f"No {provider} session is available for your account."
            ),
        )
    elif upstream == 502 and "unable to refresh token" in error_message:
        reason = "refresh_failed"
        exc = AuthException(
            http_status=status.HTTP_401_UNAUTHORIZED,
            message=_relink_message(provider, f"Your {provider} session has expired."),
        )
    elif upstream == 401 or (upstream == 400 and "invalid token" in error_message):
        reason = "invalid_user_token"
        exc = AuthException(
            http_status=status.HTTP_401_UNAUTHORIZED,
            message="Could not validate credentials. Please retry signing in.",
        )
    elif upstream == 403:
        reason = (
            "broker_client_missing"
            if "has not migrated" in error_message
            else "read_token_role_missing_in_access_token"
        )
        exc = AuthException(
            http_status=status.HTTP_403_FORBIDDEN,
            message=(
                f"The APEx Dispatcher is not permitted to use your {provider} account. "
                "Please contact APEx support or reach out through the "
                "<a href='https://forum.apex.esa.int/'>APEx User Forum</a>."
            ),
        )
    elif upstream == 400 and "does not support this operation" in error_message:
        reason = "store_tokens_disabled"
        exc = AuthException(
            http_status=status.HTTP_502_BAD_GATEWAY, message=_support_message(provider)
        )
    else:
        reason = "upstream_error"
        exc = AuthException(
            http_status=status.HTTP_502_BAD_GATEWAY, message=_support_message(provider)
        )

    logger.error(
        f"Broker token retrieval failed for provider={provider}, "
        f"status={upstream}, reason={reason}"
    )
    return exc


def _validate_external_token(
    access_token: str, user_token: str, token_response: Dict[str, Any], provider: str
) -> None:
    """
    Ensure the token returned by the broker is an external, non-expired token. Raises an
    AuthException otherwise.
    """
    if access_token == user_token:
        logger.error(f"Broker returned the APEx user token for provider={provider}")
        raise AuthException(
            http_status=status.HTTP_502_BAD_GATEWAY, message=_support_message(provider)
        )

    claims: Dict[str, Any] = {}
    try:
        # Signature is checked by the external backend; claims are only inspected here.
        claims = jwt.decode(access_token, options={"verify_signature": False})
    except jwt.PyJWTError:
        pass  # Opaque (non-JWT) access token

    if claims.get("iss") == KEYCLOAK_BASE_URL:
        logger.error(f"Broker returned an APEx-issued token for provider={provider}")
        raise AuthException(
            http_status=status.HTTP_502_BAD_GATEWAY, message=_support_message(provider)
        )

    # `expires_in` in the stored response is the original lifetime, not the remaining one.
    expiration: Any = token_response.get("accessTokenExpiration")
    if not _is_positive_number(expiration):
        expiration = claims.get("exp")

    if not _is_positive_number(expiration):
        logger.warning(
            f"Could not determine expiry of external token for provider={provider}"
        )
        return

    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    if expiration <= now + EXTERNAL_TOKEN_MIN_VALIDITY_SECONDS:
        logger.error(
            f"Broker token retrieval failed for provider={provider}, reason=expired"
        )
        raise AuthException(
            http_status=status.HTTP_401_UNAUTHORIZED,
            message=_relink_message(provider, f"Your {provider} session has expired."),
        )


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


async def _retrieve_broker_token(user_token: str, provider: str) -> str:
    """
    Retrieve the user's stored external access token for `provider` from the Keycloak broker
    endpoint (GET /realms/{realm}/broker/{provider}/token), authenticated with the user's APEx
    access token. Requires "Store tokens" on the identity provider and the `broker/read-token`
    role in the APEx access token.

    :param user_token: APEx access token of the user (Bearer token).
    :param provider: Keycloak identity provider alias.
    :return: The external access token.
    :raise: AuthException with an appropriate status and message on error.
    """
    broker_url = f"{KEYCLOAK_BASE_URL}/broker/{quote(provider, safe='')}/token"

    try:
        async with httpx.AsyncClient(timeout=BROKER_TOKEN_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                broker_url,
                headers={"Authorization": f"Bearer {user_token}", "Accept": "application/json"},
            )
    except httpx.TimeoutException:
        logger.error(f"Broker token retrieval timed out for provider={provider}")
        raise AuthException(
            http_status=status.HTTP_504_GATEWAY_TIMEOUT, message=_support_message(provider)
        )
    except httpx.RequestError as exc:
        logger.error(
            f"Broker token retrieval network error for provider={provider}: "
            f"{type(exc).__name__}"
        )
        raise AuthException(
            http_status=status.HTTP_502_BAD_GATEWAY, message=_support_message(provider)
        )

    if resp.status_code != 200:
        raise _broker_error(resp, provider)

    try:
        body = resp.json()
    except ValueError:
        body = None

    access_token = body.get("access_token") if isinstance(body, dict) else None
    if not isinstance(body, dict) or not isinstance(access_token, str) or not access_token.strip():
        logger.error(
            f"Broker token retrieval returned a malformed response for provider={provider}"
        )
        raise AuthException(
            http_status=status.HTTP_502_BAD_GATEWAY, message=_support_message(provider)
        )

    _validate_external_token(access_token, user_token, body, provider)
    return access_token
