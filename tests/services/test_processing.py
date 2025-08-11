from unittest.mock import patch, MagicMock

import pytest

from app.database.models.processing_job import ProcessingJobRecord
from app.schemas import BaseJobRequest, ProcessingJobSummary, ProcessType, ProcessingStatusEnum, ServiceDetails
from app.services.processing import create_processing_job


def make_job_request():
    """Helper to build a valid job request."""
    return BaseJobRequest(
        label=ProcessType.OPENEO,
        title="Test Job",
        service= ServiceDetails(
            service="dummy-service-id",
            application="dummy-application"
        ),
        parameters={"param": 1}
    )


@patch("app.services.processing.save_job_to_db")
@patch("app.services.processing.get_processing_platform")
def test_create_processing_job_calls_platform_execute(mock_get_platform, mock_save_job_to_db):
    
    # Arrange
    fake_job= make_job_request()
    fake_result = 1
    fake_summary = ProcessingJobSummary(id=fake_result, title=fake_job.title, status=ProcessingStatusEnum.CREATED,)
    fake_record = ProcessingJobRecord(id=fake_result, title=fake_summary.title, status=ProcessingStatusEnum.CREATED)
    fake_platform = MagicMock()

    fake_platform.execute_job.return_value = fake_result 
    mock_get_platform.return_value = fake_platform
    
    mock_save_job_to_db.return_value =fake_record

    result = create_processing_job(None, "foobar", fake_job)

    mock_get_platform.assert_called_once_with(fake_job.label)
    fake_platform.execute_job.assert_called_once_with(
        title=fake_job.title,
        details=fake_job.service,
        parameters=fake_job.parameters
    )
    mock_save_job_to_db.assert_called_once()
    assert result == fake_summary
    
    
@patch("app.services.processing.save_job_to_db")
@patch("app.services.processing.get_processing_platform")
def test_create_processing_job_platform_raises(mock_get_platform, mock_save_job_to_db):
    fake_summary = make_job_request() 
    mock_get_platform.side_effect = ValueError("Unsupported platform")

    with pytest.raises(ValueError, match="Unsupported platform"):
        create_processing_job(None, "foobar", fake_summary)
