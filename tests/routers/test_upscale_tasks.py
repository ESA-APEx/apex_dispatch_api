import json
from unittest.mock import AsyncMock, patch

from fastapi import WebSocketDisconnect
import pytest


@patch("app.routers.upscale_tasks.create_upscaling_processing_jobs")
@patch("app.routers.upscale_tasks.create_upscaling_task")
def test_upscaling_task_create_201(
    mock_create_upscaling_task,
    mock_create_processing_jobs,
    client,
    fake_upscaling_task_request,
    fake_upscaling_task_summary,
):

    mock_create_upscaling_task.return_value = fake_upscaling_task_summary

    r = client.post("/upscale_tasks", json=fake_upscaling_task_request.model_dump())
    assert r.status_code == 201
    assert r.json() == fake_upscaling_task_summary.model_dump()
    assert mock_create_processing_jobs.called_once()


@patch("app.routers.upscale_tasks.create_upscaling_task")
def test_upscaling_task_create_500(
    mock_create_upscaling_task,
    client,
    fake_upscaling_task_request,
):

    mock_create_upscaling_task.side_effect = SystemError(
        "Could not launch the upscale task"
    )

    r = client.post("/upscale_tasks", json=fake_upscaling_task_request.model_dump())
    assert r.status_code == 500
    assert "could not launch the upscale task" in r.json().get("detail", "").lower()


@patch("app.routers.upscale_tasks.get_upscaling_task_by_user_id")
def test_upscaling_task_get_task_200(
    mock_get_upscale_task,
    client,
    fake_upscaling_task,
):

    mock_get_upscale_task.return_value = fake_upscaling_task

    r = client.get("/upscale_tasks/1")
    assert r.status_code == 200
    assert json.dumps(r.json(), indent=1) == fake_upscaling_task.model_dump_json(
        indent=1
    )


@patch("app.routers.upscale_tasks.get_upscaling_task_by_user_id")
def test_upscaling_task_get_task_404(mock_get_upscale_task, client):

    mock_get_upscale_task.return_value = None

    r = client.get("/upscale_tasks/1")
    assert r.status_code == 404
    assert "upscale task 1 not found" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
@patch("app.auth.get_current_user_id", new_callable=AsyncMock)
@patch("app.routers.upscale_tasks.get_upscale_task", new_callable=AsyncMock)
async def test_ws_jobs_status(
    mock_get_task_status, mock_get_user_id, client, fake_upscaling_task
):
    mock_get_user_id.return_value = "foobar"
    mock_get_task_status.return_value = fake_upscaling_task

    with client.websocket_connect("/ws/upscale_tasks/1?interval=1&token=123") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        data = websocket.receive_json()
        assert data["data"] == json.loads(fake_upscaling_task.model_dump_json())


@pytest.mark.asyncio
@patch("app.auth.get_current_user_id", new_callable=AsyncMock)
@patch("app.routers.upscale_tasks.get_upscale_task", new_callable=AsyncMock)
async def test_ws_jobs_status_closes_on_error(
    mock_get_task_status, mock_get_user_id, client
):
    mock_get_user_id.return_value = "foobar"
    mock_get_task_status.side_effect = RuntimeError("Database connection lost")

    with client.websocket_connect("/ws/upscale_tasks/1?token=123") as websocket:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_json()
            websocket.receive_json()
            websocket.receive_json()

        assert exc_info.value.code == 1011


@pytest.mark.asyncio
@patch("app.auth.get_current_user_id", new_callable=AsyncMock)
@patch("app.routers.upscale_tasks.get_upscale_task", new_callable=AsyncMock)
async def test_ws_jobs_status_not_found(
    mock_get_task_status, mock_get_user_id, client, fake_upscaling_task
):
    mock_get_user_id.return_value = "foobar"
    mock_get_task_status.return_value = None

    with client.websocket_connect(
        "/ws/upscale_tasks/1?interval=1&token=123"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()
        data = websocket.receive_json()
        assert data["type"] == "error"
        assert data["message"].lower() == "task not found"
