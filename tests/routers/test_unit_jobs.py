import json
from unittest.mock import patch


@patch("app.routers.unit_jobs.create_processing_job")
def test_unit_jobs_create_201(
    mock_create_processing_job,
    client,
    fake_processing_job_request,
    fake_processing_job_summary,
):

    mock_create_processing_job.return_value = fake_processing_job_summary

    r = client.post("/unit_jobs", json=fake_processing_job_request.model_dump())
    assert r.status_code == 201
    assert r.json() == fake_processing_job_summary.model_dump()


@patch("app.routers.unit_jobs.create_processing_job")
def test_unit_jobs_create_500(
    mock_create_processing_job,
    client,
    fake_processing_job_request,
):

    mock_create_processing_job.side_effect = SystemError("Could not launch the job")

    r = client.post("/unit_jobs", json=fake_processing_job_request.model_dump())
    assert r.status_code == 500
    assert "could not launch the job" in r.json().get("detail", "").lower()


@patch("app.routers.unit_jobs.get_processing_job_by_user_id")
def test_unit_jobs_get_job_200(
    mock_get_processing_job,
    client,
    fake_processing_job,
):

    mock_get_processing_job.return_value = fake_processing_job

    r = client.get("/unit_jobs/1")
    assert r.status_code == 200
    assert json.dumps(r.json(), indent=1) == fake_processing_job.model_dump_json(
        indent=1
    )


@patch("app.routers.unit_jobs.get_processing_job_by_user_id")
def test_unit_jobs_get_job_404(
    mock_get_processing_job,
    client,
    fake_processing_job,
):

    mock_get_processing_job.return_value = None

    r = client.get("/unit_jobs/1")
    assert r.status_code == 404
    assert "processing job 1 not found" in r.json().get("detail", "").lower()
