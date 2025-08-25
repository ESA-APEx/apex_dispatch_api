import json
from typing import List, Optional

from loguru import logger
from app.database.models.processing_job import (
    ProcessingJobRecord,
    get_job_by_user_id,
    get_jobs_by_user_id,
    save_job_to_db,
    update_job_status_by_id,
)
from app.platforms.dispatcher import get_processing_platform
from sqlalchemy.orm import Session

from app.schemas.enum import ProcessingStatusEnum
from app.schemas.unit_job import (
    BaseJobRequest,
    ProcessingJob,
    ProcessingJobSummary,
    ServiceDetails,
)

from stac_pydantic import Collection

INACTIVE_JOB_STATUSES = {
    ProcessingStatusEnum.CANCELED,
    ProcessingStatusEnum.FAILED,
    ProcessingStatusEnum.FINISHED,
}


def create_processing_job(
    database: Session,
    user: str,
    request: BaseJobRequest,
    upscaling_task_id: int | None = None,
) -> ProcessingJobSummary:
    logger.info(f"Creating processing job for {user} with summary: {request}")

    platform = get_processing_platform(request.label)

    job_id = platform.execute_job(
        title=request.title, details=request.service, parameters=request.parameters
    )

    record = ProcessingJobRecord(
        title=request.title,
        label=request.label,
        status=ProcessingStatusEnum.CREATED,
        user_id=user,
        platform_job_id=job_id,
        parameters=json.dumps(request.parameters),
        service=request.service.model_dump_json(),
        upscaling_task_id=upscaling_task_id,
    )
    record = save_job_to_db(database, record)
    return ProcessingJobSummary(
        id=record.id,
        title=record.title,
        label=request.label,
        status=record.status,
        parameters=request.parameters,
    )


def get_job_status(job: ProcessingJobRecord) -> ProcessingStatusEnum:
    logger.info(
        f"Retrieving job status for job: {job.platform_job_id} (current: {job.status})"
    )
    platform = get_processing_platform(job.label)
    details = ServiceDetails.model_validate_json(job.service)
    return platform.get_job_status(job.platform_job_id, details)


def get_processing_job_results(
    database: Session, job_id: int, user_id: str
) -> Collection | None:
    record = get_job_by_user_id(database, job_id, user_id)
    if not record:
        return None

    logger.info(f"Retrieving job result for job: {record.platform_job_id}")
    platform = get_processing_platform(record.label)
    details = ServiceDetails.model_validate_json(record.service)
    return platform.get_job_results(record.platform_job_id, details)


def _refresh_job_status(
    database: Session,
    record: ProcessingJobRecord,
) -> ProcessingJobRecord:
    new_status = get_job_status(record)
    if new_status != record.status:
        update_job_status_by_id(database, record.id, new_status)
        record.status = new_status
    return record


def get_processing_jobs_by_user_id(
    database: Session, user_id: str, upscaling_task_id: int | None = None
) -> List[ProcessingJobSummary]:
    logger.info(f"Retrieving processing jobs for user {user_id}")

    jobs: List[ProcessingJobSummary] = []
    records = get_jobs_by_user_id(database, user_id, upscaling_task_id)

    for record in records:
        # Only check status for active jobs
        if record.status not in INACTIVE_JOB_STATUSES:
            record = _refresh_job_status(database, record)

        jobs.append(
            ProcessingJobSummary(
                id=record.id,
                title=record.title,
                label=record.label,
                status=record.status,
                parameters=json.loads(record.parameters),
            )
        )
    return jobs


def get_processing_job_by_user_id(
    database: Session, job_id: int, user_id: str
) -> Optional[ProcessingJob]:
    logger.info(f"Retrieving processing job with ID {job_id} for user {user_id}")
    record = get_job_by_user_id(database, job_id, user_id)
    if not record:
        return None

    if record.status not in INACTIVE_JOB_STATUSES:
        record = _refresh_job_status(database, record)

    return ProcessingJob(
        id=record.id,
        title=record.title,
        label=record.label,
        status=record.status,
        service=ServiceDetails.model_validate_json(record.service or "{}"),
        parameters=json.loads(record.parameters or "{}"),
        created=record.created,
        updated=record.updated,
    )
