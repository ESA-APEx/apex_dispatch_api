from datetime import datetime
from unittest.mock import patch

from fastapi import status

from app.schemas.statistics import (
    EntityStatistics,
    PublicStatisticsResponse,
    UpscalingStatistics,
)


@patch("app.routers.statistics.get_public_statistics")
def test_statistics_get_200(mock_get_public_statistics, client):
    mock_get_public_statistics.return_value = PublicStatisticsResponse(
        generated_at=datetime(2026, 1, 1, 12, 0, 0),
        processing_jobs=EntityStatistics(
            total=42,
            by_status={"finished": 30, "failed": 12},
            by_platform={"openeo": 40, "ogc_api_process": 2},
            by_service={
                "variabilitymap": 40,
                "land-cover": 2,
            },
        ),
        upscaling_tasks=UpscalingStatistics(
            total=10,
            by_status={"finished": 9, "failed": 1},
            by_platform={"openeo": 10},
            by_service={"variabilitymap": 10},
            average_processing_jobs_per_upscaling_task=4.2,
        ),
    )

    response = client.get("/statistics")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["processing_jobs"]["total"] == 42
    assert payload["upscaling_tasks"]["total"] == 10
    assert payload["upscaling_tasks"]["average_processing_jobs_per_upscaling_task"] == 4.2
    assert payload["processing_jobs"]["by_status"]["finished"] == 30
    assert payload["processing_jobs"]["by_service"]["variabilitymap"] == 40


@patch("app.routers.statistics.get_public_statistics")
def test_statistics_get_500(mock_get_public_statistics, client):
    mock_get_public_statistics.side_effect = RuntimeError("Database timeout")

    response = client.get("/statistics")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "An error occurred while retrieving public statistics." in response.json().get(
        "message", ""
    )


@patch("app.routers.statistics.get_public_statistics")
def test_statistics_get_200_with_date_filter(mock_get_public_statistics, client):
    mock_get_public_statistics.return_value = PublicStatisticsResponse(
        generated_at=datetime(2026, 1, 1, 12, 0, 0),
        processing_jobs=EntityStatistics(
            total=0,
            by_status={},
            by_platform={},
            by_service={},
        ),
        upscaling_tasks=UpscalingStatistics(
            total=0,
            by_status={},
            by_platform={},
            by_service={},
            average_processing_jobs_per_upscaling_task=0.0,
        ),
    )

    response = client.get("/statistics?date_from=2026-01-01&date_to=2026-01-31")

    assert response.status_code == status.HTTP_200_OK
    mock_get_public_statistics.assert_called_once()
    _, kwargs = mock_get_public_statistics.call_args
    assert kwargs["date_from"].isoformat() == "2026-01-01"
    assert kwargs["date_to"].isoformat() == "2026-01-31"


def test_statistics_get_400_when_date_range_invalid(client):
    response = client.get("/statistics?date_from=2026-02-01&date_to=2026-01-01")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "date_from must be before or equal to date_to" in response.json().get(
        "detail", ""
    )
