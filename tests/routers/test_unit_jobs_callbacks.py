from unittest.mock import MagicMock, patch
import pytest
from fastapi import status

from app.schemas.enum import OutputFormatEnum, ProcessingStatusEnum
from app.schemas.unit_job import ServiceDetails
from app.platforms.implementations.ogc_api_process import OGCAPIProcessPlatform


# --- Test Payloads ---
PIPED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "default:test-uid:job-123",
    "partitionkey": "part-1",
    "type": "piped",
    "data": {
        "namespace": "default",
        "process_id": "test-proc",
        "job_id": "job-123",
        "entries": {},
    },
}

STAGED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "default:test-uid:job-123",
    "partitionkey": "part-1",
    "type": "staged",
    "data": {
        "namespace": "default",
        "process_id": "test-proc",
        "job_id": "job-123",
        "outputs": {},
    },
}

PREPARED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "default:test-uid:job-123",
    "partitionkey": "part-1",
    "type": "prepared",
    "data": {
        "namespace": "default",
        "process_id": "test-proc",
        "job_id": "job-123",
        "inputs": {},
    },
}

SUBMITTED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "default:test-uid:job-123",
    "partitionkey": "part-1",
    "type": "submitted",
    "data": {
        "namespace": "default",
        "process_id": "test-proc",
    },
}

DISMISSED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "default:test-uid:job-123",
    "partitionkey": "part-1",
    "type": "dismissed",
    "data": {
        "namespace": "default",
        "status": "Pending",
    },
}

FAILED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "default:test-uid:job-123",
    "partitionkey": "part-1",
    "type": "failed",
    "data": {
        "namespace": "default",
        "process_id": "test-proc",
        "job_id": "job-123",
        "usage": {},
    },
}

COMPLETED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "default:test-uid:job-123",
    "partitionkey": "part-1",
    "type": "completed",
    "data": {
        "namespace": "default",
        "process_id": "test-proc",
        "job_id": "job-123",
        "outputs": {},
        "usage": {},
    },
}


# --- Inbound Callback Tests ---

@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_success_piped_200(mock_update, client):
    r = client.post(
        "/unit_jobs/success",
        json=PIPED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    mock_update.assert_called_once()
    args, _ = mock_update.call_args
    assert args[1] == "default:job-123"
    assert args[2] == ProcessingStatusEnum.FINISHED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_success_completed_200(mock_update, client):
    r = client.post(
        "/unit_jobs/success",
        json=COMPLETED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    mock_update.assert_called_once()
    args, _ = mock_update.call_args
    assert args[1] == "default:job-123"
    assert args[2] == ProcessingStatusEnum.FINISHED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_success_404_problem_details(mock_update, client):
    mock_update.return_value = None
    r = client.post(
        "/unit_jobs/success",
        json={**PIPED_PAYLOAD, "subject": "default:test-uid:nonexistent"},
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.headers.get("content-type") == "application/problem+json"
    data = r.json()
    assert data["status"] == 404
    assert data["title"] == "Not Found"
    assert data["instance"].endswith("/unit_jobs/success")
    assert data["errors"] == [
        {
            "detail": "Job default:nonexistent does not exist in the Job registry",
            "parameter": "job_id",
        }
    ]


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_in_progress_staged_200(mock_update, client):
    r = client.post(
        "/unit_jobs/inProgress",
        json=STAGED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "default:job-123"
    assert args[2] == ProcessingStatusEnum.RUNNING


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_in_progress_prepared_200(mock_update, client):
    r = client.post(
        "/unit_jobs/inProgress",
        json=PREPARED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "default:job-123"
    assert args[2] == ProcessingStatusEnum.RUNNING


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_in_progress_submitted_200(mock_update, client):
    r = client.post(
        "/unit_jobs/inProgress",
        json=SUBMITTED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "default:job-123"
    assert args[2] == ProcessingStatusEnum.QUEUED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_in_progress_dismissed_200(mock_update, client):
    r = client.post(
        "/unit_jobs/inProgress",
        json=DISMISSED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "default:job-123"
    assert args[2] == ProcessingStatusEnum.CANCELED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_failed_200(mock_update, client):
    r = client.post(
        "/unit_jobs/failed",
        json=FAILED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "default:job-123"
    assert args[2] == ProcessingStatusEnum.FAILED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_resolves_3part_subject_from_cloudevent(mock_update, client):
    payload = {
        **PIPED_PAYLOAD,
        "source": "mmiraftab:opensartoolkit:stage-out",
        "subject": "mmiraftab:test-uid:opensartoolkit-v2-2-1-p6ms6",
    }
    r = client.post(
        "/unit_jobs/success",
        json=payload,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    mock_update.assert_called_once()
    args, _ = mock_update.call_args
    assert args[1] == "mmiraftab:opensartoolkit-v2-2-1-p6ms6"
    assert args[2] == ProcessingStatusEnum.FINISHED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_in_progress_uncommitted_job_acknowledges_cleanly(mock_update, client):
    mock_update.return_value = None  # simulate job not committed yet
    payload = {
        **SUBMITTED_PAYLOAD,
        "source": "mmiraftab:opensartoolkit:main",
        "subject": "mmiraftab:test-uid:opensartoolkit-v2-2-1-p6ms6",
    }
    r = client.post(
        "/unit_jobs/inProgress",
        json=payload,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK


def test_extract_job_identifier_from_cloudevent():
    from app.routers.unit_jobs import _extract_job_identifier_from_cloudevent

    # 3-part subject (<namespace>:<uid>:<workflow_name>)
    event = MagicMock(subject="myns:uid-1234:wf-5678")
    assert _extract_job_identifier_from_cloudevent(event) == "myns:wf-5678"

    # 2-part subject
    event = MagicMock(subject="myns:wf-5678")
    assert _extract_job_identifier_from_cloudevent(event) == "myns:wf-5678"

    # Single string
    event = MagicMock(subject="wf-5678")
    assert _extract_job_identifier_from_cloudevent(event) == "wf-5678"

    # Missing / None subject
    event = MagicMock(subject=None)
    assert _extract_job_identifier_from_cloudevent(event) is None


# --- Outbound Subscriber Payload Test ---

@pytest.mark.asyncio
@patch("app.platforms.implementations.ogc_api_process.exchange_token")
@patch("app.platforms.implementations.ogc_api_process.get_current_user_claims")
async def test_ogc_platform_execute_job_injects_subscriber(
    mock_claims, mock_exchange, monkeypatch
):
    mock_exchange.return_value = "fake_exchanged_token"
    mock_claims.return_value = {
        "sub": "user-sub",
        "preferred_username": "testuser",
        "email": "test@example.com",
    }

    platform = OGCAPIProcessPlatform()

    mock_client = MagicMock()
    mock_content = MagicMock()
    mock_content.job_id = "ogc-exec-999"
    mock_client.execute_simple.return_value = mock_content

    with patch.object(
        platform, "_create_api_client_instance", return_value=mock_client
    ), patch.object(
        platform, "_transform_parameters", return_value={"param1": "val1"}
    ):
        details = ServiceDetails(
            endpoint="https://ades.example.com",
            application="my-app",
            namespace="my-ns",
        )
        job_id = await platform.execute_job(
            user_token="user_token_123",
            title="My Execution",
            details=details,
            parameters={"param1": "val1"},
            format=OutputFormatEnum.JSON,
        )

        assert job_id == "my-ns:ogc-exec-999"

        # Verify execute_simple was called with the subscriber block
        mock_client.execute_simple.assert_called_once()
        _, kwargs = mock_client.execute_simple.call_args
        execute_data = kwargs["execute"]
        assert "subscriber" in execute_data
        subscriber = execute_data["subscriber"]
        assert subscriber["successUri"].endswith("/unit_jobs/success")
        assert subscriber["inProgressUri"].endswith("/unit_jobs/inProgress")
        assert subscriber["failedUri"].endswith("/unit_jobs/failed")
