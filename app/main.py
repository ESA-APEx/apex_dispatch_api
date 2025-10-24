from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.correlation_id import add_correlation_id
from app.platforms.dispatcher import load_processing_platforms
from app.services.tiles.base import load_grids
from app.config.logger import setup_logging
from app.config.settings import settings
from app.routers import jobs_status, unit_jobs, health, tiles, upscale_tasks, sync_jobs

setup_logging()

load_processing_platforms()
load_grids()

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(add_correlation_id)

# include routers
app.include_router(tiles.router)
app.include_router(jobs_status.router)
app.include_router(unit_jobs.router)
app.include_router(sync_jobs.router)
app.include_router(upscale_tasks.router)
app.include_router(health.router)
