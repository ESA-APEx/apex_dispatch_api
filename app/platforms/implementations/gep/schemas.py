"""Payload models accepted by the GEP callback integration."""

from stage_events_client.models import (
    CompletedCloudEvent, DismissedCloudEvent, FailedCloudEvent,
    PipedCloudEvent, PreparedCloudEvent, StagedCloudEvent, SubmittedCloudEvent,
)

ProgressEvent = (
    SubmittedCloudEvent | DismissedCloudEvent | PreparedCloudEvent | StagedCloudEvent
)
SuccessEvent = PipedCloudEvent | CompletedCloudEvent
FailureEvent = FailedCloudEvent
