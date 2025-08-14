from pydantic import BaseModel
from app.schemas.enum import ProcessingStatusEnum


class UpscalingTaskSummary(BaseModel):
    id: int
    title: str
    status: ProcessingStatusEnum


# class UpscalingTaskDetails(BaseModel):
#     label: str
#     service: ServiceDetails
#     parameters: ServiceParameters
#     jobs: List[ProcessingJob] = []


# class UpscalingTask(UpscalingTaskSummary, UpscalingTaskDetails):
#     pass

# class UpscaleRequest(BaseJobRequest):
#     tiles: List[Tile] = []
