import logging
from fastapi import APIRouter, HTTPException, status
from geojson_pydantic import GeometryCollection

from app.schemas.tiles import TileRequest
from app.services.tiles import split_polygon_by_grid


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/tiles",
    status_code=status.HTTP_201_CREATED,
    tags=["Upscale Tasks"],
    summary="Split an area of interest in a list of tiles.",
    description="Given a certain area of interest and a tiling grid definition (from the"
    "service’s Max AOI capacity), calculate the number of tiles to be"
    "processed by the upscaling service.",
)
def split_in_tiles(payload: TileRequest) -> GeometryCollection:
    try:
        logger.debug(f"Splitting tiles in a {payload.grid} formation")
        return split_polygon_by_grid(payload.aoi, payload.grid)
    except Exception as e:
        logger.exception(
            f"An error occurred while calculating tiles for {payload.grid}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while calculating tiles for {payload.grid}: {e}",
        )
