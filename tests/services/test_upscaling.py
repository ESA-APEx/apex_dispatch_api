from datetime import datetime
from unittest.mock import call, patch

from app.database.models.upscaling_task import UpscalingTaskRecord
from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.unit_job import (
    BaseJobRequest,
    ProcessingJobSummary,
)
from app.services.upscaling import (
    _get_upscale_status,
    _refresh_record_status,
    create_upscaling_processing_jobs,
    create_upscaling_task,
    get_upscaling_task_by_user_id,
    get_upscaling_tasks_by_user_id,
)


def make_job(status: ProcessingStatusEnum) -> ProcessingJobSummary:
    return ProcessingJobSummary(
        id=1,
        title="job",
        status=status,
        label=ProcessTypeEnum.OPENEO,
        parameters={"param1": "value1", "param2": "value2"},
    )


def make_upscaling_record(status: ProcessingJobSummary) -> UpscalingTaskRecord:
    return UpscalingTaskRecord(
        id=1,
        title="Dummy Record",
        label=ProcessTypeEnum.OPENEO,
        status=status,
        service='{"endpoint":"foo","application":"bar"}',
        created=datetime.now(),
        updated=datetime.now(),
    )


@patch("app.services.upscaling.save_upscaling_task_to_db")
def test_create_upscaling_task_creates_task(
    mock_save_upscaling_task,
    fake_upscaling_task_request,
    fake_upscaling_task_record,
    fake_upscaling_task_summary,
    fake_db_session,
):
    user = "foobar"
    mock_save_upscaling_task.return_value = fake_upscaling_task_record
    result = create_upscaling_task(fake_db_session, user, fake_upscaling_task_request)
    mock_save_upscaling_task.assert_called_once()
    assert result == fake_upscaling_task_summary


@patch("app.services.upscaling.create_processing_job")
def test_create_upscaling_task_creates_jobs(
    mock_create_processing_job,
    fake_upscaling_task_request,
    fake_upscaling_task_record,
    fake_processing_job_summary,
    fake_db_session,
):
    user = "foobar"
    mock_create_processing_job.return_value = fake_processing_job_summary
    result = create_upscaling_processing_jobs(
        fake_db_session, user, fake_upscaling_task_request, 1
    )

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
    assert len(result) == len(fake_upscaling_task_request.dimension.values)


def test_returns_running_if_any_running():
    jobs = [
        make_job(ProcessingStatusEnum.FAILED),
        make_job(ProcessingStatusEnum.RUNNING),
    ]
    assert _get_upscale_status(jobs) == ProcessingStatusEnum.RUNNING


def test_returns_failed_if_all_failed():
    jobs = [make_job(ProcessingStatusEnum.FAILED) for _ in range(3)]
    assert _get_upscale_status(jobs) == ProcessingStatusEnum.FAILED


def test_returns_canceled_if_all_canceled():
    jobs = [make_job(ProcessingStatusEnum.CANCELED) for _ in range(2)]
    assert _get_upscale_status(jobs) == ProcessingStatusEnum.CANCELED


def test_returns_finished_if_all_finished_or_failed():
    jobs = [
        make_job(ProcessingStatusEnum.FINISHED),
        make_job(ProcessingStatusEnum.FAILED),
    ]
    assert _get_upscale_status(jobs) == ProcessingStatusEnum.FINISHED


def test_returns_created_as_fallback():
    jobs = [
        make_job(ProcessingStatusEnum.CREATED),
        make_job(ProcessingStatusEnum.FINISHED),
    ]
    assert _get_upscale_status(jobs) == ProcessingStatusEnum.CREATED


def test_returns_created_when_no_jobs():
    jobs = []
    assert _get_upscale_status(jobs) == ProcessingStatusEnum.CREATED


@patch("app.services.upscaling.update_upscale_task_status_by_id")
def test_refresh_updates_status(
    mock_update, fake_db_session, fake_upscaling_task_record
):
    jobs = [make_job(ProcessingStatusEnum.RUNNING)]

    updated_record = _refresh_record_status(
        fake_db_session, fake_upscaling_task_record, jobs
    )

    assert updated_record.status == ProcessingStatusEnum.RUNNING
    mock_update.assert_called_once_with(
        fake_db_session, fake_upscaling_task_record.id, ProcessingStatusEnum.RUNNING
    )


@patch("app.services.upscaling.update_upscale_task_status_by_id")
def test_refresh_does_not_update_if_same(
    mock_update, fake_db_session, fake_upscaling_task_record
):
    jobs = [make_job(fake_upscaling_task_record.status)]

    updated_record = _refresh_record_status(
        fake_db_session, fake_upscaling_task_record, jobs
    )

    assert updated_record.status == fake_upscaling_task_record.status
    mock_update.assert_not_called()


@patch("app.services.upscaling.get_processing_jobs_by_user_id")
@patch("app.services.upscaling.get_upscale_task_by_user_id")
@patch("app.services.upscaling.update_upscale_task_status_by_id")
def test_returns_none_if_task_not_found(
    mock_update, mock_get_task, mock_get_jobs, fake_db_session
):
    mock_get_task.return_value = None

    result = get_upscaling_task_by_user_id(fake_db_session, task_id=123, user_id="foo")

    assert result is None
    mock_get_jobs.assert_not_called()
    mock_update.assert_not_called()


@patch("app.services.upscaling.get_processing_jobs_by_user_id")
@patch("app.services.upscaling.get_upscale_task_by_user_id")
@patch("app.services.upscaling._refresh_record_status")
def test_get_task_refreshes_status_if_active(
    mock_refresh,
    mock_get_task,
    mock_get_jobs,
    fake_db_session,
    fake_upscaling_task_record,
):
    mock_record = make_upscaling_record(ProcessingStatusEnum.RUNNING)
    mock_get_task.return_value = mock_record
    mock_get_jobs.return_value = [make_job(ProcessingStatusEnum.RUNNING)]
    mock_refresh.return_value = mock_record

    result = get_upscaling_task_by_user_id(fake_db_session, 1, "user1")

    assert result.id == mock_record.id
    mock_refresh.assert_called_once()
    mock_get_jobs.assert_called_once()


@patch("app.services.upscaling.get_processing_jobs_by_user_id")
@patch("app.services.upscaling.get_upscale_task_by_user_id")
@patch("app.services.upscaling._refresh_record_status")
def test_get_task_skips_refresh_if_inactive(
    mock_refresh, mock_get_task, mock_get_jobs, fake_db_session
):
    mock_record = make_upscaling_record(ProcessingStatusEnum.FINISHED)
    mock_get_task.return_value = mock_record
    mock_get_jobs.return_value = [make_job(ProcessingStatusEnum.FINISHED)]

    result = get_upscaling_task_by_user_id(fake_db_session, 2, "user1")

    assert result.id == mock_record.id
    mock_refresh.assert_not_called()
    mock_get_jobs.assert_called_once()


@patch("app.services.upscaling._refresh_record_status")
@patch("app.services.upscaling.get_processing_jobs_by_user_id")
@patch("app.services.upscaling.get_upscale_tasks_by_user_id")
def test_get_upscaling_tasks_refreshes_active(
    mock_get_tasks, mock_get_jobs, mock_refresh, fake_db_session
):
    record = make_upscaling_record(ProcessingStatusEnum.RUNNING)
    mock_get_tasks.return_value = [record]
    mock_get_jobs.return_value = [make_job(ProcessingStatusEnum.RUNNING)]
    mock_refresh.return_value = record

    result = get_upscaling_tasks_by_user_id(fake_db_session, "user1")

    assert len(result) == 1
    assert result[0].id == record.id
    assert result[0].status == record.status

    mock_get_jobs.assert_called_once_with(fake_db_session, "user1", 1)
    mock_refresh.assert_called_once_with(
        fake_db_session, record, mock_get_jobs.return_value
    )


@patch("app.services.upscaling._refresh_record_status")
@patch("app.services.upscaling.get_processing_jobs_by_user_id")
@patch("app.services.upscaling.get_upscale_tasks_by_user_id")
def test_get_upscaling_tasks_skips_inactive(
    mock_get_tasks, mock_get_jobs, mock_refresh, fake_db_session
):
    record = make_upscaling_record(ProcessingStatusEnum.FINISHED)
    mock_get_tasks.return_value = [record]

    result = get_upscaling_tasks_by_user_id(fake_db_session, "user1")

    assert len(result) == 1
    assert result[0].id == record.id
    assert result[0].status == record.status
    mock_get_jobs.assert_not_called()
    mock_refresh.assert_not_called()
