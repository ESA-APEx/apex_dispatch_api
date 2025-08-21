from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.enum import ProcessingStatusEnum, ProcessTypeEnum


class ServiceDetails(BaseModel):
    endpoint: str = Field(
        ...,
        description="URL to the endpoint where the service is hosted. For openEO, this is the openEO backend. For OGC API Processes, this field should include the base URL of the platform API",
    )
    application: str = Field(
        ...,
        description="Path to the application that needs to be executed. For openEO this is referring to the public URL of the UDP (JSON) to execute. For OGC API Processes, this field should include the URL path pointing to the hosted service.",
    )


class ProcessingJobSummary(BaseModel):
    id: int = Field(..., description="Unique identifier of the processing job")
    title: str = Field(..., description="Title of the job")
    label: ProcessTypeEnum = Field(
        ...,
        description="Label that is representing the type of the service that will be executed",
    )
    status: ProcessingStatusEnum = Field(
        ..., description="Current status of the processing job"
    )


class ProcessingJobDetails(BaseModel):
    service: ServiceDetails = Field(
        ..., description="Details of the service to be executed"
    )
    parameters: dict = Field(
        ..., description="JSON representing the parameters for the service execution"
    )
    result_link: Optional[str] = Field(
        ..., description="URL to the results of the processing job"
    )
    created: datetime = Field(..., description="Creation time of the processing job")
    updated: datetime = Field(
        ...,
        description="Timestamp representing the last time that the job details were updated",
    )


class ProcessingJob(ProcessingJobSummary, ProcessingJobDetails):
    pass


class BaseJobRequest(BaseModel):
    title: str = Field(..., description="Title of the job to execute")
    label: ProcessTypeEnum = Field(
        ...,
        description="Label that is representing the type of the service that will be executed",
    )
    service: ServiceDetails = Field(
        ..., description="Details of the service to be executed"
    )
    parameters: dict = Field(
        ..., description="JSON representing the parameters for the service execution"
    )
