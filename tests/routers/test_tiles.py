from unittest.mock import patch
import pytest
from app.schemas.tiles import GridTypeEnum
from fastapi import status


@pytest.fixture
def dummy_payload():
    coords = [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]]
    return {
        "aoi": {
            "type": "Polygon",
            "coordinates": coords,
        },
        "grid": GridTypeEnum.KM_20,
    }


def test_split_in_tiles_success(client, dummy_payload):
    response = client.post("/tiles", json=dummy_payload)
    assert response.status_code == 201
    data = response.json()
    assert "geometries" in data
    assert len(data["geometries"]) == 36
    assert data["type"] == "GeometryCollection"


@patch("app.routers.tiles.split_polygon_by_grid")
def test_split_in_tiles_unknown_grid(mock_split, client, dummy_payload):
    mock_split.side_effect = ValueError("Unknown grid: INVALID_GRID")
    response = client.post("/tiles", json=dummy_payload)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "An error occurred while calculating tiles for 20x20km" in response.json()["message"]
