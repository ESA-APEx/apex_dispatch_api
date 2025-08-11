from unittest.mock import patch, MagicMock

import pytest

from app.schemas import BaseJobRequest, ProcessingJobSummary, ProcessType, ServiceDetails
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


@patch("app.services.processing.get_processing_platform")
def test_create_processing_job_calls_platform_execute(mock_get_platform):
    
    # Arrange
    fake_summary = make_job_request()
    fake_result = ProcessingJobSummary(
        id="fake-job-id",
        title=fake_summary.title,
        status="created"
    )

    fake_platform = MagicMock()
    fake_platform.execute_job.return_value = fake_result
    mock_get_platform.return_value = fake_platform

    # Act
    result = create_processing_job(fake_summary)

    # Assert
    mock_get_platform.assert_called_once_with(fake_summary.label)
    fake_platform.execute_job.assert_called_once_with(
        title=fake_summary.title,
        details=fake_summary.service,
        parameters=fake_summary.parameters
    )
    assert result is fake_result
    
    
@patch("app.services.processing.get_processing_platform")
def test_create_processing_job_platform_raises(mock_get_platform):
    # Arrange
    fake_summary = make_job_request()
    mock_get_platform.side_effect = ValueError("Unsupported platform")

    # Act & Assert
    with pytest.raises(ValueError, match="Unsupported platform"):
        create_processing_job(fake_summary)
