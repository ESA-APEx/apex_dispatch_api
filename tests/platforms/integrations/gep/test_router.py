from unittest.mock import ANY, MagicMock, patch
import pytest
from fastapi import status

from app.main import app
from app.platforms.implementations.gep.auth import verify_callback_token
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

@pytest.fixture
def callback_dependencies(fake_processing_job_record):
    fake_processing_job_record.platform_job_id = "default:job-123"
    # Ensure authorized caller matches the endpoint in fake_processing_job_record.service ("foo")
    app.dependency_overrides[verify_callback_token] = lambda: {"foo"}
    with (
        patch(
            "app.platforms.implementations.gep.router.get_gep_job",
            return_value=fake_processing_job_record,
        ) as lookup,
        patch(
            "app.services.job_status.ProcessingStateMachine.can_transition",
            return_value=True,
        ) as can_transition,
        patch("app.services.job_status.update_job_status_by_id") as update,
    ):
        yield lookup, can_transition, update
    app.dependency_overrides.pop(verify_callback_token, None)


CALLBACK_CASES = [
    pytest.param("success", PIPED_PAYLOAD, ProcessingStatusEnum.FINISHED, id="piped"),
    pytest.param("success", COMPLETED_PAYLOAD, ProcessingStatusEnum.FINISHED, id="completed"),
    pytest.param("inProgress", STAGED_PAYLOAD, ProcessingStatusEnum.RUNNING, id="staged"),
    pytest.param("inProgress", PREPARED_PAYLOAD, ProcessingStatusEnum.RUNNING, id="prepared"),
    pytest.param("inProgress", SUBMITTED_PAYLOAD, ProcessingStatusEnum.QUEUED, id="submitted"),
    pytest.param("inProgress", DISMISSED_PAYLOAD, ProcessingStatusEnum.CANCELED, id="dismissed"),
    pytest.param("failed", FAILED_PAYLOAD, ProcessingStatusEnum.FAILED, id="failed"),
]


@pytest.mark.parametrize("endpoint,payload,target_status", CALLBACK_CASES)
def test_callback_updates_job_status(
    client, callback_dependencies, fake_processing_job_record,
    endpoint, payload, target_status,
):
    lookup, can_transition, update = callback_dependencies
    initial_status = fake_processing_job_record.status

    response = client.post(
        f"/integrations/ogc-api-processes/gep/callbacks/{endpoint}",
        json=payload,
        headers={"Content-Type": "application/cloudevents+json"},
    )

    assert response.status_code == status.HTTP_200_OK
    lookup.assert_called_once_with(ANY, "default:job-123")
    can_transition.assert_called_once_with(initial_status, target_status)
    update.assert_called_once_with(
        lookup.call_args.args[0], fake_processing_job_record.id, target_status
    )
    assert fake_processing_job_record.status == target_status


@pytest.mark.parametrize("endpoint,payload,target_status", CALLBACK_CASES)
def test_callback_rejects_invalid_transition(
    client, callback_dependencies, fake_processing_job_record,
    endpoint, payload, target_status,
):
    lookup, can_transition, update = callback_dependencies
    fake_processing_job_record.status = ProcessingStatusEnum.DELETED
    can_transition.return_value = False

    response = client.post(
        f"/integrations/ogc-api-processes/gep/callbacks/{endpoint}",
        json=payload,
        headers={"Content-Type": "application/cloudevents+json"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.headers["content-type"] == "application/problem+json"
    data = response.json()
    assert data["status"] == 422
    assert data["instance"].endswith(f"/integrations/ogc-api-processes/gep/callbacks/{endpoint}")
    assert len(data["errors"]) == 1
    assert data["errors"][0]["pointer"] == "subject"
    assert "default:job-123" in data["errors"][0]["detail"]
    lookup.assert_called_once_with(ANY, "default:job-123")
    can_transition.assert_called_once_with(ProcessingStatusEnum.DELETED, target_status)
    update.assert_not_called()
    assert fake_processing_job_record.status == ProcessingStatusEnum.DELETED


@pytest.mark.parametrize("endpoint,payload", [
    ("success", PIPED_PAYLOAD),
    ("failed", FAILED_PAYLOAD),
])
def test_callback_missing_job_404_problem_details(
    client, callback_dependencies, endpoint, payload,
):
    lookup, can_transition, update = callback_dependencies
    lookup.return_value = None

    response = client.post(
        f"/integrations/ogc-api-processes/gep/callbacks/{endpoint}",
        json={**payload, "subject": "default:test-uid:nonexistent"},
        headers={"Content-Type": "application/cloudevents+json"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"
    data = response.json()
    assert data["status"] == 404
    assert data["title"] == "Not Found"
    assert data["instance"].endswith(f"/integrations/ogc-api-processes/gep/callbacks/{endpoint}")
    assert data["errors"] == [
        {
            "detail": "Job default:nonexistent does not exist in the Job registry",
            "pointer": "subject",
        }
    ]
    lookup.assert_called_once_with(ANY, "default:nonexistent")
    can_transition.assert_not_called()
    update.assert_not_called()


@pytest.mark.parametrize("payload", [
    SUBMITTED_PAYLOAD, PREPARED_PAYLOAD, STAGED_PAYLOAD, DISMISSED_PAYLOAD,
])
def test_callback_in_progress_uncommitted_job_acknowledges_cleanly(
    client, callback_dependencies, payload,
):
    lookup, can_transition, update = callback_dependencies
    lookup.return_value = None

    response = client.post(
        "/integrations/ogc-api-processes/gep/callbacks/inProgress",
        json=payload,
        headers={"Content-Type": "application/cloudevents+json"},
    )

    assert response.status_code == status.HTTP_200_OK
    lookup.assert_called_once_with(ANY, "default:job-123")
    can_transition.assert_not_called()
    update.assert_not_called()


@pytest.mark.parametrize("failure_point", ["lookup", "transition", "update"])
def test_callback_unexpected_error_returns_500(
    client, callback_dependencies, fake_processing_job_record, failure_point,
):
    lookup, can_transition, update = callback_dependencies
    initial_status = fake_processing_job_record.status
    dependencies = {"lookup": lookup, "transition": can_transition, "update": update}
    dependencies[failure_point].side_effect = RuntimeError("callback failure")

    response = client.post(
        "/integrations/ogc-api-processes/gep/callbacks/success",
        json=PIPED_PAYLOAD,
        headers={"Content-Type": "application/cloudevents+json"},
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.headers["content-type"] == "application/problem+json"
    data = response.json()
    assert data["status"] == 500
    assert data["instance"].endswith("/integrations/ogc-api-processes/gep/callbacks/success")
    assert data["errors"] == [{
        "parameter": "job_id",
        "detail": (
            "An error occurred when updating status of Job default:job-123: "
            "callback failure"
        ),
    }]
    assert fake_processing_job_record.status == initial_status
    if failure_point != "update":
        update.assert_not_called()
    if failure_point == "lookup":
        can_transition.assert_not_called()


def testextract_job_identifier():
    from app.platforms.implementations.gep.callbacks import extract_job_identifier

    # 3-part subject (<namespace>:<uid>:<workflow_name>)
    event = MagicMock(subject="myns:uid-1234:wf-5678")
    assert extract_job_identifier(event) == "myns:wf-5678"

    # 2-part subject
    event = MagicMock(subject="myns:wf-5678")
    assert extract_job_identifier(event) == "myns:wf-5678"

    # Single string
    event = MagicMock(subject="wf-5678")
    assert extract_job_identifier(event) == "wf-5678"

    # Missing / None subject
    event = MagicMock(subject=None)
    assert extract_job_identifier(event) is None


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
        assert subscriber["successUri"].endswith(
            "/integrations/ogc-api-processes/gep/callbacks/success"
        )
        assert subscriber["inProgressUri"].endswith(
            "/integrations/ogc-api-processes/gep/callbacks/inProgress"
        )
        assert subscriber["failedUri"].endswith(
            "/integrations/ogc-api-processes/gep/callbacks/failed"
        )
