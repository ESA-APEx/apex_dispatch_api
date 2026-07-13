from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field


class EntityStatistics(BaseModel):
    total: int = Field(..., description="Total amount of records")
    by_status: Dict[str, int] = Field(..., description="Totals grouped by status")
    by_platform: Dict[str, int] = Field(
        ..., description="Totals grouped by platform label"
    )
    by_service: Dict[str, int] = Field(
        ...,
        description="Totals grouped by executed service process ID",
    )


class UpscalingStatistics(EntityStatistics):
    average_processing_jobs_per_upscaling_task: float = Field(
        ..., description="Average number of processing jobs linked to each upscaling task"
    )


class PublicStatisticsResponse(BaseModel):
    generated_at: datetime = Field(..., description="Timestamp when stats were generated")
    processing_jobs: EntityStatistics = Field(
        ..., description="Statistics for executed processing jobs"
    )
    upscaling_tasks: UpscalingStatistics = Field(
        ..., description="Statistics for executed upscaling tasks"
    )
