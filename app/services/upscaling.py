from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.database.models.upscaling_task import (
    UpscalingTaskRecord,
    save_upscaling_task_to_db,
)
from app.schemas.enum import ProcessingStatusEnum
from app.schemas.unit_job import BaseJobRequest, ProcessingJobSummary
from app.schemas.upscale_task import (
    UpscalingTask,
    UpscalingTaskRequest,
    UpscalingTaskSummary,
)
from app.services.processing import create_processing_job


def _create_upscaling_processing_jobs(
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

    logger.info(f"Creating upscaling job for {user} with request: {request}")
    _create_upscaling_processing_jobs(
        database=database, user=user, request=request, upscaling_task_id=record.id
    )

    return UpscalingTaskSummary(
        id=record.id, title=record.title, label=record.label, status=record.status
    )


def get_upscaling_task_by_user_id(
    database: Session, job_id: int, user_id: str
) -> Optional[UpscalingTask]:
    pass


def get_upscaling_tasks_by_user_id(
    database: Session, user_id: str
) -> List[UpscalingTaskSummary]:
    return []
