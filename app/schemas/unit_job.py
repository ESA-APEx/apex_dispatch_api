from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum


class ServiceDetails(BaseModel):
    service: str
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


