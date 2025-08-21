from geojson_pydantic import GeometryCollection, Polygon

from app.services.tiles.grids.km_grids import _split_by_km_grid, split_by_20x20_km_grid


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
