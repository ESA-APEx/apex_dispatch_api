from fastapi_keycloak import FastAPIKeycloak
from .config.settings import settings

# create the FastAPIKeycloak instance — used to protect routes
# The server_url must include trailing slash for library
keycloak = FastAPIKeycloak(
    server_url=str(settings.keycloak_server_url),
    client_id=settings.keycloak_client_id,
    client_secret=settings.keycloak_client_secret,
    admin_client_secret=settings.keycloak_client_secret,  # optional for admin operations
    realm=settings.keycloak_realm,
    callback_uri="http://localhost:8000/callback",  # for auth code flow if needed
)

# expose a helper dependency for current user
get_current_user = keycloak.get_current_user
get_current_active_user = keycloak.get_current_user
