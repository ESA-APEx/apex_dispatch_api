import json
from typing import List, Optional

from loguru import logger
from app.auth import get_current_user_id
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


async def create_processing_job(
    token: str,
    database: Session,
    request: BaseJobRequest,
    upscaling_task_id: int | None = None,
) -> ProcessingJobSummary:
    user = get_current_user_id(token)
    logger.info(f"Creating processing job for {user} with summary: {request}")

    try:
        platform = get_processing_platform(request.label)

        job_id = await platform.execute_job(
            user_token=token,
            title=request.title,
            details=request.service,
            parameters=request.parameters,
            format=request.format,
        )

        record = ProcessingJobRecord(
            title=request.title,
            label=request.label,
            status=(
                ProcessingStatusEnum.CREATED if job_id else ProcessingStatusEnum.FAILED
            ),
            user_id=user,
            platform_job_id=job_id,
            parameters=json.dumps(request.parameters),
            service=request.service.model_dump_json(),
            upscaling_task_id=upscaling_task_id,
        )

    except Exception as e:
        logger.error(f"Error creating processing job: {e}")

        if upscaling_task_id:
            # Do create the record in case of upscaling task to mark it as failed
            record = ProcessingJobRecord(
                title=request.title,
                label=request.label,
                status=ProcessingStatusEnum.FAILED,
                user_id=user,
                platform_job_id=None,
                parameters=json.dumps(request.parameters),
                service=request.service.model_dump_json(),
                upscaling_task_id=upscaling_task_id,
            )
        else:
            raise e

    record = save_job_to_db(database, record)
    return ProcessingJobSummary(
        id=record.id,
        title=record.title,
        label=request.label,
        status=record.status,
        parameters=request.parameters,
        service=request.service,
    )


async def get_job_status(token: str, job: ProcessingJobRecord) -> ProcessingStatusEnum:
    logger.info(
        f"Retrieving job status for job: {job.platform_job_id} (current: {job.status})"
    )
    platform = get_processing_platform(job.label)
    details = ServiceDetails.model_validate_json(job.service)
    return (
        await platform.get_job_status(
            user_token=token, job_id=job.platform_job_id, details=details
        )
        if job.platform_job_id
        else job.status
    )


async def get_processing_job_results(
    token: str,
    database: Session,
    job_id: int,
) -> Collection | None:
    user = get_current_user_id(token)
    record = get_job_by_user_id(database, job_id, user)
    if not record:
        return None

    logger.info(f"Retrieving job result for job: {record.platform_job_id}")
    platform = get_processing_platform(record.label)
    details = ServiceDetails.model_validate_json(record.service)
    return (
        await platform.get_job_results(
            user_token=token, job_id=record.platform_job_id, details=details
        )
        if record.platform_job_id
        else None
    )


async def _refresh_job_status(
    token: str,
    database: Session,
    record: ProcessingJobRecord,
) -> ProcessingJobRecord:
    new_status = await get_job_status(token, record)
    if new_status != record.status:
        update_job_status_by_id(database, record.id, new_status)
        record.status = new_status
    return record


async def get_processing_jobs_by_user_id(
    token: str, database: Session, upscaling_task_id: int | None = None
) -> List[ProcessingJobSummary]:
    user = get_current_user_id(token)
    logger.info(f"Retrieving processing jobs for user {user}")

    jobs: List[ProcessingJobSummary] = []
    records = get_jobs_by_user_id(database, user, upscaling_task_id)

    for record in records:
        # Only check status for active jobs
        if record.status not in INACTIVE_JOB_STATUSES:
            record = await _refresh_job_status(token, database, record)

        jobs.append(
            ProcessingJobSummary(
                id=record.id,
                title=record.title,
                label=record.label,
                status=record.status,
                parameters=json.loads(record.parameters),
                service=ServiceDetails.model_validate_json(record.service or "{}"),
            )
        )
    return jobs


async def get_processing_job_by_user_id(
    token: str,
    database: Session,
    job_id: int,
) -> Optional[ProcessingJob]:
    user = get_current_user_id(token)
    logger.info(f"Retrieving processing job with ID {job_id} for user {user}")
    record = get_job_by_user_id(database, job_id, user)
    if not record:
        return None

    if record.status not in INACTIVE_JOB_STATUSES:
        record = await _refresh_job_status(token, database, record)

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
