import json
from unittest.mock import patch


@patch("app.routers.sync_jobs.create_synchronous_job")
def test_sync_jobs_create_201(
    mock_create_synchronous_job,
    client,
    fake_processing_job_request,
    fake_sync_job_response,
):

    mock_create_synchronous_job.return_value = fake_sync_job_response

    r = client.post("/sync_jobs", json=fake_processing_job_request.model_dump())
    assert r.status_code == 201
    assert r.json() == fake_sync_job_response


@patch("app.routers.sync_jobs.create_synchronous_job")
def test_sync_jobs_create_500(
    mock_create_synchronous_job,
    client,
    fake_processing_job_request,
):

    mock_create_synchronous_job.side_effect = SystemError("Could not launch the job")

    r = client.post("/sync_jobs", json=fake_processing_job_request.model_dump())
    assert r.status_code == 500
    assert "could not launch the job" in r.json().get("detail", "").lower()
