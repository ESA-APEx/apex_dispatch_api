from datetime import datetime
from unittest.mock import MagicMock

from geojson_pydantic import GeometryCollection
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
from app.schemas.upscale_task import (
    ParameterDimension,
    UpscalingTask,
    UpscalingTaskRequest,
    UpscalingTaskSummary,
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
        service=ServiceDetails(endpoint="foo", application="bar"),
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
        service='{"endpoint":"foo","application":"bar"}',
        parameters="{}",
        result_link="https://foo.bar",
        created=datetime.now(),
        updated=datetime.now()
    )
    record.status = ProcessingStatusEnum.CREATED
    return record


@pytest.fixture
def fake_upscaling_task_request():
    return UpscalingTaskRequest(
        title="Test Job",
        label=ProcessTypeEnum.OPENEO,
        service=ServiceDetails(endpoint="foo", application="bar"),
        parameters={},
        dimension=ParameterDimension(
            name="spatial_extent",
            values=[
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [4.813414938308839, 51.231275511382016],
                            [4.968699285344775, 51.231275511382016],
                            [4.968699285344775, 51.12105211672323],
                            [4.78903622852087, 51.123264199758346],
                            [4.813414938308839, 51.231275511382016],
                        ]
                    ],
                },
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [4.836037011633863, 51.331277680080774],
                            [4.968699285344775, 51.34099814769344],
                            [4.968699285344775, 51.231275511382016],
                            [4.813414938308839, 51.231275511382016],
                            [4.836037011633863, 51.331277680080774],
                        ]
                    ],
                },
            ],
        ),
    )


@pytest.fixture
def fake_upscaling_task_summary():
    return UpscalingTaskSummary(
        id=1,
        title="Test Job",
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
    )


@pytest.fixture
def fake_upscaling_task(fake_upscaling_task_summary, fake_upscaling_task_request):
    return UpscalingTask(
        **(fake_upscaling_task_summary.model_dump()),
        service=fake_upscaling_task_request.service,
        parameters=fake_upscaling_task_request.parameters,
        created=datetime.now(),
        updated=datetime.now(),
        jobs=[]
    )


# @pytest.fixture(autouse=True)
# def disable_auth(monkeypatch):
#     # Replace auth.get_current_user dependency with a stub for tests
#     from app import auth

#     monkeypatch.setattr(auth, "get_current_user", lambda: {"sub": "test-user"})
