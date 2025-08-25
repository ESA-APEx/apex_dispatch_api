from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.database.models.upscaling_task import (
    UpscalingTaskRecord,
    get_upscale_task_by_user_id,
    get_upscale_tasks_by_user_id,
    save_upscaling_task_to_db,
    update_upscale_task_status_by_id,
)
from app.schemas.enum import ProcessingStatusEnum
from app.schemas.unit_job import BaseJobRequest, ProcessingJobSummary, ServiceDetails
from app.schemas.upscale_task import (
    UpscalingTask,
    UpscalingTaskRequest,
    UpscalingTaskSummary,
)
from app.services.processing import (
    create_processing_job,
    get_processing_jobs_by_user_id,
)

INACTIVE_TASK_STATUSES = {
    ProcessingStatusEnum.CANCELED,
    ProcessingStatusEnum.FAILED,
    ProcessingStatusEnum.FINISHED,
}


def create_upscaling_processing_jobs(
    database: Session, user: str, request: UpscalingTaskRequest, upscaling_task_id: int
) -> List[ProcessingJobSummary]:
    jobs: List[ProcessingJobSummary] = []

    logger.info(
        f"Splitting up upscaling task in processing jobs for parameter {request.dimension.name}"
    )

    # Create jobs
    for idx, value in enumerate(request.dimension.values):
        logger.debug(
            f"Creating processing job with id {idx}: {request.dimension.name}={value}"
        )
        jobs.append(
            create_processing_job(
                database=database,
                user=user,
                request=BaseJobRequest(
                    title=f"{request.title} - Processing Job {idx + 1}",
                    label=request.label,
                    service=request.service,
                    parameters={**request.parameters, request.dimension.name: value},
                ),
                upscaling_task_id=upscaling_task_id,
            )
        )
    return jobs


def create_upscaling_task(
    database: Session, user: str, request: UpscalingTaskRequest
) -> UpscalingTaskSummary:

    logger.info(f"Saving upscaling job for {user} to the database")
    record = UpscalingTaskRecord(
        title=request.title,
        label=request.label,
        status=ProcessingStatusEnum.CREATED,
        user_id=user,
        service=request.service.model_dump_json(),
    )
    record = save_upscaling_task_to_db(database, record)
    return UpscalingTaskSummary(
        id=record.id, title=record.title, label=record.label, status=record.status
    )


def _get_upscale_status(jobs: List[ProcessingJobSummary]) -> ProcessingStatusEnum:
    if not jobs:
        return ProcessingStatusEnum.CREATED  # edge case: no jobs

    statuses = {job.status for job in jobs}

    if ProcessingStatusEnum.RUNNING in statuses:
        return ProcessingStatusEnum.RUNNING
    if statuses == {ProcessingStatusEnum.FAILED}:
        return ProcessingStatusEnum.FAILED
    if statuses == {ProcessingStatusEnum.CANCELED}:
        return ProcessingStatusEnum.CANCELED
    if statuses.issubset({ProcessingStatusEnum.FINISHED, ProcessingStatusEnum.FAILED}):
        return ProcessingStatusEnum.FINISHED
    return ProcessingStatusEnum.CREATED


def _refresh_record_status(
    database: Session,
    record: UpscalingTaskRecord,
    jobs: List[ProcessingJobSummary],
) -> UpscalingTaskRecord:
    new_status = _get_upscale_status(jobs)
    if new_status != record.status:
        update_upscale_task_status_by_id(database, record.id, new_status)
        record.status = new_status
    return record


def get_upscaling_task_by_user_id(
    database: Session, task_id: int, user_id: str
) -> Optional[UpscalingTask]:

    logger.info(f"Retrieving upscaling task with ID {task_id} for user {user_id}")
    record = get_upscale_task_by_user_id(database, task_id, user_id)
    if not record:
        return None

    jobs = get_processing_jobs_by_user_id(database, user_id, record.id)
    if record.status not in INACTIVE_TASK_STATUSES:
        record = _refresh_record_status(database, record, jobs)

    return UpscalingTask(
        id=record.id,
        title=record.title,
        label=record.label,
        status=record.status,
        service=ServiceDetails.model_validate_json(record.service or "{}"),
        created=record.created,
        updated=record.updated,
        jobs=jobs,
    )


def get_upscaling_tasks_by_user_id(
    database: Session, user_id: str
) -> List[UpscalingTaskSummary]:

    logger.info(f"Retrieving upscaling tasks for user {user_id}")

    tasks: List[UpscalingTaskSummary] = []
    records = get_upscale_tasks_by_user_id(database, user_id)

    for record in records:
        if record.status not in INACTIVE_TASK_STATUSES:
            jobs = get_processing_jobs_by_user_id(database, user_id, record.id)
            record = _refresh_record_status(database, record, jobs)
        tasks.append(
            UpscalingTaskSummary(
                id=record.id,
                title=record.title,
                label=record.label,
                status=record.status,
            )
        )

    return tasks
