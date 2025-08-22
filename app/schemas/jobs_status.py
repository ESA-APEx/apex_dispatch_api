from typing import List
from pydantic import BaseModel, Field

from app.schemas.unit_job import ProcessingJobSummary
from app.schemas.upscaling_task import UpscalingTaskSummary


class JobsStatusResponse(BaseModel):
    upscaling_tasks: List[UpscalingTaskSummary] = Field(
        ..., description="List of upscaling tasks that are available for the user"
    )
    processing_jobs: List[ProcessingJobSummary] = Field(
        ..., description="List of processing jobs that are available for the user"
    )
