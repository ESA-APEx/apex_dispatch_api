import json
from unittest.mock import patch, MagicMock

import pytest

from app.database.models.processing_job import ProcessingJobRecord
from app.schemas import BaseJobRequest, ProcessingJob, ProcessingJobSummary, ProcessingStatusEnum, ProcessTypeEnum, ServiceDetails
from app.services.processing import create_processing_job, get_processing_job_by_user_id, get_processing_jobs_by_user_id


def make_job_request():
    """Helper to build a valid job request."""
    return BaseJobRequest(
        label=ProcessTypeEnum.OPENEO,
        title="Test Job",
        service= ServiceDetails(
            service="dummy-service-id",
            application="dummy-application"
        ),
        parameters={"param": 1}
    )


@patch("app.services.processing.save_job_to_db")
@patch("app.services.processing.get_processing_platform")
def test_create_processing_job_calls_platform_execute(mock_get_platform, mock_save_job_to_db, fake_db_session):
    
    # Arrange
    fake_job= make_job_request()
    fake_result = 1
    fake_summary = ProcessingJobSummary(id=fake_result, title=fake_job.title, label=ProcessTypeEnum.OPENEO ,status=ProcessingStatusEnum.CREATED,)
    fake_record = ProcessingJobRecord(id=fake_result, title=fake_summary.title, label=ProcessTypeEnum.OPENEO, status=ProcessingStatusEnum.CREATED)
    fake_platform = MagicMock()

    fake_platform.execute_job.return_value = fake_result 
    mock_get_platform.return_value = fake_platform
    
    mock_save_job_to_db.return_value =fake_record

    result = create_processing_job(fake_db_session, "foobar", fake_job)

    mock_get_platform.assert_called_once_with(fake_job.label)
    fake_platform.execute_job.assert_called_once_with(
        title=fake_job.title,
        details=fake_job.service,
        parameters=fake_job.parameters
    )
    mock_save_job_to_db.assert_called_once()
    assert result == fake_summary
    
    
@patch("app.services.processing.get_processing_platform")
def test_create_processing_job_platform_raises(mock_get_platform, fake_db_session):
    fake_summary = make_job_request() 
    mock_get_platform.side_effect = ValueError("Unsupported platform")

    with pytest.raises(ValueError, match="Unsupported platform"):
        create_processing_job(fake_db_session, "foobar", fake_summary)

@patch("app.services.processing.get_jobs_by_user_id")
def test_get_processing_jobs_by_user_id(mock_get_jobs, fake_db_session):
    # Arrange
    fake_db_records = [
        MagicMock(id=1, title="Job 1", label=ProcessTypeEnum.OPENEO, status=ProcessingStatusEnum.CREATED),
        MagicMock(id=2, title="Job 2", label=ProcessTypeEnum.OGC_API_PROCESS, status=ProcessingStatusEnum.CREATED),
    ]
    mock_get_jobs.return_value = fake_db_records

    # Act
    results = get_processing_jobs_by_user_id(fake_db_session, "user1")

    # Assert
    mock_get_jobs.assert_called_once_with(fake_db_session, "user1")
    assert len(results) == len(fake_db_records)
    for i, job_summary in enumerate(results):
        assert job_summary.id == fake_db_records[i].id
        assert job_summary.title == fake_db_records[i].title
        assert job_summary.status == fake_db_records[i].status

        
@patch("app.services.processing.get_job_by_user_id")
def test_get_processing_job_by_user_id(mock_get_job, fake_db_session):
    
    fake_service_details = {
        "service": "https://openeofed.dataspace.copernicus.eu",
        "application": "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/32ea3c9a6fa24fe063cb59164cd318cceb7209b0/openeo_udp/variabilitymap/variabilitymap.json"
    }
    fake_result = ProcessingJobRecord(
        id=1,
        title="Test Job",
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
        user_id="user-123",
        platform_job_id="platform-job-456",
        parameters=json.dumps({"param1": "value1"}),
        result_link=None,
        created="2025-08-11T10:00:00",
        updated="2025-08-11T10:00:00",
        # Double-encoded JSON
        service_record=json.dumps(json.dumps(fake_service_details)),
    )
    mock_get_job.return_value = fake_result

    result = get_processing_job_by_user_id(fake_db_session, 1, "user1")

    mock_get_job.assert_called_once_with(fake_db_session, 1, "user1")
    assert isinstance(result, ProcessingJob)
    assert result.id == 1
    assert result.title == "Test Job"
    assert result.status == ProcessingStatusEnum.CREATED
    assert isinstance(result.service, ServiceDetails)
    assert result.service.service == fake_service_details["service"]
    assert result.service.application == fake_service_details["application"]
    assert result.parameters == {"param1": "value1"}

@patch("app.services.processing.get_job_by_user_id")
def test_get_processing_job_by_user_id_returns_none(mock_get_job, fake_db_session):

    mock_get_job.return_value = None

    result = get_processing_job_by_user_id(fake_db_session, 1, "user1")

    mock_get_job.assert_called_once_with(fake_db_session, 1, "user1")
    assert result == None