from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Body
from geojson_pydantic import GeometryCollection
from loguru import logger

from app.schemas.tiles import GridTypeEnum, TileRequest
from app.services.tiles.base import split_polygon_by_grid


router = APIRouter()


@router.post(
    "/tiles",
    status_code=status.HTTP_201_CREATED,
    tags=["Upscale Tasks"],
    summary="Split an area of interest in a list of tiles.",
    description="Given a certain area of interest and a tiling grid definition (from the"
    "service’s Max AOI capacity), calculate the number of tiles to be"
    "processed by the upscaling service.",
)
def split_in_tiles(
    payload: Annotated[
        TileRequest,
        Body(
            openapi_examples={
                "20x20 Grid": {
                    "summary": "Request to split up area in a 20x20km grid",
                    "description": "An example request of splitting up a given area of interest "
                    "into a 20 by 20km grid.",
                    "value": TileRequest(
                        grid=GridTypeEnum.KM_20,
                        aoi={
                            "coordinates": [
                                [
                                    [5.131074140132512, 51.352892918832026],
                                    [4.836037011633863, 51.331277680080774],
                                    [4.789036228520871, 51.12326419975835],
                                    [5.164855813583216, 51.11863683854557],
                                    [5.192048230607185, 51.33847556306924],
                                    [5.131074140132512, 51.352892918832026],
                                ]
                            ],
                            "type": "Polygon",
                        },
                    ),
                }
            }
        ),
    ],
) -> GeometryCollection:
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
