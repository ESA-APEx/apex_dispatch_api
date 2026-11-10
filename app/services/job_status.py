"""Platform-independent status updates for already-resolved jobs."""

from sqlalchemy.orm import Session

from app.database.models.processing_job import (
    ProcessingJobRecord, update_job_status_by_id,
)
from app.schemas.enum import ProcessingStatusEnum
from app.services.processing_state_machine import ProcessingStateMachine


class InvalidJobTransition(ValueError):
    """The requested status would violate the job lifecycle."""


def apply_job_status(
    database: Session,
    job: ProcessingJobRecord,
    target_status: ProcessingStatusEnum,
) -> None:
    if not ProcessingStateMachine.can_transition(job.status, target_status):
        raise InvalidJobTransition(
            f"Job {job.platform_job_id} can not transition from status "
            f"{job.status} to {target_status}"
        )
    if job.status != target_status:
        update_job_status_by_id(database, job.id, target_status)
        job.status = target_status
