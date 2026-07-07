from typing import Any, Dict
import httpx
import jwt
from fastapi import Depends, WebSocket, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jwt import PyJWKClient
from loguru import logger

from app.error import AuthException, DispatcherException
from app.schemas.websockets import WSStatusMessage
from app.config.schemas import BackendAuthConfig

from .config.settings import settings

# Keycloak OIDC info
KEYCLOAK_BASE_URL = f"{settings.keycloak_host}/realms/{settings.keycloak_realm}"
JWKS_URL = f"{KEYCLOAK_BASE_URL}/protocol/openid-connect/certs"
ALGORITHM = "RS256"


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
        logger.debug(f"Decoding token for user authentication: {token} with "
                     f"issuer {KEYCLOAK_BASE_URL}")
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token).key
        except Exception as e:
            raise
            logger.warning(f"Signing key error: {str(e)}")
            signing_key = ""
        logger.warning("Before decode")
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[ALGORITHM],
            issuer=KEYCLOAK_BASE_URL,
            options={"verify_aud": False},
        )
        return payload
    except Exception:
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
    Retrieve the exchanged token for accessing an external backend. This is done  by exchanging the
    user's token for a platform-specific token using the configured token provider.

    :param url: The URL of the backend for which to exchange the token. This URL should be
    configured in the BACKEND_CONFIG environment variable.
    :return: The bearer token as a string.
    """

    backend_idp = settings.backend_auth_config[url]

    if not backend_idp.token_provider:
        raise ValueError(
            f"Backend '{url}' must define 'token_provider'"
        )

    platform_token = await _exchange_token_for_provider(
        initial_token=user_token,
        backend_idp=backend_idp
    )
    return (
        f"{backend_idp.token_prefix}/{platform_token['access_token']}"
        if backend_idp.token_prefix
        else platform_token["access_token"]
    )


async def _exchange_token_for_provider(
    initial_token: str, backend_idp: BackendAuthConfig
) -> Dict[str, Any]:
    """
    Exchange a Keycloak access token for a token/audience targeted at `provider`
    using the Keycloak Token Exchange (grant_type=urn:ietf:params:oauth:grant-type:token-exchange).

    :param initial_token: token obtained from the client (Bearer token)
    :param backend_idp: target IDP.

    :return: The token response (dict) on success.

    :raise: Raises AuthException with an appropriate status and message on error.
    """
    if backend_idp.token_url:
        # Cross-Domain Federation/Trusted Token Delegation
        # Payload will be sent to the backend IDP and receive a valid access token from it
        logger.info(f"Using Cross-Domain Federation/Trusted Token Delegation with IDP {backend_idp.token_url}")
        if not backend_idp.client_id:
            raise AuthException(
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Token exchange not configured on the server (missing client credentials).",
            )
        token_url = backend_idp.token_url
        payload = {
            "client_id": backend_idp.client_id,
            "client_secret": backend_idp.client_secret, 
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange", 
            "subject_token": initial_token, 
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token", 
            "subject_issuer": backend_idp.subject_issuer,
            "audience": backend_idp.audience, 
            "requested_token_type": "urn:ietf:params:oauth:token-type:access_token", 
            "scope": "openid profile email"
        }

    else:
        # Internal-to-External Token Exchange
        # Payload will be sent to the backend IDP and receive a valid access token from it
        logger.info(f"Using Internal-to-External Token Exchange with IDP {backend_idp.token_provider}")

        token_url = f"{KEYCLOAK_BASE_URL}/protocol/openid-connect/token"
        #token_url = "https://iam.terradue.com/realms/master/protocol/openid-connect/token"

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
            "requested_issuer": backend_idp.token_provider,
        }

    provider_str = backend_idp.token_provider or backend_idp.token_url
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_url, data=payload)
    except httpx.RequestError as exc:
        logger.error(
            f"Token exchange network error for provider={provider_str}: {exc}")
        raise AuthException(
            http_status=status.HTTP_502_BAD_GATEWAY,
            message=(
                f"Could not authenticate with {provider_str}. Please contact APEx support or reach out "
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
                f"Could not authenticate with {provider_str}. Please contact APEx support or reach out "
                "through the <a href='https://forum.apex.esa.int/'>APEx User Forum</a>."
            ),
        )

    if resp.status_code != 200:
        # Keycloak returns error and error_description fields for token errors
        err = body.get("error_description") or body.get("error") or resp.text
        logger.error(
            f"Token exchange failed for provider={provider_str}, status={resp.status_code}, error={err}"
        )
        # Map common upstream statuses to meaningful client statuses
        client_status = (
            status.HTTP_401_UNAUTHORIZED
            if resp.status_code in (400, 401, 403)
            else status.HTTP_502_BAD_GATEWAY
        )

        if backend_idp.token_provider:
            message = (
                f"Please link your account with {provider_str} in your "
                f"<a href='{settings.keycloak_host}/realms/{settings.keycloak_realm}/"
                "account'>Account Dashboard</a>"
                if body.get("error", "") == "not_linked"
                else f"Could not authenticate with {provider_str}: {err}"
            )
        else:
            message = f"Could not authenticate with {provider_str}: {err}"

        raise AuthException(
            http_status=client_status,
            message=message
        )

    # Successful exchange, return token response (access_token, expires_in, etc.)
    return body
