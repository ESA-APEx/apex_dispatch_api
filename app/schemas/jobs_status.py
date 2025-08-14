from typing import List
from pydantic import BaseModel

from app.schemas.unit_job import ProcessingJobSummary
from app.schemas.upscaling_task import UpscalingTaskSummary


class JobsStatusResponse(BaseModel):
    upscaling_tasks: List[UpscalingTaskSummary] = []
    processing_jobs: List[ProcessingJobSummary] = []
