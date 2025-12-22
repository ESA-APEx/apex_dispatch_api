import json
from unittest.mock import ANY, AsyncMock, patch, MagicMock

import pytest

from app.database.models.processing_job import ProcessingJobRecord
from app.schemas.enum import OutputFormatEnum, ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.unit_job import (
    BaseJobRequest,
    ProcessingJob,
    ProcessingJobSummary,
    ServiceDetails,
)
from app.services.processing import (
    create_processing_job,
    create_synchronous_job,
    get_processing_job_results,
    get_job_status,
    get_processing_job_by_user_id,
    get_processing_jobs_by_user_id,
    retrieve_service_parameters,
)


def make_job_request():
    """Helper to build a valid job request."""
    return BaseJobRequest(
        label=ProcessTypeEnum.OPENEO,
        title="Test Job",
        service=ServiceDetails(
            endpoint="dummy-service-id", application="dummy-application"
        ),
        parameters={"param": 1},
        format=OutputFormatEnum.GEOTIFF,
    )


def make_job_record(status, service_details) -> ProcessingJobRecord:
    return ProcessingJobRecord(
        id=1,
        title="Test Job",
        label=ProcessTypeEnum.OPENEO,
        status=status,
        user_id="user-123",
        platform_job_id="platform-job-456",
        parameters=json.dumps({"param1": "value1"}),
        created="2025-08-11T10:00:00",
        updated="2025-08-11T10:00:00",
        service=json.dumps(service_details),
    )


@pytest.mark.asyncio
@patch("app.services.processing.save_job_to_db")
@patch("app.services.processing.get_processing_platform")
@patch("app.services.processing.get_current_user_id")
async def test_create_processing_job_calls_platform_execute(
    mock_current_user, mock_get_platform, mock_save_job_to_db, fake_db_session
):

    # Arrange
    fake_job = make_job_request()
    fake_result = 1
    fake_summary = ProcessingJobSummary(
        id=fake_result,
        title=fake_job.title,
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
        parameters=fake_job.parameters,
        service=fake_job.service,
    )
    fake_record = ProcessingJobRecord(
        id=fake_result,
        title=fake_summary.title,
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
    )
    fake_platform = MagicMock()

    fake_platform.execute_job = AsyncMock(return_value=fake_result)
    mock_get_platform.return_value = fake_platform

    mock_save_job_to_db.return_value = fake_record

    mock_current_user.return_value = "foobar"

    result = await create_processing_job(
        "foobar-token", fake_db_session, fake_job, None
    )

    mock_get_platform.assert_called_once_with(fake_job.label)
    fake_platform.execute_job.assert_called_once_with(
        user_token="foobar-token",
        title=fake_job.title,
        details=fake_job.service,
        parameters=fake_job.parameters,
        format=fake_job.format,
    )
    mock_save_job_to_db.assert_called_once()
    args, _ = mock_save_job_to_db.call_args
    saved_record = args[1]
    assert saved_record.status == ProcessingStatusEnum.CREATED
    assert result == fake_summary


@pytest.mark.asyncio
@patch("app.services.processing.save_job_to_db")
@patch("app.services.processing.get_processing_platform")
@patch("app.services.processing.get_current_user_id")
async def test_create_processing_job_calls_platform_execute_failure(
    mock_current_user, mock_get_platform, mock_save_job_to_db, fake_db_session
):

    # Arrange
    fake_job = make_job_request()
    fake_result = 1
    fake_summary = ProcessingJobSummary(
        id=fake_result,
        title=fake_job.title,
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
        parameters=fake_job.parameters,
        service=fake_job.service,
    )
    fake_record = ProcessingJobRecord(
        id=fake_result,
        title=fake_summary.title,
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
    )
    fake_platform = MagicMock()

    fake_platform.execute_job.side_effect = SystemError(
        "Could not authenticate with platform"
    )
    mock_get_platform.return_value = fake_platform

    mock_save_job_to_db.return_value = fake_record

    mock_current_user.return_value = "foobar"

    with pytest.raises(SystemError):
        await create_processing_job("foobar-token", fake_db_session, fake_job, None)

    mock_get_platform.assert_called_once_with(fake_job.label)
    fake_platform.execute_job.assert_called_once_with(
        user_token="foobar-token",
        title=fake_job.title,
        details=fake_job.service,
        parameters=fake_job.parameters,
        format=fake_job.format,
    )
    mock_save_job_to_db.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.processing.save_job_to_db")
@patch("app.services.processing.get_processing_platform")
@patch("app.services.processing.get_current_user_id")
async def test_create_processing_job_calls_platform_execute_failure_save_when_upscaling(
    mock_current_user, mock_get_platform, mock_save_job_to_db, fake_db_session
):

    # Arrange
    fake_job = make_job_request()
    fake_result = 1
    fake_summary = ProcessingJobSummary(
        id=fake_result,
        title=fake_job.title,
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
        parameters=fake_job.parameters,
        service=fake_job.service,
    )
    fake_record = ProcessingJobRecord(
        id=fake_result,
        title=fake_summary.title,
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
    )
    fake_platform = MagicMock()

    fake_platform.execute_job.side_effect = SystemError(
        "Could not authenticate with platform"
    )
    mock_get_platform.return_value = fake_platform

    mock_save_job_to_db.return_value = fake_record

    mock_current_user.return_value = "foobar"

    result = await create_processing_job("foobar-token", fake_db_session, fake_job, 1)

    mock_get_platform.assert_called_once_with(fake_job.label)
    fake_platform.execute_job.assert_called_once_with(
        user_token="foobar-token",
        title=fake_job.title,
        details=fake_job.service,
        parameters=fake_job.parameters,
        format=fake_job.format,
    )

    mock_save_job_to_db.assert_called_once()
    args, _ = mock_save_job_to_db.call_args
    saved_record = args[1]
    assert saved_record.status == ProcessingStatusEnum.FAILED
    assert result == fake_summary


@pytest.mark.asyncio
@patch("app.services.processing.get_processing_platform")
@patch("app.services.processing.get_current_user_id")
async def test_create_processing_job_platform_raises(
    mock_current_user, mock_get_platform, fake_db_session
):
    fake_summary = make_job_request()
    mock_get_platform.side_effect = ValueError("Unsupported platform")

    mock_current_user.return_value = "foobar"

    with pytest.raises(ValueError, match="Unsupported platform"):
        await create_processing_job("foobar-token", fake_db_session, fake_summary, None)


@pytest.mark.asyncio
@patch("app.services.processing.update_job_status_by_id")
@patch("app.services.processing.get_job_status")
@patch("app.services.processing.get_jobs_by_user_id")
@patch("app.services.processing.get_current_user_id")
async def test_get_processing_jobs_with_active_and_inactive_statuses(
    mock_current_user,
    mock_get_jobs,
    mock_get_job_status,
    mock_update_job_status,
    fake_db_session,
    fake_processing_job_record,
):
    inactive_job = ProcessingJobRecord(
        id=2,
        platform_job_id="platform456",
        label=ProcessTypeEnum.OGC_API_PROCESS,
        title="Finished Job",
        status=ProcessingStatusEnum.FAILED,
        parameters="{}",
        service=json.dumps({"application": "foo", "endpoint": "bar"}),
    )
    mock_get_jobs.return_value = [fake_processing_job_record, inactive_job]
    mock_get_job_status.return_value = ProcessingStatusEnum.RUNNING

    mock_current_user.return_value = "foobar"

    results = await get_processing_jobs_by_user_id("foobar-token", fake_db_session)

    assert len(results) == 2
    assert isinstance(results[0], ProcessingJobSummary)
    assert results[0].status == ProcessingStatusEnum.RUNNING
    assert results[1].status == ProcessingStatusEnum.FAILED

    # Active job should be refreshed
    mock_get_job_status.assert_called_once_with(
        "foobar-token", fake_processing_job_record
    )
    mock_update_job_status.assert_called_once_with(
        ANY, fake_processing_job_record.id, ProcessingStatusEnum.RUNNING
    )


@pytest.mark.asyncio
@patch("app.services.processing.update_job_status_by_id")
@patch("app.services.processing.get_job_status")
@patch("app.services.processing.get_jobs_by_user_id")
@patch("app.services.processing.get_current_user_id")
async def test_get_processing_jobs_no_updates(
    mock_current_user,
    mock_get_jobs,
    mock_get_job_status,
    mock_update_job_status,
    fake_db_session,
    fake_processing_job_record,
):
    mock_get_jobs.return_value = [fake_processing_job_record]
    mock_get_job_status.return_value = fake_processing_job_record.status

    mock_current_user.return_value = "foobar"

    results = await get_processing_jobs_by_user_id("foobar-token", fake_db_session)

    assert len(results) == 1
    assert results[0].status == fake_processing_job_record.status

    # Active job should be refreshed
    mock_get_job_status.assert_called_once_with(
        "foobar-token", fake_processing_job_record
    )
    mock_update_job_status.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.processing.get_processing_job_results")
@patch("app.services.processing.get_jobs_by_user_id")
@patch("app.services.processing.get_current_user_id")
async def test_get_processing_jobs_with_finished_statuses(
    mock_current_user,
    mock_get_jobs,
    mock_get_jobs_results,
    fake_db_session,
    fake_result,
):
    finished_job_no_result = ProcessingJobRecord(
        id=2,
        platform_job_id="platform456",
        label=ProcessTypeEnum.OGC_API_PROCESS,
        title="Finished Job",
        status=ProcessingStatusEnum.FINISHED,
        service=json.dumps({"application": "foo", "endpoint": "bar"}),
        parameters="{}",
    )
    finished_job_result = ProcessingJobRecord(
        id=3,
        platform_job_id="platform456",
        label=ProcessTypeEnum.OGC_API_PROCESS,
        title="Finished Job",
        status=ProcessingStatusEnum.FINISHED,
        service=json.dumps({"application": "foo", "endpoint": "bar"}),
        parameters="{}",
    )
    mock_get_jobs.return_value = [finished_job_no_result, finished_job_result]
    mock_get_jobs_results.return_value = fake_result

    mock_current_user.return_value = "foobar"

    results = await get_processing_jobs_by_user_id("foobar-token", fake_db_session)

    assert len(results) == 2
    assert isinstance(results[0], ProcessingJobSummary)


@pytest.mark.asyncio
@patch("app.services.processing.get_processing_platform")
async def test_get_job_status_from_platform(
    mock_get_platform, fake_processing_job_record
):

    fake_platform = MagicMock()
    fake_platform.get_job_status = AsyncMock(return_value=ProcessingStatusEnum.QUEUED)
    mock_get_platform.return_value = fake_platform

    status = await get_job_status("foobar-token", fake_processing_job_record)

    assert status == ProcessingStatusEnum.QUEUED


@pytest.mark.asyncio
@patch("app.services.processing.get_job_by_user_id")
@patch("app.services.processing.get_processing_platform")
@patch("app.services.processing.get_current_user_id")
async def test_get_job_result_from_platform(
    mock_current_user,
    mock_get_platform,
    mock_get_job_by_user_id,
    fake_processing_job_record,
    fake_db_session,
    fake_result,
):

    fake_platform = MagicMock()
    fake_platform.get_job_results = AsyncMock(return_value=fake_result)
    mock_get_platform.return_value = fake_platform
    mock_get_job_by_user_id.return_value = fake_processing_job_record

    mock_current_user.return_value = "foobar"

    result = await get_processing_job_results("foobar-token", fake_db_session, 1)

    assert result == fake_result


@pytest.mark.asyncio
@patch("app.services.processing.get_job_by_user_id")
@patch("app.services.processing.get_processing_platform")
@patch("app.services.processing.get_current_user_id")
async def test_get_job_result_from_platform_not_found(
    mock_current_user,
    mock_get_platform,
    mock_get_job_by_user_id,
    fake_processing_job_record,
    fake_db_session,
    fake_result,
):

    fake_platform = MagicMock()
    fake_platform.get_job_results = AsyncMock(return_value=fake_result)
    mock_get_platform.return_value = fake_platform
    mock_get_job_by_user_id.return_value = None

    mock_current_user.return_value = "foobar"

    result = await get_processing_job_results("foobar-token", fake_db_session, 1)

    assert result is None


@pytest.mark.asyncio
@patch("app.services.processing._refresh_job_status")
@patch("app.services.processing.get_job_by_user_id")
@patch("app.services.processing.get_current_user_id")
async def test_get_processing_job_by_user_id_active_status(
    mock_current_user, mock_get_job, mock_refresh_status, fake_db_session
):

    fake_service_details = {
        "endpoint": "https://openeofed.dataspace.copernicus.eu",
        "application": "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/"
        "32ea3c9a6fa24fe063cb59164cd318cceb7209b0/openeo_udp/variabilitymap/"
        "variabilitymap.json",
    }
    fake_result = make_job_record(ProcessingStatusEnum.CREATED, fake_service_details)
    mock_get_job.return_value = fake_result
    mock_refresh_status.return_value = fake_result

    mock_current_user.return_value = "foobar"

    result = await get_processing_job_by_user_id("foobar-token", fake_db_session, 1)

    mock_get_job.assert_called_once_with(fake_db_session, 1, "foobar")
    mock_refresh_status.assert_called_once()
    assert isinstance(result, ProcessingJob)
    assert result.id == 1
    assert result.title == "Test Job"
    assert result.status == ProcessingStatusEnum.CREATED
    assert isinstance(result.service, ServiceDetails)
    assert result.service.endpoint == fake_service_details["endpoint"]
    assert result.service.application == fake_service_details["application"]
    assert result.parameters == {"param1": "value1"}


@pytest.mark.asyncio
@patch("app.services.processing._refresh_job_status")
@patch("app.services.processing.get_job_by_user_id")
@patch("app.services.processing.get_current_user_id")
async def test_get_processing_job_by_user_id_inactive_status(
    mock_current_user, mock_get_job, mock_refresh_status, fake_db_session
):

    fake_service_details = {
        "endpoint": "https://openeofed.dataspace.copernicus.eu",
        "application": "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/"
        "32ea3c9a6fa24fe063cb59164cd318cceb7209b0/openeo_udp/variabilitymap/"
        "variabilitymap.json",
    }
    fake_result = make_job_record(ProcessingStatusEnum.FINISHED, fake_service_details)
    mock_get_job.return_value = fake_result
    mock_refresh_status.return_value = fake_result

    mock_current_user.return_value = "foobar"

    result = await get_processing_job_by_user_id("foobar-token", fake_db_session, 1)

    mock_get_job.assert_called_once_with(fake_db_session, 1, "foobar")
    mock_refresh_status.assert_not_called()
    assert isinstance(result, ProcessingJob)
    assert result.id == 1
    assert result.title == "Test Job"
    assert result.status == fake_result.status
    assert isinstance(result.service, ServiceDetails)
    assert result.service.endpoint == fake_service_details["endpoint"]
    assert result.service.application == fake_service_details["application"]
    assert result.parameters == {"param1": "value1"}


@pytest.mark.asyncio
@patch("app.services.processing.get_job_by_user_id")
@patch("app.services.processing.get_current_user_id")
async def test_get_processing_job_by_user_id_returns_none(
    mock_current_user, mock_get_job, fake_db_session
):

    mock_get_job.return_value = None

    mock_current_user.return_value = "foobar"

    result = await get_processing_job_by_user_id("foobar-user", fake_db_session, 1)

    mock_get_job.assert_called_once_with(fake_db_session, 1, "foobar")
    assert result is None


@pytest.mark.asyncio
@patch("app.services.processing.get_processing_platform")
async def test_create_sync_job_calls_platform_execute(
    mock_get_platform, fake_sync_response, fake_processing_job_request
):

    # Arrange
    fake_platform = MagicMock()

    fake_platform.execute_synchronous_job = AsyncMock(return_value=fake_sync_response)
    mock_get_platform.return_value = fake_platform

    result = await create_synchronous_job("foobar-token", fake_processing_job_request)

    mock_get_platform.assert_called_once_with(fake_processing_job_request.label)
    fake_platform.execute_synchronous_job.assert_called_once_with(
        user_token="foobar-token",
        title=fake_processing_job_request.title,
        details=fake_processing_job_request.service,
        parameters=fake_processing_job_request.parameters,
        format=fake_processing_job_request.format,
    )
    assert result == fake_sync_response


@pytest.mark.asyncio
@patch("app.services.processing.get_processing_platform")
async def test_create_sync_job_calls_platform_execute_failure(
    mock_get_platform, fake_sync_response, fake_processing_job_request
):

    # Arrange
    fake_platform = MagicMock()

    fake_platform.execute_synchronous_job.side_effect = SystemError(
        "Could not authenticate with platform"
    )
    mock_get_platform.return_value = fake_platform

    with pytest.raises(SystemError):
        await create_synchronous_job("foobar-token", fake_processing_job_request)

    mock_get_platform.assert_called_once_with(fake_processing_job_request.label)
    fake_platform.execute_synchronous_job.assert_called_once_with(
        user_token="foobar-token",
        title=fake_processing_job_request.title,
        details=fake_processing_job_request.service,
        parameters=fake_processing_job_request.parameters,
        format=fake_processing_job_request.format,
    )


@pytest.mark.asyncio
@patch("app.services.processing.get_processing_platform")
async def test_retrieve_service_parameters_success(
    mock_get_platform, fake_parameter_result, fake_param_request
):

    fake_platform = MagicMock()
    fake_platform.get_service_parameters = AsyncMock(return_value=fake_parameter_result)
    mock_get_platform.return_value = fake_platform

    result = await retrieve_service_parameters("foobar-token", fake_param_request)

    mock_get_platform.assert_called_once_with(fake_param_request.label)
    fake_platform.get_service_parameters.assert_called_once_with(
        user_token="foobar-token",
        details=fake_param_request.service,
    )
    assert result == fake_parameter_result
