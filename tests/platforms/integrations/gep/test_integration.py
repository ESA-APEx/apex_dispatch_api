"""GEP job correlation, subscriber URLs, and shared lifecycle regressions."""

import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database.models.processing_job import ProcessingJobRecord
from app.platforms.implementations.gep.callbacks import get_gep_job
from app.platforms.implementations.gep.subscriber import (
    CALLBACK_PREFIX, build_subscriber,
)
from app.schemas.enum import ProcessingStatusEnum as Status
from app.services.job_status import apply_job_status, InvalidJobTransition


def test_subscriber_uses_dispatcher_url():
    expected = {
        "successUri": "https://dispatch.example" + CALLBACK_PREFIX + "/success",
        "inProgressUri": "https://dispatch.example" + CALLBACK_PREFIX + "/inProgress",
        "failedUri": "https://dispatch.example" + CALLBACK_PREFIX + "/failed",
    }
    assert build_subscriber('https://dispatch.example/') == expected
    assert build_subscriber('https://dispatch.example') == expected


@pytest.fixture
def jobs_database():
    engine = create_engine('sqlite:///:memory:')
    # Portable fixture for the MySQL LONGTEXT-backed production ORM model.
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE processing_jobs (
            id INTEGER PRIMARY KEY, title TEXT, label TEXT, status TEXT,
            user_id TEXT, platform_job_id TEXT, parameters TEXT, service TEXT,
            created DATETIME, updated DATETIME, upscaling_task_id INTEGER
        )'''))
        rows = [
            (1, 'OPENEO', 'ns:job', 'https://gep.example'),
            (2, 'OGC_API_PROCESS', 'ns:other-job', 'https://other.example'),
            (3, 'OGC_API_PROCESS', 'other:job', 'https://gep.example'),
            (4, 'OGC_API_PROCESS', 'ns:job', 'https://gep.example'),
            (5, 'OGC_API_PROCESS', '123', 'https://gep.example'),
        ]
        for job_id, label, platform_id, endpoint in rows:
            conn.execute(text('''INSERT INTO processing_jobs
                (id, label, status, platform_job_id, service)
                VALUES (:id, :label, 'RUNNING', :platform_id, :service)'''),
                         dict(id=job_id, label=label, platform_id=platform_id,
                              service=json.dumps(dict(endpoint=endpoint, application='app'))))
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_lookup_is_exact_and_scoped_to_ogc(jobs_database):
    assert get_gep_job(jobs_database, 'ns:job').id == 4
    assert get_gep_job(jobs_database, 'ns:other-job').id == 2
    assert get_gep_job(jobs_database, 'job') is None
    assert get_gep_job(jobs_database, '4') is None
    assert get_gep_job(jobs_database, '123').id == 5


def test_lookup_rejects_ambiguity(jobs_database):
    jobs_database.execute(text('''INSERT INTO processing_jobs
        (id, label, status, platform_job_id, service)
        SELECT 6, label, status, platform_job_id, service
        FROM processing_jobs WHERE id = 4'''))
    with pytest.raises(ValueError, match='Ambiguous'):
        get_gep_job(jobs_database, 'ns:job')


@pytest.mark.parametrize('current', [Status.FINISHED, Status.FAILED, Status.CANCELED])
def test_terminal_state_cannot_regress(current):
    job = ProcessingJobRecord(id=1, status=current, platform_job_id='ns:job')
    with patch('app.services.job_status.update_job_status_by_id') as update:
        with pytest.raises(InvalidJobTransition):
            apply_job_status(None, job, Status.RUNNING)
        update.assert_not_called()
        assert job.status == current


def test_duplicate_status_is_noop():
    job = ProcessingJobRecord(id=1, status=Status.FINISHED)
    with patch('app.services.job_status.update_job_status_by_id') as update:
        apply_job_status(None, job, Status.FINISHED)
        update.assert_not_called()


def test_routes_and_openapi(client):
    paths = client.get('/openapi.json').json()['paths']
    for event in ('success', 'inProgress', 'failed'):
        assert CALLBACK_PREFIX + '/' + event in paths
        assert '/unit_jobs/' + event not in paths
        response = client.post('/unit_jobs/' + event, json={})
        assert response.status_code in (404, 405)
