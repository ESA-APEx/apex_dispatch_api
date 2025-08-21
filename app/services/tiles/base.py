from typing import Callable, Dict
from geojson_pydantic import GeometryCollection, Polygon
from loguru import logger
from app.schemas.tiles import GridTypeEnum

GRID_REGISTRY: Dict[GridTypeEnum, Callable[[Polygon], GeometryCollection]] = {}


def register_grid(grid_type: GridTypeEnum):
    def decorator(func: Callable[[Polygon], GeometryCollection]):
        GRID_REGISTRY[grid_type] = func
        return func

    return decorator


def split_polygon_by_grid(polygon: Polygon, grid: GridTypeEnum) -> GeometryCollection:
    """
    Split a GeoJSON Polygon into smaller polygons according to the specified grid type.

    :param polygon: The GeoJSON Polygon to split.
    :param grid: The grid type to use for splitting.
    :return: A list of GeoJSON Polygons.
    :raises ValueError: If the grid type is unknown.
    """
    if grid.lower() not in GRID_REGISTRY:
        logger.error(f"An unknown grid was requested: {grid}")
        raise ValueError(f"Unknown grid: {grid}")

    split_func = GRID_REGISTRY[grid]
    return split_func(polygon)
