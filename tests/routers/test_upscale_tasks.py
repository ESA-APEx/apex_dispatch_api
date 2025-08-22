import json
from unittest.mock import patch


@patch("app.routers.upscale_tasks.create_upscaling_task")
def test_upscaling_task_create_201(
    mock_create_upscaling_task,
    client,
    fake_upscaling_task_request,
    fake_upscaling_task_summary,
):

    mock_create_upscaling_task.return_value = fake_upscaling_task_summary

    r = client.post("/upscale_tasks", json=fake_upscaling_task_request.model_dump())
    assert r.status_code == 201
    assert r.json() == fake_upscaling_task_summary.model_dump()


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
