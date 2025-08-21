from enum import Enum
from pydantic import BaseModel, Field
from geojson_pydantic import Polygon


class GridTypeEnum(str, Enum):
    KM_20 = "20x20km"


class TileRequest(BaseModel):
    aoi: Polygon = Field(
        ...,
        description="Polygon representing the area of interest for which the tiling grid should "
        "be calculated",
    )
    grid: GridTypeEnum = Field(
        ...,
        description="Identifier of the grid system that needs to be used to split up the area of "
        "interest",
    )


# class TileResponse(BaseModel):
#     tiles: List[Tile] = []
