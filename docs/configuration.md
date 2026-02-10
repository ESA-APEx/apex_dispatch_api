# Configuring the Dispatcher
The Dispatcher can be configured using environment variables. These variables can be set directly in your shell or defined in a `.env` file for convenience.
Below are the key settings that can be adjusted to tailor the Dispatcher's behavior to your needs. 

| Environment Variable     | Description                                                        | Values                        | Default Value     |
| ------------------------ | ------------------------------------------------------------------ | ----------------------------- | ----------------- |
| **General Settings**     |                                                                    |                               |                   |
| `APP_NAME`               | The name of the application.                                       | Text                          | APEx Dispatch API |
| `APP_DESCRIPTION`        | A brief description of the application.                            | Text                          | ""                |
| `APP_ENV`                | The environment in which the application is running                | `development` /  `production` | development       |
| `CORS_ALLOWED_ORIGINS`   | Comma-separated list of allowed origins for CORS.                  | Text                          | ""                |
| **Database Settings**    |                                                                    |                               |                   |
| `DATABASE_URL`           | The database connection URL.                                       | Text                          | ""                |
| **Keycloak Settings**    |                                                                    |                               |                   |
| `KEYCLOAK_HOST`          | The hostname and protocol of the Keycloak server.                  | Text                          | http://localhost  |
| `KEYCLOAK_REALM`         | The Keycloak realm to use for authentication.                      | Text                          | ""                |
| `KEYCLOAK_CLIENT_ID`     | The client ID registered in Keycloak.                              | Text                          | ""                |
| `KEYCLOAK_CLIENT_SECRET` | The client secret for the Keycloak client.                         | Text                          | ""                |
| **Backend Settings**     |                                                                    |                               |                   |
| `BACKENDS`               | JSON string defining the configuration for the supported backends. | JSON                          | `{}`              |


## Backend Configuration
The `BACKENDS` environment variable allows you to specify the configuration for multiple backends, to support within the Dispatcher API in JSON format.
Here is an example of how to structure this configuration:  

```json
{
  "https://openeo.backend1.com": {
    "auth_method": "CLIENT_CREDENTIALS",
    "client_credentials": "oidc_provider/client_id/secret_secret",
  },
 "https://openeo.backend2.com": {
    "auth_method": "USER_CREDENTIALS",
    "token_provider": "backend",
    "token_prefix": "oidc/backend"
  }, 
  ...
}
```
Each backend is configured by including a new key based on the backend URL. For each provided URL, the specific backend configuration can include the following fields:

- `auth_method`: The authentication method to use for the backend. This value can either be `USER_CREDENTIALS` or `CLIENT_CREDENTIALS`. The default value is set to `USER_CREDENTIALS`.
- `client_credentials`: The client credentials for authenticating with the backend. This is required if the `auth_method` is set to `CLIENT_CREDENTIALS`. It is a single string in the format `oidc_provider/client_id/client_secret` that should be split into its components when used.
- `token_provider`: The provider refers to the OIDC IDP alias that needs to be used to exchange the incoming token to an external token. This is required if the `auth_method` is set to `USER_CREDENTIALS`. For example, if you have a Keycloak setup with an IDP alias `backend-idp`, you would set this field to `backend-idp`. This means that when a user authenticates with their token, the Dispatcher will use the `backend-idp` to exchange the user's token for a token that is valid for the corresponding backend.
- `token_prefix`: An optional prefix to be added to the token when authenticating (e.g., "CDSE"). The prefix is required by some backends to identify the token type. This will be prepended to the exchanged token when authenticating with the backend.

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
KEYCLOAK_HOST=http://localhost
KEYCLOAK_REALM=apex
KEYCLOAK_CLIENT_ID=apex-client-id
KEYCLOAK_CLIENT_SECRET=apex-client-secret


BACKENDS='{"https://openeo.backend1.com" {"auth_method": "CLIENT_CREDENTIALS", "client_credentials": "oidc_provider/client_id/secret_secret"}, "https://openeo.backend2.com" {"auth_method": "USER_CREDENTIALS",  "token_provider": "backend", "token_prefix": "oidc/backend"}}'
```