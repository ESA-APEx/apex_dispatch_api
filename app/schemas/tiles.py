from enum import Enum
from pydantic import BaseModel
from geojson_pydantic import Polygon


class GridTypeEnum(str, Enum):
    KM_20 = "20x20km"


class TileRequest(BaseModel):
    aoi: Polygon
    grid: GridTypeEnum


# class TileResponse(BaseModel):
#     tiles: List[Tile] = []
