from geojson_pydantic import GeometryCollection, Polygon
import pytest

from app.schemas.tiles import GridTypeEnum
from app.services.tiles import (
    _split_by_km_grid,
    split_by_20x20_km_grid,
    split_polygon_by_grid,
)


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


def test__split_by_km_grid_creates_multiple_cells():
    coords = [[(0, 0), (0.36, 0), (0.36, 0.36), (0, 0.36), (0, 0)]]
    polygon = Polygon(type="Polygon", coordinates=coords)

    result = _split_by_km_grid(polygon, 10.0)

    assert len(result) == 25
    for geom in result:
        assert geom.type == "Polygon"


def test_split_by_20x20_km_grid_returns_geometry_collection():
    coords = [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]]
    polygon = Polygon(type="Polygon", coordinates=coords)

    result = split_by_20x20_km_grid(polygon)

    assert isinstance(result, GeometryCollection)
    assert len(result.geometries) == 36
    for geom in result.geometries:
        assert geom.type == "Polygon"
