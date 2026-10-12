from __future__ import annotations

from pydantic import RootModel
from eoap_problems_registry import (
    BadRequest,
    InvalidBodyPropertyFormat,
    InvalidBodyPropertyValue,
    InvalidParameters,
    InvalidRequestHeaderFormat,
    InvalidRequestParameterFormat,
    InvalidRequestParameterValue,
    MissingBodyProperty,
    MissingRequestHeader,
    MissingRequestParameter,
)
from stage_events_client.models import (
    SubmittedCloudEvent,
    DismissedCloudEvent,
    PreparedCloudEvent,
    CompletedCloudEvent,
    StagedCloudEvent,
    PipedCloudEvent,
)

from app.schemas.enum import ProcessingStatusEnum

STAGE_TO_APEX_STATUS: dict[str, ProcessingStatusEnum] = {
    "submitted": ProcessingStatusEnum.QUEUED,
    "prepared": ProcessingStatusEnum.RUNNING,
    "staged": ProcessingStatusEnum.RUNNING,
    "piped": ProcessingStatusEnum.FINISHED,
    "completed": ProcessingStatusEnum.FINISHED,
    "failed": ProcessingStatusEnum.FAILED,
    "dismissed": ProcessingStatusEnum.CANCELED,
}


class UnitJobsJobIdSuccessPostResponse(
    RootModel[
        BadRequest
        | InvalidBodyPropertyFormat
        | InvalidBodyPropertyValue
        | InvalidParameters
        | InvalidRequestHeaderFormat
        | InvalidRequestParameterFormat
        | InvalidRequestParameterValue
        | MissingBodyProperty
        | MissingRequestHeader
        | MissingRequestParameter
    ]
):
    root: (
        BadRequest
        | InvalidBodyPropertyFormat
        | InvalidBodyPropertyValue
        | InvalidParameters
        | InvalidRequestHeaderFormat
        | InvalidRequestParameterFormat
        | InvalidRequestParameterValue
        | MissingBodyProperty
        | MissingRequestHeader
        | MissingRequestParameter
    )


class UnitJobsJobIdInProgressPostRequest(
    RootModel[
        SubmittedCloudEvent
        | DismissedCloudEvent
        | PreparedCloudEvent
        | CompletedCloudEvent
        | StagedCloudEvent
    ]
):
    root: (
        SubmittedCloudEvent
        | DismissedCloudEvent
        | PreparedCloudEvent
        | CompletedCloudEvent
        | StagedCloudEvent
    )


class UnitJobsJobIdInProgressPostResponse(
    RootModel[
        BadRequest
        | InvalidBodyPropertyFormat
        | InvalidBodyPropertyValue
        | InvalidParameters
        | InvalidRequestHeaderFormat
        | InvalidRequestParameterFormat
        | InvalidRequestParameterValue
        | MissingBodyProperty
        | MissingRequestHeader
        | MissingRequestParameter
    ]
):
    root: (
        BadRequest
        | InvalidBodyPropertyFormat
        | InvalidBodyPropertyValue
        | InvalidParameters
        | InvalidRequestHeaderFormat
        | InvalidRequestParameterFormat
        | InvalidRequestParameterValue
        | MissingBodyProperty
        | MissingRequestHeader
        | MissingRequestParameter
    )


class UnitJobsJobIdFailedPostResponse(
    RootModel[
        BadRequest
        | InvalidBodyPropertyFormat
        | InvalidBodyPropertyValue
        | InvalidParameters
        | InvalidRequestHeaderFormat
        | InvalidRequestParameterFormat
        | InvalidRequestParameterValue
        | MissingBodyProperty
        | MissingRequestHeader
        | MissingRequestParameter
    ]
):
    root: (
        BadRequest
        | InvalidBodyPropertyFormat
        | InvalidBodyPropertyValue
        | InvalidParameters
        | InvalidRequestHeaderFormat
        | InvalidRequestParameterFormat
        | InvalidRequestParameterValue
        | MissingBodyProperty
        | MissingRequestHeader
        | MissingRequestParameter
    )
