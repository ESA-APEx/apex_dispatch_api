from typing import Any, Dict
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
KEYCLOAK_BASE_URL = f"https://{settings.keycloak_host}/realms/{settings.keycloak_realm}"
JWKS_URL = f"{KEYCLOAK_BASE_URL}/protocol/openid-connect/certs"
ALGORITHM = "RS256"


# Keycloak OIDC endpoints
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"https://{settings.keycloak_host}/realms/{settings.keycloak_realm}/"
    "protocol/openid-connect/auth",
    tokenUrl=f"https://{settings.keycloak_host}/realms/{settings.keycloak_realm}/"
    "protocol/openid-connect/token",
)

# PyJWT helper to fetch and cache keys
jwks_client = PyJWKClient(JWKS_URL, cache_keys=True)


def _decode_token(token: str):
    try:
        logger.debug(f"Decoding token for user authentication: {token} with "
                     f"issuer {KEYCLOAK_BASE_URL}")
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[ALGORITHM],
            issuer=KEYCLOAK_BASE_URL,
        )
        return payload
    except Exception:
        raise AuthException(
            http_status=status.HTTP_401_UNAUTHORIZED,
            message="Could not validate credentials. Please retry signing in.",
        )


def get_current_user_id(token: str = Depends(oauth2_scheme)):
    user: dict = _decode_token(token)
    return user["sub"]


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
    Retrieve the exchanged token for accessing an external backend. This is done  by exchanging the
    user's token for a platform-specific token using the configured token provider.

    :param url: The URL of the backend for which to exchange the token. This URL should be
    configured in the BACKEND_CONFIG environment variable.
    :return: The bearer token as a string.
    """

    provider = settings.backend_auth_config[url].token_provider
    token_prefix = settings.backend_auth_config[url].token_prefix

    if not provider or not token_prefix:
        raise ValueError(
            f"Backend '{url}' must define 'token_provider' and 'token_prefix'"
        )

    platform_token = await _exchange_token_for_provider(
        initial_token=user_token, provider=provider
    )
    return (
        f"{token_prefix}/{platform_token['access_token']}"
        if token_prefix
        else platform_token["access_token"]
    )


async def _exchange_token_for_provider(
    initial_token: str, provider: str
) -> Dict[str, Any]:
    """
    Exchange a Keycloak access token for a token/audience targeted at `provider`
    using the Keycloak Token Exchange (grant_type=urn:ietf:params:oauth:grant-type:token-exchange).

    :param initial_token: token obtained from the client (Bearer token)
    :param provider: target provider name or client_id.

    :return: The token response (dict) on success.

    :raise: Raises AuthException with an appropriate status and message on error.
    """
    token_url = f"{KEYCLOAK_BASE_URL}/protocol/openid-connect/token"

    # Check if the necessary settings are in place
    if not settings.keycloak_client_id:
        raise AuthException(
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Token exchange not configured on the server (missing client credentials).",
        )

    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "client_id": settings.keycloak_client_id,
        "client_secret": settings.keycloak_client_secret,
        "subject_token": initial_token,
        "requested_issuer": provider,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_url, data=payload)
    except httpx.RequestError as exc:
        logger.error(f"Token exchange network error for provider={provider}: {exc}")
        raise AuthException(
            http_status=status.HTTP_502_BAD_GATEWAY,
            message=(
                f"Could not authenticate with {provider}. Please contact APEx support or reach out "
                "through the <a href='https://forum.apex.esa.int/'>APEx User Forum</a>."
            ),
        )

    # Parse response
    try:
        body = resp.json()
    except ValueError:
        logger.error(
            f"Token exchange invalid JSON response (status={resp.status_code})"
        )
        raise AuthException(
            http_status=status.HTTP_502_BAD_GATEWAY,
            message=(
                f"Could not authenticate with {provider}. Please contact APEx support or reach out "
                "through the <a href='https://forum.apex.esa.int/'>APEx User Forum</a>."
            ),
        )

    if resp.status_code != 200:
        # Keycloak returns error and error_description fields for token errors
        err = body.get("error_description") or body.get("error") or resp.text
        logger.error(
            "Token exchange failed",
            extra={"provider": provider, "status": resp.status_code, "error": err},
        )
        # Map common upstream statuses to meaningful client statuses
        client_status = (
            status.HTTP_401_UNAUTHORIZED
            if resp.status_code in (400, 401, 403)
            else status.HTTP_502_BAD_GATEWAY
        )

        raise AuthException(
            http_status=client_status,
            message=(
                f"Please link your account with {provider} in your "
                "<a href='https://{settings.keycloak_host}/realms/{settings.keycloak_realm}/"
                "account'>Account Dashboard</a>"
                if body.get("error", "") == "not_linked"
                else f"Could not authenticate with {provider}: {err}"
            ),
        )

    # Successful exchange, return token response (access_token, expires_in, etc.)
    return body
