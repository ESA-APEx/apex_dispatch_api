import datetime
from typing import List, Optional

from loguru import logger
from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database.db import Base
from app.schemas.unit_job import ProcessingStatusEnum, ProcessTypeEnum


class UpscalingTaskRecord(Base):
    __tablename__ = "upscaling_tasks"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    title: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[ProcessTypeEnum] = mapped_column(Enum(ProcessTypeEnum), index=True)
    status: Mapped[ProcessingStatusEnum] = mapped_column(
        Enum(ProcessingStatusEnum), index=True
    )
    user_id: Mapped[str] = mapped_column(String, index=True)
    service: Mapped[str] = mapped_column(String, index=True)
    created: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, index=True
    )
    updated: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        index=True,
    )


def save_upscaling_task_to_db(
    db_session: Session, task: UpscalingTaskRecord
) -> UpscalingTaskRecord:
    """
    Save an upscaling task record to the database and update the ID of the task.

    :param db_session: The database session to use for saving the task.
    :param job: The UpscalingTaskRecord instance to save.
    """
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)  # Refresh to get the ID after commit
    logger.debug(f"Upscale task saved with ID: {task.id}")
    return task


def get_upscale_tasks_by_user_id(
    database: Session, user_id: str
) -> List[UpscalingTaskRecord]:
    logger.info(f"Retrieving all upscale tasks for user {user_id}")
    return (
        database.query(UpscalingTaskRecord)
        .filter(UpscalingTaskRecord.user_id == user_id)
        .all()
    )


def get_upscale_task_by_id(
    database: Session, task_id: int
) -> Optional[UpscalingTaskRecord]:
    logger.info(f"Retrieving upscale task with ID {task_id}")
    return (
        database.query(UpscalingTaskRecord)
        .filter(UpscalingTaskRecord.id == task_id)
        .first()
    )


def get_upscale_task_by_user_id(
    database: Session, task_id: int, user_id: str
) -> Optional[UpscalingTaskRecord]:
    logger.info(f"Retrieving upscale task with ID {task_id} for user {user_id}")
    return (
        database.query(UpscalingTaskRecord)
        .filter(
            UpscalingTaskRecord.id == task_id, UpscalingTaskRecord.user_id == user_id
        )
        .first()
    )


def update_upscale_task_status_by_id(
    database: Session, task_id: int, status: ProcessingStatusEnum
):
    logger.info(f"Updating the status of upscale task with ID {task_id} to {status}")
    task = get_upscale_task_by_id(database, task_id)

    if task:
        task.status = status
        database.commit()
        database.refresh(task)
    else:
        logger.warning(
            f"Could not update upscaling task status of task {task_id} as it could not be found in the database"
        )


# def get_jobs_by_user_id(database: Session, user_id: str) -> List[ProcessingJobRecord]:
#     logger.info(f"Retrieving all processing jobs for user {user_id}")
#     return (
#         database.query(ProcessingJobRecord)
#         .filter(
#             ProcessingJobRecord.user_id == user_id,
#             ProcessingJobRecord.upscaling_task_id is None,
#         )
#         .all()
#     )
