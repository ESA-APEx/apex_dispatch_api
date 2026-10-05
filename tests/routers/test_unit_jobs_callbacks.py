from unittest.mock import MagicMock, patch
import pytest
from fastapi import status

from app.schemas.enum import OutputFormatEnum, ProcessingStatusEnum
from app.schemas.unit_job import ServiceDetails
from app.platforms.implementations.ogc_api_process import OGCAPIProcessPlatform


# --- Test Payloads ---
PIPED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "job:step:1",
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
    "subject": "job:step:1",
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
    "subject": "job:step:1",
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
    "subject": "job:step:1",
    "partitionkey": "part-1",
    "type": "submitted",
    "data": {
        "namespace": "default",
        "process_id": "test-proc",
    },
}

DISMISSED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "job:step:1",
    "partitionkey": "part-1",
    "type": "dismissed",
    "data": {
        "namespace": "default",
        "status": "Pending",
    },
}

FAILED_PAYLOAD = {
    "source": "terradue:apex:test",
    "subject": "job:step:1",
    "partitionkey": "part-1",
    "type": "failed",
    "data": {
        "namespace": "default",
        "process_id": "test-proc",
        "job_id": "job-123",
        "usage": {},
    },
}


# --- Inbound Callback Tests ---

@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_success_200(mock_update, client):
    r = client.post(
        "/unit_jobs/job-123/success",
        json=PIPED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    mock_update.assert_called_once()
    args, _ = mock_update.call_args
    assert args[1] == "job-123"
    assert args[2] == ProcessingStatusEnum.FINISHED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_success_404_problem_details(mock_update, client):
    mock_update.return_value = None
    r = client.post(
        "/unit_jobs/nonexistent/success",
        json=PIPED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.headers.get("content-type") == "application/problem+json"
    data = r.json()
    assert data["status"] == 404
    assert data["title"] == "Not Found"
    assert data["instance"] == "/unit_jobs/nonexistent/success"
    assert data["errors"] == [
        {"detail": "Job nonexistent does not exist in the Job registry", "parameter": "job_id"}
    ]


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_in_progress_staged_200(mock_update, client):
    r = client.post(
        "/unit_jobs/job-123/inProgress",
        json=STAGED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "job-123"
    assert args[2] == ProcessingStatusEnum.RUNNING


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_in_progress_prepared_200(mock_update, client):
    r = client.post(
        "/unit_jobs/job-123/inProgress",
        json=PREPARED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "job-123"
    assert args[2] == ProcessingStatusEnum.QUEUED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_in_progress_submitted_200(mock_update, client):
    r = client.post(
        "/unit_jobs/job-123/inProgress",
        json=SUBMITTED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "job-123"
    assert args[2] == ProcessingStatusEnum.CREATED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_in_progress_dismissed_200(mock_update, client):
    r = client.post(
        "/unit_jobs/job-123/inProgress",
        json=DISMISSED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "job-123"
    assert args[2] == ProcessingStatusEnum.CANCELED


@patch("app.routers.unit_jobs.update_job_status_from_callback")
def test_callback_failed_200(mock_update, client):
    r = client.post(
        "/unit_jobs/job-123/failed",
        json=FAILED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )
    assert r.status_code == status.HTTP_200_OK
    args, _ = mock_update.call_args
    assert args[1] == "job-123"
    assert args[2] == ProcessingStatusEnum.FAILED


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
        assert subscriber["successUri"].endswith("/unit_jobs/{job_id}/success")
        assert subscriber["inProgressUri"].endswith("/unit_jobs/{job_id}/inProgress")
        assert subscriber["failedUri"].endswith("/unit_jobs/{job_id}/failed")
