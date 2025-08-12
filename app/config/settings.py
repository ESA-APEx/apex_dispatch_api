from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="", json_schema_extra={"env": "APP_NAME"})
    app_description: str = Field(default="", json_schema_extra={"env": "APP_DESCRIPTION"})
    env: str = Field(default="development", json_schema_extra={"env": "APP_ENV"})

    # Keycloak / OIDC
    keycloak_server_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("https://localhost"),
        json_schema_extra={"env": "KEYCLOAK_SERVER_URL"},
    )
    keycloak_realm: str = Field(default="", json_schema_extra={"env": "KEYCLOAK_REALM"})
    keycloak_client_id: str = Field(default="", json_schema_extra={"env": "KEYCLOAK_CLIENT_ID"})
    keycloak_client_secret: str | None = Field(
        default="", json_schema_extra={"env": "KEYCLOAK_CLIENT_SECRET"}
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


settings = Settings()
