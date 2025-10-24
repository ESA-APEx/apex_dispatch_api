import json
from unittest.mock import patch

from fastapi import HTTPException


@patch("app.routers.sync_jobs.create_synchronous_job")
def test_sync_jobs_create_201(
    mock_create_sync_job, client, fake_sync_response, fake_processing_job_request
):

    mock_create_sync_job.return_value = fake_sync_response

    r = client.post("/sync_jobs", json=fake_processing_job_request.model_dump())
    assert r.status_code == fake_sync_response.status_code
    assert r.json() == json.loads(fake_sync_response.body)
    assert r.headers.get("content-type") == fake_sync_response.media_type


@patch("app.routers.sync_jobs.create_synchronous_job")
def test_sync_jobs_create_500(
    mock_create_sync_job,
    client,
    fake_processing_job_request,
):

    mock_create_sync_job.side_effect = SystemError("Could not launch the job")

    r = client.post("/sync_jobs", json=fake_processing_job_request.model_dump())
    assert r.status_code == 500
    assert "could not launch the job" in r.json().get("detail", "").lower()


@patch("app.routers.sync_jobs.create_synchronous_job")
def test_sync_jobs_create_http_error(
    mock_create_sync_job,
    client,
    fake_processing_job_request,
):

    mock_create_sync_job.side_effect = HTTPException(
        status_code=503, detail="Oops, service unavailable"
    )

    r = client.post("/sync_jobs", json=fake_processing_job_request.model_dump())
    assert r.status_code == 503
    assert "service unavailable" in r.json().get("detail", "").lower()
