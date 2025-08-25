import jwt
from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jwt import PyJWKClient
from loguru import logger

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
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[ALGORITHM],
            issuer=KEYCLOAK_BASE_URL,
        )
        return payload
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


def get_current_user_id(token: str = Depends(oauth2_scheme)):
    user: dict = _decode_token(token)
    return user["sub"]


async def websocket_authenticate(websocket: WebSocket) -> str | None:
    """
    Authenticate a WebSocket connection using a JWT token from query params.
    Returns the ID of the authenticated user payload if valid, otherwise closes the connection.
    """
    logger.debug("Authenticating websocket")
    token = websocket.query_params.get("token")
    if not token:
        logger.error("Token is missing from websocket authentication")
        await websocket.close(code=1008, reason="Missing token")
        return None

    try:
        user_id = get_current_user_id(token)
        await websocket.accept()
        return user_id
    except Exception as e:
        logger.error(f"Invalid token in websocket authentication: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return None
