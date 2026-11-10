"""Authenticate GEP callback service accounts independently of APEx user login."""

from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from http_apis_problems_detail import ErrorDetail
from http_apis_problems_detail.fastapi import ForbiddenException, UnauthorizedException
from jwt import PyJWKClient

from app.platforms.implementations.gep.settings import get_callback_backends

callback_bearer = HTTPBearer(auto_error=False, scheme_name="GepCallbackBearer")


@lru_cache(maxsize=32)
def _callback_jwks_client(issuer: str) -> PyJWKClient:
    # Called only after matching a configured issuer, never an arbitrary token URL.
    # Cache the JWKS rather than individual keys indefinitely, allowing key rotation.
    return PyJWKClient(
        f"{issuer.rstrip('/')}/protocol/openid-connect/certs",
        cache_jwk_set=True,
        lifespan=300,
        timeout=10,
    )


def verify_callback_token(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(callback_bearer)],
) -> set[str]:
    """Return the backend endpoints this verified service account may update."""
    unauthorized = UnauthorizedException(
        request=request,
        errors=[ErrorDetail(
            header="Authorization", detail="Callback Bearer Authorization token not set or invalid."
        )],
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized

    # Configuration errors are server errors, not invalid client credentials.
    configured_backends = get_callback_backends()
    try:
        issuer = jwt.decode(
            creds.credentials, options={"verify_signature": False}
        ).get("iss")
        candidates = {
            endpoint: cfg for endpoint, cfg in configured_backends.items()
            if isinstance(issuer, str) and issuer
            and cfg.callback_issuer == issuer
            and cfg.callback_audience and cfg.callback_clients
        }
        if not candidates:
            raise unauthorized

        key = _callback_jwks_client(issuer).get_signing_key_from_jwt(creds.credentials).key
        allowed: set[str] = set()
        valid_audience = False
        # Require an audience match; reject any other JWT validation failure.
        for endpoint, cfg in candidates.items():
            try:
                claims = jwt.decode(
                    creds.credentials,
                    key,
                    algorithms=["RS256"],
                    issuer=issuer,
                    audience=cfg.callback_audience,
                    options={"require": ["iss", "aud", "exp"]},
                )
            except jwt.InvalidAudienceError:
                continue
            valid_audience = True
            client = claims.get("azp")
            if isinstance(client, str) and client in cfg.callback_clients:
                allowed.add(endpoint.rstrip("/"))
        if not valid_audience:
            raise unauthorized
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError) as exc:
        raise unauthorized from exc

    if not allowed:
        raise ForbiddenException(
            request=request,
            errors=[ErrorDetail(
                header="Authorization", detail="Callback client is not allowed."
            )],
        )
    return allowed
