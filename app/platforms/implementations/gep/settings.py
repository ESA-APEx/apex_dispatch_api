"""Read GEP callback settings without changing shared backend configuration."""

from functools import lru_cache

from pydantic import TypeAdapter

from app.config.settings import settings
from app.platforms.implementations.gep.schemas import CallbackBackendAuthConfig


@lru_cache(maxsize=1)
def _parse_callback_backends(raw: str) -> dict[str, CallbackBackendAuthConfig]:
    return TypeAdapter(dict[str, CallbackBackendAuthConfig]).validate_json(raw)


def get_callback_backends() -> dict[str, CallbackBackendAuthConfig]:
    # The shared BackendAuthConfig ignores callback fields. Reparse the same raw
    # BACKENDS value with our local extension, preserving the deployment contract.
    return _parse_callback_backends(settings.backends or "{}")
