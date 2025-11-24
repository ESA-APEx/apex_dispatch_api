import datetime
import json
from typing import List, Optional

from loguru import logger
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database.db import Base
from app.schemas.unit_job import ProcessingStatusEnum, ProcessTypeEnum

from stac_pydantic import Collection


class ProcessingJobRecord(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    title: Mapped[str] = mapped_column(String(255), index=True)
    label: Mapped[ProcessTypeEnum] = mapped_column(Enum(ProcessTypeEnum), index=True)
    status: Mapped[ProcessingStatusEnum] = mapped_column(
        Enum(ProcessingStatusEnum), index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    platform_job_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    parameters: Mapped[str] = mapped_column(LONGTEXT())
    service: Mapped[str] = mapped_column(LONGTEXT())
    created: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, index=True
    )
    updated: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        index=True,
    )

    upscaling_task_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("upscaling_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )


def save_job_to_db(
    db_session: Session, job: ProcessingJobRecord
) -> ProcessingJobRecord:
    """
    Save a processing job record to the database and update the ID of the job.

    :param db_session: The database session to use for saving the job.
    :param job: The ProcessingJobRecord instance to save.
    """
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)  # Refresh to get the ID after commit
    logger.debug(f"Processing job saved with ID: {job.id}")
    return job


def get_jobs_by_user_id(
    database: Session, user_id: str, upscaling_task_id: Optional[int]
) -> List[ProcessingJobRecord]:
    logger.info(
        f"Retrieving all processing jobs for user {user_id} for upscaling task {upscaling_task_id}"
    )
    return (
        database.query(ProcessingJobRecord)
        .filter(
            ProcessingJobRecord.user_id == user_id,
            (
                ProcessingJobRecord.upscaling_task_id == upscaling_task_id
                if upscaling_task_id
                else ProcessingJobRecord.upscaling_task_id.is_(None)
            ),
        )
        .all()
    )


def get_job_by_id(database: Session, job_id: int) -> Optional[ProcessingJobRecord]:
    logger.info(f"Retrieving processing job with ID {job_id}")
    return (
        database.query(ProcessingJobRecord)
        .filter(ProcessingJobRecord.id == job_id)
        .first()
    )


def get_job_by_user_id(
    database: Session, job_id: int, user_id: str
) -> Optional[ProcessingJobRecord]:
    logger.info(f"Retrieving processing job with ID {job_id} for user {user_id}")
    return (
        database.query(ProcessingJobRecord)
        .filter(
            ProcessingJobRecord.id == job_id, ProcessingJobRecord.user_id == user_id
        )
        .first()
    )


def update_job_status_by_id(
    database: Session, job_id: int, status: ProcessingStatusEnum
):
    logger.info(f"Updating the status of processing job with ID {job_id} to {status}")
    job = get_job_by_id(database, job_id)

    if job:
        job.status = status
        database.commit()
        database.refresh(job)
    else:
        logger.warning(
            f"Could not update job status of job {job_id} as it could not be found in the database"
        )


def update_job_result_by_id(database: Session, job_id: int, result: Collection):
    logger.info(f"Updating the result link of processing job with ID {job_id}")
    job = get_job_by_id(database, job_id)

    if job:
        job.result = json.dumps(result)
        database.commit()
        database.refresh(job)
    else:
        logger.warning(
            f"Could not update job result link of job {job_id} as it could not be found in "
            "the database"
        )
