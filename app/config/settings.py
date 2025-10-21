import json
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.openeo.settings import OpenEOAuthMethod, OpenEOBackendConfig


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

    # openEO Settings
    openeo_auth_method: OpenEOAuthMethod = Field(
        default=OpenEOAuthMethod.USER_CREDENTIALS,
        json_schema_extra={"env": "OPENEO_AUTH_METHOD"},
    )

    openeo_backends: str | None = Field(
        default="", json_schema_extra={"env": "OPENEO_BACKENDS"}
    )

    openeo_backend_config: Dict[str, OpenEOBackendConfig] = Field(default_factory=dict)

    def load_openeo_backends_from_env(self):
        """
        Populate self.backends from BACKENDS_JSON if provided, otherwise keep defaults.
        BACKENDS_JSON should be a JSON object keyed by hostname with BackendConfig-like values.
        """
        required_fields = []
        if self.openeo_backends:

            if self.openeo_auth_method == OpenEOAuthMethod.CLIENT_CREDENTIALS:
                required_fields = ["client_credentials"]
            elif self.openeo_auth_method == OpenEOAuthMethod.USER_CREDENTIALS:
                required_fields = ["token_provider"]

            try:
                raw = json.loads(self.openeo_backends)
                for host, cfg in raw.items():
                    backend = OpenEOBackendConfig(**cfg)

                    for field in required_fields:
                        if not getattr(backend, field, None):
                            raise ValueError(
                                f"Backend '{host}' must define '{field}' when "
                                f"OPENEO_AUTH_METHOD={self.openeo_auth_method}"
                            )
                    self.openeo_backend_config[host] = OpenEOBackendConfig(**cfg)
            except Exception:
                # Fall back or raise as appropriate
                raise


settings = Settings()
settings.load_openeo_backends_from_env()
