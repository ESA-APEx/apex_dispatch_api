from datetime import datetime
from unittest.mock import MagicMock

from fastapi import Response
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from stac_pydantic import Collection
from stac_pydantic.collection import Extent, SpatialExtent, TimeInterval

from app.auth import get_current_user_id, oauth2_scheme
from app.database.models.processing_job import ProcessingJobRecord
from app.database.models.upscaling_task import UpscalingTaskRecord
from app.main import app
from app.schemas.enum import OutputFormatEnum, ProcessingStatusEnum, ProcessTypeEnum
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


def fake_get_current_user_id():
    return "foobar"


def fake_user_token():
    return "foobar_token"


@pytest.fixture
def client():
    app.dependency_overrides[oauth2_scheme] = fake_user_token
    app.dependency_overrides[get_current_user_id] = fake_get_current_user_id
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user_id, None)


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
        format=OutputFormatEnum.GEOTIFF,
        parameters={},
    )


@pytest.fixture
def fake_processing_job_summary():
    return ProcessingJobSummary(
        id=1,
        title="Test Job",
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.CREATED,
        parameters={"param1": "value1", "param2": "value2"},
        service=ServiceDetails(endpoint="foo", application="bar"),
    )


@pytest.fixture
def fake_processing_job(fake_processing_job_summary, fake_processing_job_request):
    return ProcessingJob(
        **(fake_processing_job_summary.model_dump()),
        created=datetime.now(),
        updated=datetime.now()
    )


@pytest.fixture
def fake_processing_job_record(
    fake_processing_job_summary, fake_processing_job_request
):
    record = ProcessingJobRecord(
        id=fake_processing_job_summary.id,
        title=fake_processing_job_summary.title,
        label=fake_processing_job_summary.label,
        status=fake_processing_job_summary.status,
        platform_job_id="platform-job-1",
        service='{"endpoint":"foo","application":"bar"}',
        parameters="{}",
        created=datetime.now(),
        updated=datetime.now(),
    )
    record.status = ProcessingStatusEnum.CREATED
    return record


@pytest.fixture
def fake_upscaling_task_request():
    return UpscalingTaskRequest(
        title="Test Job",
        label=ProcessTypeEnum.OPENEO,
        service=ServiceDetails(endpoint="foo", application="bar"),
        format=OutputFormatEnum.GEOTIFF,
        parameters={"temporal_extent": "2025-01-01"},
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


@pytest.fixture
def fake_upscaling_task_record(fake_upscaling_task_summary):
    return UpscalingTaskRecord(
        **(fake_upscaling_task_summary.model_dump()),
        service='{"endpoint":"foo","application":"bar"}',
        created=datetime.now(),
        updated=datetime.now()
    )


@pytest.fixture
def fake_result():
    return Collection(
        id="fake-result",
        title="fake-title",
        description="This is a fake result",
        links=[],
        type="Collection",
        license="free",
        extent=Extent(
            spatial=SpatialExtent(bbox=[]),
            temporal=TimeInterval(
                interval=[["2025-01-01T00:00:00Z", "2025-12-31T23:59:59Z"]]
            ),
        ),
    )


@pytest.fixture
def fake_sync_response():
    return Response(
        content='{"status":"success","data":{"message":"Synchronous job completed successfully."}}',
        media_type="application/json",
        status_code=200,
    )
