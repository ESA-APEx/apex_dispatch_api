from pydantic import AnyHttpUrl, ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = Field("", json_schema_extra={"env": "APP_NAME"})
    app_description: str = Field("", json_schema_extra={"env": "APP_DESCRIPTION"})
    env: str = Field("development", json_schema_extra={"env": "APP_ENV"})

    # Keycloak / OIDC
    keycloak_server_url: AnyHttpUrl = Field(
        None, json_schema_extra={"env": "KEYCLOAK_SERVER_URL"}
    )
    keycloak_realm: str = Field(None, json_schema_extra={"env": "KEYCLOAK_REALM"})
    keycloak_client_id: str = Field(
        None, json_schema_extra={"env": "KEYCLOAK_CLIENT_ID"}
    )
    keycloak_client_secret: str | None = Field(
        None, json_schema_extra={"env": "KEYCLOAK_CLIENT_SECRET"}
    )

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


settings = Settings()
