import logging
from typing import List

from geojson_pydantic import GeometryCollection, Polygon
from geojson_pydantic.geometries import Geometry, parse_geometry_obj
import pyproj
from shapely import box
from shapely.geometry import shape
from shapely.ops import transform

from app.schemas.tiles import GridTypeEnum
from app.services.tiles.base import register_grid


logger = logging.getLogger(__name__)


@register_grid(GridTypeEnum.KM_20)
def split_by_20x20_km_grid(polygon: Polygon) -> GeometryCollection:
    """
    Split polygon into 20x20 km tiles.

    :param polygon: The GeoJSON Polygon to split.
    :return: A list of GeoJSON Polygons.
    """
    logger.debug("Splitting polygon in a 20x20km grid")

    return GeometryCollection(
        type="GeometryCollection", geometries=_split_by_km_grid(polygon, 20.0)
    )


def _split_by_km_grid(aoi: Polygon, cell_size_km: float) -> List[Geometry]:
    """
    Splits a polygon into a list of smaller polygons based on a square grid of given size in km.

    :param aoi: Polygon in GeoJSON format.
    :param cell_size_km: Size of the grid cell in kilometers (default 20km).
    :return: List of polygons as GeoJSON dicts.
    """
    # Load the polygon
    polygon = shape(aoi)

    # Project to a local projection (meters) for accurate distance calculations
    proj_wgs84 = pyproj.CRS("EPSG:4326")
    proj_meters = pyproj.CRS("EPSG:3857")
    project_to_meters = pyproj.Transformer.from_crs(
        proj_wgs84, proj_meters, always_xy=True
    ).transform
    project_to_wgs84 = pyproj.Transformer.from_crs(
        proj_meters, proj_wgs84, always_xy=True
    ).transform

    polygon_m = transform(project_to_meters, polygon)
    min_x, min_y, max_x, max_y = polygon_m.bounds
    cell_size_m = cell_size_km * 1000  # convert km to meters

    result_polygons: List[Geometry] = []

    x = min_x
    while x < max_x:
        y = min_y
        while y < max_y:
            cell = box(x, y, x + cell_size_m, y + cell_size_m)
            intersection = polygon_m.intersection(cell)
            if not intersection.is_empty:
                # Transform back to WGS84
                intersection_wgs84 = transform(project_to_wgs84, intersection)
                result_polygons.append(
                    parse_geometry_obj(intersection_wgs84.__geo_interface__)
                )
            y += cell_size_m
        x += cell_size_m
    return result_polygons
