import json
from unittest.mock import ANY, call, patch, MagicMock

import pytest

from app.database.models.processing_job import ProcessingJobRecord
from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.unit_job import (
    BaseJobRequest,
    ProcessingJob,
    ProcessingJobSummary,
    ServiceDetails,
)
from app.services.processing import (
    create_processing_job,
    get_job_result_url,
    get_job_status,
    get_processing_job_by_user_id,
    get_processing_jobs_by_user_id,
)
from app.services.upscaling import create_upscaling_task


@patch("app.services.upscaling.create_processing_job")
@patch("app.services.upscaling.save_upscaling_task_to_db")
def test_create_upscaling_task_creates_jobs(
    mock_save_upscaling_task,
    mock_create_processing_job,
    fake_upscaling_task_request,
    fake_upscaling_task_record,
    fake_upscaling_task_summary,
    fake_processing_job_summary,
    fake_db_session,
):
    user = "foobar"
    mock_save_upscaling_task.return_value = fake_upscaling_task_record
    mock_create_processing_job.return_value = fake_processing_job_summary
    result = create_upscaling_task(fake_db_session, user, fake_upscaling_task_request)

    expected_calls = [
        call(
            database=fake_db_session,
            user=user,
            request=BaseJobRequest(
                title=f"{fake_upscaling_task_request.title} - Processing Job {idx + 1}",
                label=fake_upscaling_task_request.label,
                parameters={
                    **fake_upscaling_task_request.parameters,
                    fake_upscaling_task_request.dimension.name: value,
                },
                service=fake_upscaling_task_request.service,
            ),
            upscaling_task_id=fake_upscaling_task_record.id,
        )
        for idx, value in enumerate(fake_upscaling_task_request.dimension.values)
    ]

    mock_create_processing_job.assert_has_calls(expected_calls)
    mock_save_upscaling_task.assert_called_once()
    assert result == fake_upscaling_task_summary
