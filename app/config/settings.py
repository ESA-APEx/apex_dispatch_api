from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(
        default="APEx Disatpcher API", json_schema_extra={"env": "APP_NAME"}
    )
    app_description: str = Field(
        default="API description for the APEx Dispatcher",
        json_schema_extra={"env": "APP_DESCRIPTION"},
    )
    env: str = Field(default="development", json_schema_extra={"env": "APP_ENV"})

    cors_allowed_origins: str = Field(
        default="", json_schema_extra={"env": "CORS_ALLOWED_ORIGINS"}
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


settings = Settings()
