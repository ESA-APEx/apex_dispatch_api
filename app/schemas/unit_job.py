from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.enum import ProcessingStatusEnum, ProcessTypeEnum


class ServiceDetails(BaseModel):
    endpoint: str
    application: str


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


class BaseJobRequest(BaseModel):
    title: str
    label: ProcessTypeEnum
    service: ServiceDetails
    parameters: dict
