# Configuring the Dispatcher
The Dispatcher can be configured using environment variables. These variables can be set directly in your shell or defined in a `.env` file for convenience.
Below are the key settings that can be adjusted to tailor the Dispatcher's behavior to your needs. 

| Environment Variable     | Description                                                 | Values                                    | Default Value      |
| ------------------------ | ----------------------------------------------------------- | ----------------------------------------- | ------------------ |
| **General Settings**     |                                                             |                                           |                    |
| `APP_NAME`               | The name of the application.                                | Text                                      | APEx Dispatch API  |
| `APP_DESCRIPTION`        | A brief description of the application.                     | Text                                      | ""                 |
| `APP_ENV`                | The environment in which the application is running         | `development` /  `production`                    | development        |
| `CORS_ALLOWED_ORIGINS`   | Comma-separated list of allowed origins for CORS.           | Text                                      | ""                 |
| **Database Settings**|||
| `DATABASE_URL`           | The database connection URL.                                | Text                                      | "" |
| **Keycloak Settings**    |                                                             |                                           |                    |
| `KEYCLOAK_HOST`          | The hostname of the Keycloak server.                        | Text                                      | localhost          |
| `KEYCLOAK_REALM`         | The Keycloak realm to use for authentication.               | Text                                      | ""                 |
| `KEYCLOAK_CLIENT_ID`     | The client ID registered in Keycloak.                       | Text                                      | ""                 |
| `KEYCLOAK_CLIENT_SECRET` | The client secret for the Keycloak client.                  | Text                                      | ""                 |
| **openEO Settings**      |                                                             |                                           |                    |
| `OPENEO_AUTH_METHOD`     | The authentication method to use for openEO backends.       | `USER_CREDENTIALS` / `CLIENT_CREDENTIALS` | `USER_CREDENTIALS` |
| `OPENEO_BACKEND_CONFIG`  | JSON string defining the configuration for openEO backends. | JSON                                      | `{}`               |


## openEO Backend Configuration
The `OPENEO_BACKEND_CONFIG` environment variable allows you to specify the configuration for multiple openEO backends in JSON format.
Here is an example of how to structure this configuration:  

```json
{
  "https://openeo.backend1.com": {
    "client_credentials": "oidc_provider/client_id/secret_secret",
    "token_provider": "backend",
    "token_prefix": "oidc/backend"
  },
  ...
}
```
Each backend configuration can include the following fields:

- `client_credentials`: The client credentials for authenticating with the openEO backend. This is required if the `OPENEO_AUTH_METHOD` is set to `CLIENT_CREDENTIALS`. It is a single string in the format `oidc_provider/client_id/client_secret` that should be split into its components when used.
- `token_provider`: The provider refers to the OIDC IDP alias that needs to be used to exchange the incoming token to an external token. This is required if the `OPENEO_AUTH_METHOD` is set to `USER_CREDENTIALS`. For example, if you have a Keycloak setup with an IDP alias `openeo-idp`, you would set this field to `openeo-idp`. This means that when a user authenticates with their token, the Dispatcher will use the `openeo-idp` to exchange the user's token for a token that is valid for the openEO backend.
- `token_prefix`: An optional prefix to be added to the token when authenticating (e.g., "CDSE"). The prefix is required by some backends to identify the token type. This will be prepended to the exchanged token when authenticating with the openEO backend.

## Example Configuration
Here is an example of setting the environment variables in a `.env` file:

```env
# General Settings
APP_NAME="APEx Dispatch API"
APP_DESCRIPTION="APEx Dispatch Service API to run jobs and upscaling tasks"
APP_ENV=development

CORS_ALLOWED_ORIGINS=http://localhost:5173

# Database Settings
DATABASE_URL=sqlite:///:memory:

# Keycloak Settings
KEYCLOAK_HOST=localhost
KEYCLOAK_REALM=apex
KEYCLOAK_CLIENT_ID=apex-client-id
KEYCLOAK_CLIENT_SECRET=apex-client-secret


# openEO Settings
OPENEO_AUTH_METHOD=USER_CREDENTIALS
OPENEO_BACKENDS='{"https://openeo.backend1.com" {"client_credentials": "oidc_provider/client_id/secret_secret", "token_provider": "backend", "token_prefix": "oidc/backend"}}'
```