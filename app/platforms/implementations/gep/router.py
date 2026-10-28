"""Receive GEP stage CloudEvents, not arbitrary OGC callback payloads."""

from fastapi import APIRouter, Depends, Request, status
from loguru import logger
from sqlalchemy.orm import Session
from stage_events_client.models import BaseCloudEvent
from http_apis_problems_detail import ErrorDetail
from http_apis_problems_detail.fastapi import (
    PROBLEM_RESPONSES, BusinessRuleViolationException, ServerErrorException,
    NotFoundException, ProblemRegistryException,
)

from app.database.db import get_db
from app.schemas.enum import ProcessingStatusEnum
from app.services.job_status import apply_job_status, InvalidJobTransition
from app.platforms.implementations.gep.callbacks import (
    STAGE_TO_APEX_STATUS, extract_job_identifier, get_gep_job,
)
from app.platforms.implementations.gep.schemas import (
    ProgressEvent, SuccessEvent, FailureEvent,
)
from app.platforms.implementations.gep.subscriber import CALLBACK_PREFIX

router = APIRouter(prefix=CALLBACK_PREFIX, tags=["GEP callbacks"])


def _handle_callback_status_update(
    db: Session,
    cloud_event: BaseCloudEvent,
    target_status: ProcessingStatusEnum,
    request: Request,
) -> None:
    """Internal helper to update job status from callback CloudEvents."""
    job_identifier = extract_job_identifier(cloud_event) or ""
    endpoint_name = request.url.path.split("/")[-1]

    logger.info(f"Callback '{endpoint_name}' received for job '{job_identifier}'")

    try:
        job = get_gep_job(db, job_identifier)
        if not job:
            if endpoint_name == "inProgress":
                # An early inProgress callback may arrive before initial job commit finishes;
                # acknowledge gracefully without returning 404.
                logger.debug(
                    f"Job '{job_identifier}' is not registered in database yet; "
                    "acknowledging in progress"
                )
                return

            raise NotFoundException(
                request=request,
                errors=[
                    ErrorDetail(
                        pointer="subject",
                        detail=f"Job {job_identifier} does not exist in the Job registry",
                    )
                ]
            )

        try:
            apply_job_status(db, job, target_status)
        except InvalidJobTransition as exc:
            raise BusinessRuleViolationException(
                request=request,
                errors=[ErrorDetail(pointer="subject", detail=str(exc))],
            ) from exc
        logger.info(
            f"Successfully updated status of job '{job_identifier}' (id={job.id}) "
            f"to {target_status}"
        )
    except ProblemRegistryException:
        raise
    except Exception as e:
        logger.error(f"Error handling {endpoint_name} callback for job {job_identifier}: {e}")
        raise ServerErrorException(
            request=request,
            errors=[
                ErrorDetail(
                    parameter="job_id",
                    detail=(
                        f"An error occurred when updating status of Job {job_identifier}: {e}"
                    ),
                )
            ]
        )


@router.post(
    "/success",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="URIs for success callbacks for jobs.",
    description=(
        "Accepts GEP stage CloudEvents. The callback URL will be invoked "
        "after a job succeeded its execution.\n"
    ),
    operation_id="onGepJobSuccess",
    responses={
        status.HTTP_200_OK: {"description": "Job status updated successfully."},
        status.HTTP_400_BAD_REQUEST: PROBLEM_RESPONSES[status.HTTP_400_BAD_REQUEST],
        status.HTTP_404_NOT_FOUND: PROBLEM_RESPONSES[status.HTTP_404_NOT_FOUND],
        status.HTTP_422_UNPROCESSABLE_CONTENT: (
            PROBLEM_RESPONSES[status.HTTP_422_UNPROCESSABLE_CONTENT]
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR: (
            PROBLEM_RESPONSES[status.HTTP_500_INTERNAL_SERVER_ERROR]
        ),
    },
)
def on_gep_job_success(
    request: Request,
    body: SuccessEvent,
    db: Session = Depends(get_db),
) -> None:
    """URIs for success callbacks for jobs."""
    _handle_callback_status_update(
        db, body, ProcessingStatusEnum.FINISHED, request
    )


@router.post(
    "/inProgress",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="URIs for progress callbacks for jobs.",
    description=(
        "Accepts GEP stage CloudEvents. The callback URL will be invoked while a job is changing "
        "its status during its execution.\n"
    ),
    operation_id="onGepJobProgress",
    responses={
        status.HTTP_200_OK: {"description": "Job status updated successfully."},
        status.HTTP_400_BAD_REQUEST: PROBLEM_RESPONSES[status.HTTP_400_BAD_REQUEST],
        status.HTTP_404_NOT_FOUND: PROBLEM_RESPONSES[status.HTTP_404_NOT_FOUND],
        status.HTTP_422_UNPROCESSABLE_CONTENT: (
            PROBLEM_RESPONSES[status.HTTP_422_UNPROCESSABLE_CONTENT]
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR: (
            PROBLEM_RESPONSES[status.HTTP_500_INTERNAL_SERVER_ERROR]
        ),
    },
)
def on_gep_job_progress(
    request: Request,
    body: ProgressEvent,
    db: Session = Depends(get_db),
) -> None:
    """URIs for progress callbacks for jobs."""
    target_status = STAGE_TO_APEX_STATUS[body.type]
    _handle_callback_status_update(db, body, target_status, request)


@router.post(
    "/failed",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="URIs for failed callbacks for jobs.",
    description=(
        "Accepts GEP stage CloudEvents. The callback URL will be invoked "
        "after a job failed its execution.\n"
    ),
    operation_id="onGepJobFailed",
    responses={
        status.HTTP_200_OK: {"description": "Job status updated successfully."},
        status.HTTP_400_BAD_REQUEST: PROBLEM_RESPONSES[status.HTTP_400_BAD_REQUEST],
        status.HTTP_404_NOT_FOUND: PROBLEM_RESPONSES[status.HTTP_404_NOT_FOUND],
        status.HTTP_422_UNPROCESSABLE_CONTENT: (
            PROBLEM_RESPONSES[status.HTTP_422_UNPROCESSABLE_CONTENT]
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR: (
            PROBLEM_RESPONSES[status.HTTP_500_INTERNAL_SERVER_ERROR]
        ),
    },
)
def on_gep_job_failed(
    request: Request,
    body: FailureEvent,
    db: Session = Depends(get_db),
) -> None:
    """URIs for failed callbacks for jobs."""
    _handle_callback_status_update(
        db, body, ProcessingStatusEnum.FAILED, request
    )
