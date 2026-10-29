"""Payload models accepted by the GEP callback integration."""

from pydantic import Field

from app.config.schemas import BackendAuthConfig

from stage_events_client.models import (
    CompletedCloudEvent, DismissedCloudEvent, FailedCloudEvent,
    PipedCloudEvent, PreparedCloudEvent, StagedCloudEvent, SubmittedCloudEvent,
)

ProgressEvent = (
    SubmittedCloudEvent | DismissedCloudEvent | PreparedCloudEvent | StagedCloudEvent
)
SuccessEvent = PipedCloudEvent | CompletedCloudEvent
FailureEvent = FailedCloudEvent


class CallbackBackendAuthConfig(BackendAuthConfig):
    """Backend authentication extended locally for inbound GEP callbacks."""

    callback_issuer: str | None = None
    callback_audience: str | None = None
    callback_clients: list[str] = Field(default_factory=list)
