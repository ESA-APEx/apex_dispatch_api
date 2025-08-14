from geojson_pydantic import GeometryCollection, Polygon
import pytest

from app.schemas.tiles import GridTypeEnum
from app.services.tiles.base import split_polygon_by_grid


def test_split_polygon_by_grid_known_grid():
    coords = [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]]
    polygon = Polygon(type="Polygon", coordinates=coords)

    # Should work with known grid
    result = split_polygon_by_grid(polygon, GridTypeEnum.KM_20)
    assert isinstance(result, GeometryCollection)
    assert len(result.geometries) >= 36


def test_split_polygon_by_grid_unknown_grid_raises():
    coords = [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]]
    polygon = Polygon(type="Polygon", coordinates=coords)

    with pytest.raises(ValueError):
        split_polygon_by_grid(polygon, "UNKNOWN_GRID")
