from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class ProcessTypeEnum(str, Enum):
    OPENEO = "openeo"
    OGC_API_PROCESS = "ogc_api_process"


class ProcessingStatusEnum(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"

# class TileRequest(BaseModel):
#     aoi: dict
#     grid: str


# class TileResponse(BaseModel):
#     tiles: List[Tile] = []


# Service parameters
class ServiceDetails(BaseModel):
    service: str
    application: str


# # Process type, status
# class ProcessType(str):
#     pass


# class ProcessingStatus(str):
#     pass


class ProcessingJobSummary(BaseModel):
    id: int
    title: str
    label: ProcessTypeEnum
    status: ProcessingStatusEnum


class ProcessingJobDetails(BaseModel):
    service: ServiceDetails
    parameters: dict
    result_link: Optional[str]
    created: datetime
    updated: datetime


class ProcessingJob(ProcessingJobSummary, ProcessingJobDetails):
    pass


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


class JobsStatusResponse(BaseModel):
    upscalingTasks: List[UpscalingTaskSummary] = []
    processingJobs: List[ProcessingJobSummary] = []


class BaseJobRequest(BaseModel):
    title: str
    label: ProcessTypeEnum
    service: ServiceDetails
    parameters: dict


# class UpscaleRequest(BaseJobRequest):
#     tiles: List[Tile] = []
