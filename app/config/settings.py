import json
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.schemas import AuthMethod, BackendAuthConfig


class Settings(BaseSettings):
    app_name: str = Field(
        default="APEx Dispach API", json_schema_extra={"env": "APP_NAME"}
    )
    app_description: str = Field(
        default="",
        json_schema_extra={"env": "APP_DESCRIPTION"},
    )
    env: str = Field(default="development", json_schema_extra={"env": "APP_ENV"})

    cors_allowed_origins: str = Field(
        default="", json_schema_extra={"env": "CORS_ALLOWED_ORIGINS"}
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    # Keycloak / OIDC
    keycloak_host: str = Field(
        default=str("localhost"),
        json_schema_extra={"env": "KEYCLOAK_HOST"},
    )
    keycloak_realm: str = Field(default="", json_schema_extra={"env": "KEYCLOAK_REALM"})
    keycloak_client_id: str = Field(
        default="", json_schema_extra={"env": "KEYCLOAK_CLIENT_ID"}
    )
    keycloak_client_secret: str | None = Field(
        default="", json_schema_extra={"env": "KEYCLOAK_CLIENT_SECRET"}
    )

    # Backend auth configuration
    backends: str | None = Field(
        default="", json_schema_extra={"env": "BACKENDS"}
    )
    backend_auth_config: Dict[str, BackendAuthConfig] = Field(default_factory=dict)

    def load_backends_auth_config(self):
        """
        Populate self.backends from BACKENDS_JSON if provided, otherwise keep defaults.
        BACKENDS_JSON should be a JSON object keyed by hostname with BackendConfig-like values.
        """
        required_fields = []
        if self.backends:

            try:
                raw = json.loads(self.backends)
                for host, cfg in raw.items():
                    backend = BackendAuthConfig(**cfg)

                    if backend.auth_method == AuthMethod.CLIENT_CREDENTIALS:
                        required_fields = ["client_credentials"]
                    elif backend.auth_method == AuthMethod.USER_CREDENTIALS:
                        required_fields = ["token_provider"]

                    for field in required_fields:
                        if not getattr(backend, field, None):
                            raise ValueError(
                                f"Backend '{host}' must define '{field}' when "
                                f"OPENEO_AUTH_METHOD={backend.auth_method}"
                            )
                    self.backend_auth_config[host] = BackendAuthConfig(**cfg)
            except Exception:
                # Fall back or raise as appropriate
                raise


settings = Settings()
settings.load_backends_auth_config()
