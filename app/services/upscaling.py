from typing import List, Optional
from sqlalchemy.orm import Session

from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.upscale_task import (
    UpscalingTask,
    UpscalingTaskRequest,
    UpscalingTaskSummary,
)


def create_upscaling_task(
    database: Session, user: str, summary: UpscalingTaskRequest
) -> UpscalingTaskSummary:
    return UpscalingTaskSummary(
        id=1,
        title="Dummy",
        label=ProcessTypeEnum.OPENEO,
        status=ProcessingStatusEnum.RUNNING,
    )


def get_upscaling_task_by_user_id(
    database: Session, job_id: int, user_id: str
) -> Optional[UpscalingTask]:
    pass


def get_upscaling_tasks_by_user_id(
    database: Session, user_id: str
) -> List[UpscalingTaskSummary]:
    return []
