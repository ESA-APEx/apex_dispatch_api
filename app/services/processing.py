import json
import logging
from typing import List, Optional
from app.database.models.processing_job import (
    ProcessingJobRecord,
    get_job_by_user_id,
    get_jobs_by_user_id,
    save_job_to_db,
)
from app.platforms.dispatcher import get_processing_platform
from app.schemas import (
    BaseJobRequest,
    ProcessingJob,
    ProcessingJobSummary,
    ProcessingStatusEnum,
    ServiceDetails,
)
from sqlalchemy.orm import Session


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
        service_record=json.dumps(
            summary.service.model_dump_json()
        ),  # Assuming service is a dict
    )
    record = save_job_to_db(database, record)
    return ProcessingJobSummary(
        id=record.id, title=record.title, label=summary.label, status=record.status
    )


def get_processing_jobs_by_user_id(
    database: Session, user_id: str
) -> List[ProcessingJobSummary]:
    logger.info(f"Retrieving processing jobs for user {user_id}")
    return list(
        map(
            lambda x: ProcessingJobSummary(
                id=x.id, title=x.title, label=x.label, status=x.status
            ),
            get_jobs_by_user_id(database, user_id),
        )
    )


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
        service=ServiceDetails.model_validate_json(
            json.loads(record.service_record or "{}")
        ),
        parameters=json.loads(record.parameters or "{}"),
        result_link=record.result_link,
        created=record.created,
        updated=record.updated,
    )
