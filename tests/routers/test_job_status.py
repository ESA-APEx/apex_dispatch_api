import json
from unittest.mock import patch


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
