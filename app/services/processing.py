import json
import logging
from typing import List, Optional
from app.database.models.processing_job import (
    ProcessingJobRecord,
    get_job_by_user_id,
    get_jobs_by_user_id,
    save_job_to_db,
    update_job_result_by_id,
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


logger = logging.getLogger(__name__)


def create_processing_job(
    database: Session, user: str, summary: BaseJobRequest
) -> ProcessingJobSummary:
    logger.info(f"Creating processing job with summary: {summary}")

    platform = get_processing_platform(summary.label)

    job_id = platform.execute_job(
        title=summary.title, details=summary.service, parameters=summary.parameters
    )

    record = ProcessingJobRecord(
        title=summary.title,
        label=summary.label,
        status=ProcessingStatusEnum.CREATED,
        user_id=user,
        platform_job_id=job_id,
        parameters=json.dumps(summary.parameters),
        result_link=None,
        service_record=summary.service.model_dump_json(),
    )
    record = save_job_to_db(database, record)
    return ProcessingJobSummary(
        id=record.id, title=record.title, label=summary.label, status=record.status
    )


def get_job_status(job: ProcessingJobRecord) -> ProcessingStatusEnum:
    logger.info(f"Retrieving job status for job: {job.platform_job_id}")
    platform = get_processing_platform(job.label)
    details = ServiceDetails.model_validate_json(job.service_record)
    return platform.get_job_status(job.platform_job_id, details)


def get_job_result_url(job: ProcessingJobRecord) -> str:
    logger.info(f"Retrieving job result for job: {job.platform_job_id}")
    platform = get_processing_platform(job.label)
    details = ServiceDetails.model_validate_json(job.service_record)
    return platform.get_job_result_url(job.platform_job_id, details)


def get_processing_jobs_by_user_id(
    database: Session, user_id: str
) -> List[ProcessingJobSummary]:
    logger.info(f"Retrieving processing jobs for user {user_id}")

    jobs: List[ProcessingJobSummary] = []
    records = get_jobs_by_user_id(database, user_id)

    inactive_statuses = {
        ProcessingStatusEnum.CANCELED,
        ProcessingStatusEnum.FAILED,
        ProcessingStatusEnum.FINISHED,
    }

    for record in records:
        # Only check status for active jobs
        if record.status not in inactive_statuses:
            latest_status = get_job_status(record)
            if latest_status != record.status:
                update_job_status_by_id(database, record.id, latest_status)
            status = latest_status
        else:
            status = record.status

        # Update the result if the job is finished and results weren't retrieved yet
        if status == ProcessingStatusEnum.FINISHED and not record.result_link:
            result_link = get_job_result_url(record)
            update_job_result_by_id(database, record.id, result_link)

        jobs.append(
            ProcessingJobSummary(
                id=record.id, title=record.title, label=record.label, status=status
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

    return ProcessingJob(
        id=record.id,
        title=record.title,
        label=record.label,
        status=record.status,
        service=ServiceDetails.model_validate_json(record.service_record or "{}"),
        parameters=json.loads(record.parameters or "{}"),
        result_link=record.result_link,
        created=record.created,
        updated=record.updated,
    )
