from fastapi import FastAPI

from app.middleware.correlation_id import add_correlation_id
from app.platforms.dispatcher import load_processing_platforms
from .config.logger import setup_logging
from .config.settings import settings
from .routers import jobs_status, unit_jobs, health, tiles

setup_logging()

load_processing_platforms()

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version="1.0.0",
)

app.middleware("http")(add_correlation_id)

# Register Keycloak - must be done after FastAPI app creation
# keycloak.register(app, prefix="/auth")  # mounts OIDC endpoints for login if needed

# include routers
app.include_router(tiles.router)
app.include_router(jobs_status.router)
app.include_router(unit_jobs.router)
app.include_router(health.router)
