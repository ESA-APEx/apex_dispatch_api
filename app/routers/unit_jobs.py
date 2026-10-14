from typing import Annotated
from fastapi import Body, APIRouter, Depends, Request, status
from loguru import logger
from sqlalchemy.orm import Session

from app.auth import oauth2_scheme
from app.database.db import get_db
from app.error import (
    DispatcherException,
    ErrorResponse,
    InternalException,
    JobNotFoundException,
)
from app.middleware.error_handling import get_dispatcher_error_response
from eoap_problems_registry import ErrorDetail, NotFound, ServerError
from eoap_problems_registry.fastapi import ProblemRegistryException
from stage_events_client.models import (
    BaseCloudEvent,
    CompletedCloudEvent,
    DismissedCloudEvent,
    FailedCloudEvent,
    PipedCloudEvent,
    PreparedCloudEvent,
    StagedCloudEvent,
    SubmittedCloudEvent,
)
from app.schemas.callbacks import (
    STAGE_TO_APEX_STATUS,
    UnitJobsJobIdFailedPostResponse,
    UnitJobsJobIdInProgressPostResponse,
    UnitJobsJobIdSuccessPostResponse,
)
from app.schemas.enum import OutputFormatEnum, ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.unit_job import (
    BaseJobRequest,
    ProcessingJob,
    ProcessingJobSummary,
    ServiceDetails,
)
from app.services.processing import (
    create_processing_job,
    delete_processing_job,
    get_processing_job_by_user_id,
    get_processing_job_results,
    update_job_status_from_callback,
)

from stac_pydantic import Collection

# from app.auth import get_current_user

router = APIRouter()


@router.post(
    "/unit_jobs",
    status_code=status.HTTP_201_CREATED,
    tags=["Unit Jobs"],
    summary="Create a new processing job",
    responses={
        InternalException.http_status: {
            "description": "Internal server error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        InternalException(), "request-id"
                    )
                }
            },
        },
    },
)
async def create_unit_job(
    payload: Annotated[
        BaseJobRequest,
        Body(
            openapi_examples={
                "openEO Example": {
                    "summary": "Valid openEO job request",
                    "description": "The following example demonstrates how to create a processing "
                    "job using an openEO-based service. This example triggers the "
                    "[`variability map`](https://github.com/ESA-APEx/apex_algorithms/blob/main/algo"
                    "rithm_catalog/vito/variabilitymap/records/variabilitymap.json) "
                    "process using the CDSE openEO Federation. In this case the `endpoint`"
                    "represents the URL of the openEO backend and the `application` refers to the "
                    "User Defined Process (UDP) that is being executed on the backend.",
                    "value": BaseJobRequest(
                        label=ProcessTypeEnum.OPENEO,
                        title="Example openEO Job",
                        service=ServiceDetails(
                            endpoint="https://openeofed.dataspace.copernicus.eu",
                            application="https://raw.githubusercontent.com/ESA-APEx/apex_algorithms"
                            "/32ea3c9a6fa24fe063cb59164cd318cceb7209b0/openeo_udp/variabilitymap/"
                            "variabilitymap.json",
                        ),
                        format=OutputFormatEnum.GEOTIFF,
                        parameters={
                            "spatial_extent": {
                                "type": "FeatureCollection",
                                "features": [
                                    {
                                        "type": "Feature",
                                        "properties": {},
                                        "geometry": {
                                            "coordinates": [
                                                [
                                                    [
                                                        5.170043941798298,
                                                        51.25050990858725,
                                                    ],
                                                    [
                                                        5.171035037521989,
                                                        51.24865722468999,
                                                    ],
                                                    [
                                                        5.178521828188366,
                                                        51.24674578027137,
                                                    ],
                                                    [
                                                        5.179084341977159,
                                                        51.24984764553983,
                                                    ],
                                                    [
                                                        5.170043941798298,
                                                        51.25050990858725,
                                                    ],
                                                ]
                                            ],
                                            "type": "Polygon",
                                        },
                                    }
                                ],
                            },
                            "temporal_extent": ["2025-05-01", "2025-05-01"],
                        },
                    ).model_dump(),
                }
            },
        ),
    ],
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> ProcessingJobSummary:
    """Create a new processing job with the provided data."""
    try:
        return await create_processing_job(token, db, payload)
    except DispatcherException as de:
        raise de
    except Exception as e:
        logger.error(f"Error creating processing job: {e}")
        raise InternalException(
            message="An error occurred while creating processing job.",
            details={"error": str(e)}
        )


@router.get(
    "/unit_jobs/{job_id}",
    tags=["Unit Jobs"],
    responses={
        JobNotFoundException.http_status: {
            "description": "Job not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        JobNotFoundException(), "request-id"
                    )
                }
            },
        },
        InternalException.http_status: {
            "description": "Internal server error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        InternalException(), "request-id"
                    )
                }
            },
        },
    },
)
async def get_job(
    job_id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> ProcessingJob:
    try:
        job = await get_processing_job_by_user_id(token, db, job_id)
        if not job:
            raise JobNotFoundException()
        return job
    except DispatcherException as de:
        raise de
    except Exception as e:
        logger.error(f"Error retrieving processing job {job_id}: {e}")
        raise InternalException(
            message="An error occurred while retrieving the processing job.",
            details={"error": str(e)}
        )


@router.get(
    "/unit_jobs/{job_id}/results",
    tags=["Unit Jobs"],
    responses={
        JobNotFoundException.http_status: {
            "description": "Job not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        JobNotFoundException(), "request-id"
                    )
                }
            },
        },
        InternalException.http_status: {
            "description": "Internal server error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        InternalException(), "request-id"
                    )
                }
            },
        },
    },
)
async def get_job_results(
    job_id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> Collection | None:
    try:
        result = await get_processing_job_results(token, db, job_id)
        if not result:
            raise JobNotFoundException()
        return result
    except DispatcherException as de:
        raise de
    except Exception as e:
        logger.error(f"Error getting results for processing job {job_id}: {e}")
        raise InternalException(
            message="An error occurred while retrieving processing job results.",
            details={"error": str(e)},
        )


@router.delete(
    "/unit_jobs/{job_id}",
    tags=["Unit Jobs"],
    responses={
        JobNotFoundException.http_status: {
            "description": "Job not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        JobNotFoundException(), "request-id"
                    )
                }
            },
        },
        InternalException.http_status: {
            "description": "Internal server error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        InternalException(), "request-id"
                    )
                }
            },
        },
    },
)
async def delete_job(
    job_id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> None:
    try:
        job = await get_processing_job_by_user_id(token, db, job_id)
        if not job:
            raise JobNotFoundException()
        await delete_processing_job(token, db, job_id)
    except DispatcherException as de:
        raise de
    except Exception as e:
        logger.error(f"Error deleting processing job {job_id}: {e}")
        raise InternalException(
            message="An error occurred while deleting the processing job.",
            details={"error": str(e)}
        )


def _extract_job_identifier_from_cloudevent(cloud_event: BaseCloudEvent) -> str | None:
    """Extract job_identifier strictly from CloudEvent subject metadata."""
    # CloudEvent subject pattern: "<namespace>:<workflow_uid>:<workflow_name>"
    subject = getattr(cloud_event, "subject", None)
    if not subject:
        return None

    parts = subject.split(":")
    if len(parts) == 3:
        return f"{parts[0]}:{parts[2]}"
    return subject


def _handle_callback_status_update(
    db: Session,
    cloud_event: BaseCloudEvent,
    target_status: ProcessingStatusEnum,
    request: Request,
) -> None:
    """Internal helper to update job status from callback CloudEvents."""
    job_identifier = _extract_job_identifier_from_cloudevent(cloud_event) or ""
    instance_uri = request.url.path
    endpoint_name = instance_uri.split("/")[-1]

    logger.info(f"Callback '{endpoint_name}' received for job '{job_identifier}'")

    try:
        job = update_job_status_from_callback(db, job_identifier, target_status)
        if not job:
            if endpoint_name == "inProgress":
                # An early inProgress callback may arrive before initial job commit finishes; acknowledge gracefully without returning 404.
                logger.debug(f"Job '{job_identifier}' is not registered in database yet; acknowledging in progress")
                return

            raise ProblemRegistryException(
                problem=NotFound(
                    instance=instance_uri,
                    errors=[
                        ErrorDetail(
                            parameter="job_id",
                            detail=f"Job {job_identifier} does not exist in the Job registry",
                        )
                    ],
                )
            )
    except ProblemRegistryException:
        raise
    except Exception as e:
        logger.error(f"Error handling {endpoint_name} callback for job {job_identifier}: {e}")
        raise ProblemRegistryException(
            problem=ServerError(
                instance=instance_uri,
                errors=[
                    ErrorDetail(
                        parameter="job_id",
                        detail=f"An error occurred when updating status of Job {job_identifier}: {e}",
                    )
                ],
            )
        )


@router.post(
    "/unit_jobs/success",
    response_model=None,
    status_code=status.HTTP_200_OK,
    tags=["Unit Jobs"],
    summary="URIs for success callbacks for jobs.",
    description="The callback URL will be invoked after a job succeeded its execution.\n",
    operation_id="onSuccessJob",
    responses={
        status.HTTP_200_OK: {"description": "Job status updated successfully."},
        status.HTTP_400_BAD_REQUEST: {"model": UnitJobsJobIdSuccessPostResponse},
        status.HTTP_404_NOT_FOUND: {"model": NotFound},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ServerError},
    },
)
def on_success_job(
    request: Request,
    body: PipedCloudEvent | CompletedCloudEvent,
    db: Session = Depends(get_db),
) -> None:
    """URIs for success callbacks for jobs."""
    _handle_callback_status_update(
        db, body, ProcessingStatusEnum.FINISHED, request
    )


@router.post(
    "/unit_jobs/inProgress",
    response_model=None,
    status_code=status.HTTP_200_OK,
    tags=["Unit Jobs"],
    summary="URIs for progress callbacks for jobs.",
    description=(
        "The callback URL will be invoked while a job is changing "
        "its status during its execution.\n"
    ),
    operation_id="onProgressJob",
    responses={
        status.HTTP_200_OK: {"description": "Job status updated successfully."},
        status.HTTP_400_BAD_REQUEST: {"model": UnitJobsJobIdInProgressPostResponse},
        status.HTTP_404_NOT_FOUND: {"model": NotFound},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ServerError},
    },
)
def on_progress_job(
    request: Request,
    body: (
        SubmittedCloudEvent
        | DismissedCloudEvent
        | PreparedCloudEvent
        | StagedCloudEvent
    ),
    db: Session = Depends(get_db),
) -> None:
    """URIs for progress callbacks for jobs."""
    target_status = STAGE_TO_APEX_STATUS.get(
        body.type, ProcessingStatusEnum.RUNNING
    )
    _handle_callback_status_update(db, body, target_status, request)


@router.post(
    "/unit_jobs/failed",
    response_model=None,
    status_code=status.HTTP_200_OK,
    tags=["Unit Jobs"],
    summary="URIs for failed callbacks for jobs.",
    description="The callback URL will be invoked after a job failed its execution.\n",
    operation_id="onFailedJob",
    responses={
        status.HTTP_200_OK: {"description": "Job status updated successfully."},
        status.HTTP_400_BAD_REQUEST: {"model": UnitJobsJobIdFailedPostResponse},
        status.HTTP_404_NOT_FOUND: {"model": NotFound},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ServerError},
    },
)
def on_failed_job(
    request: Request,
    body: FailedCloudEvent,
    db: Session = Depends(get_db),
) -> None:
    """URIs for failed callbacks for jobs."""
    _handle_callback_status_update(
        db, body, ProcessingStatusEnum.FAILED, request
    )
