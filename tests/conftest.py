from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.processing_job import ProcessingJobRecord
from app.main import app
from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.unit_job import (
    BaseJobRequest,
    ProcessingJob,
    ProcessingJobSummary,
    ServiceDetails,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_db_session():
    # A simple mock DB session object
    return MagicMock(spec=Session)


@pytest.fixture
def fake_processing_job_request():
    return BaseJobRequest(
        title="Test Job",
        label=ProcessTypeEnum.OPENEO,
        service=ServiceDetails(service="foo", application="bar"),
        parameters={},
    )


@pytest.fixture
def fake_processing_job_summary():
    return ProcessingJobSummary(
        id=1,
        title="Test Job",
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
    )


@pytest.fixture
def fake_processing_job(fake_processing_job_summary, fake_processing_job_request):
    return ProcessingJob(
        **(fake_processing_job_summary.model_dump()),
        service=fake_processing_job_request.service,
        parameters=fake_processing_job_request.parameters,
        result_link="https://foo.bar",
        created=datetime.now(),
        updated=datetime.now()
    )


@pytest.fixture
def fake_processing_job_record(
    fake_processing_job_summary, fake_processing_job_request
):
    record = ProcessingJobRecord(
        **(fake_processing_job_summary.model_dump()),
        platform_job_id="platform-job-1",
        service_record='{"service":"foo","application":"bar"}',
        parameters="{}",
        result_link="https://foo.bar",
        created=datetime.now(),
        updated=datetime.now()
    )
    record.status = ProcessingStatusEnum.CREATED
    return record


# @pytest.fixture(autouse=True)
# def disable_auth(monkeypatch):
#     # Replace auth.get_current_user dependency with a stub for tests
#     from app import auth

#     monkeypatch.setattr(auth, "get_current_user", lambda: {"sub": "test-user"})
