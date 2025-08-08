from enum import Enum
from typing import List
from pydantic import BaseModel

class ProcessType(str, Enum):
    OPENEO = "openeo"
    OGC_API_PROCESS = "ogc_api_process"
    
class ProcessingStatusEnum(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


# # Tile / GeoJSON placeholders
# class Tile(BaseModel):
#     type: Optional[str] = "Feature"
#     geometry: Optional[dict] = {}


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
    id: str
    title: str
    status: ProcessingStatusEnum


# class ProcessingJobDetails(BaseModel):
#     label: str
#     service: ServiceDetails
#     parameters: ServiceParameters


# class ProcessingJob(ProcessingJobSummary, ProcessingJobDetails):
#     pass


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
    processingJobs: List[ProcessingJobSummary]= []


class BaseJobRequest(BaseModel):
    title: str
    label: ProcessType
    service: ServiceDetails
    parameters: dict


# class UpscaleRequest(BaseJobRequest):
#     tiles: List[Tile] = []
