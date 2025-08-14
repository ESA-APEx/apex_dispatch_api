import json
from unittest.mock import AsyncMock, patch

from fastapi import WebSocketDisconnect
import pytest


from app.schemas import (
    JobsStatusResponse,
)


@patch("app.routers.jobs_status.get_processing_jobs_by_user_id")
def test_unit_jobs_get_200(
    mock_get_processing_jobs, client, fake_processing_job_summary
):

    mock_get_processing_jobs.return_value = [fake_processing_job_summary]

    r = client.get("/jobs_status")
    assert r.status_code == 200
    assert json.dumps(r.json(), indent=1) == JobsStatusResponse(
        upscaling_tasks=[], processing_jobs=[fake_processing_job_summary]
    ).model_dump_json(indent=1)


@pytest.mark.asyncio
@patch("app.routers.jobs_status.get_jobs_status", new_callable=AsyncMock)
async def test_ws_jobs_status(
    mock_get_jobs_status, client, fake_processing_job_summary
):
    mock_get_jobs_status.return_value = JobsStatusResponse(
        upscaling_tasks=[], processing_jobs=[fake_processing_job_summary]
    )

    with client.websocket_connect("/ws/jobs_status?interval=1") as websocket:
        data = websocket.receive_json()
        assert data == {
            "upscaling_tasks": [],
            "processing_jobs": [fake_processing_job_summary.model_dump()],
        }


@pytest.mark.asyncio
@patch("app.routers.jobs_status.get_jobs_status", new_callable=AsyncMock)
async def test_ws_jobs_status_closes_on_error(mock_get_jobs_status, client):
    mock_get_jobs_status.side_effect = RuntimeError("Database connection lost")

    with client.websocket_connect("/ws/jobs_status") as websocket:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_json()

        assert exc_info.value.code == 1011
