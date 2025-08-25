import json
from unittest.mock import AsyncMock, patch

from fastapi import WebSocketDisconnect
import pytest

from app.schemas.jobs_status import JobsStatusResponse


@patch("app.routers.jobs_status.get_processing_jobs_by_user_id")
@patch("app.routers.jobs_status.get_upscaling_tasks_by_user_id")
def test_unit_jobs_get_200(
    mock_get_upscaling_tasks,
    mock_get_processing_jobs,
    client,
    fake_processing_job_summary,
    fake_upscaling_task_summary,
):

    mock_get_processing_jobs.return_value = [fake_processing_job_summary]
    mock_get_upscaling_tasks.return_value = [fake_upscaling_task_summary]

    r = client.get("/jobs_status")
    assert r.status_code == 200
    assert json.dumps(r.json(), indent=1) == JobsStatusResponse(
        upscaling_tasks=[fake_upscaling_task_summary],
        processing_jobs=[fake_processing_job_summary],
    ).model_dump_json(indent=1)


@pytest.mark.asyncio
@patch("app.auth.get_current_user_id", new_callable=AsyncMock)
@patch("app.routers.jobs_status.get_jobs_status", new_callable=AsyncMock)
async def test_ws_jobs_status(
    mock_get_jobs_status,
    mock_get_user_id,
    client,
    fake_processing_job_summary,
    fake_upscaling_task_summary,
):
    mock_get_user_id.return_value = "foobar"
    mock_get_jobs_status.return_value = JobsStatusResponse(
        upscaling_tasks=[fake_upscaling_task_summary],
        processing_jobs=[fake_processing_job_summary],
    )

    with client.websocket_connect("/ws/jobs_status?interval=1&token=123") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        data = websocket.receive_json()
        assert data["data"] == {
            "upscaling_tasks": [fake_upscaling_task_summary.model_dump()],
            "processing_jobs": [fake_processing_job_summary.model_dump()],
        }


@pytest.mark.asyncio
@patch("app.auth.get_current_user_id", new_callable=AsyncMock)
@patch("app.routers.jobs_status.get_jobs_status", new_callable=AsyncMock)
async def test_ws_jobs_status_closes_on_error(
    mock_get_jobs_status, mock_get_user_id, client
):
    mock_get_user_id.return_value = "foobar"
    mock_get_jobs_status.side_effect = RuntimeError("Database connection lost")

    with client.websocket_connect("/ws/jobs_status?token=123") as websocket:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_json()
            websocket.receive_json()
            websocket.receive_json()

        assert exc_info.value.code == 1011
