from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.enum import ProcessingStatusEnum, ProcessTypeEnum


class ServiceDetails(BaseModel):
    endpoint: str = Field(
        ...,
        description="URL to the endpoint where the service is hosted. For openEO, this is the "
        "openEO backend. For OGC API Processes, this field should include the base URL of the "
        "platform API",
        examples=["https://openeofed.dataspace.copernicus.eu"],
    )
    application: str = Field(
        ...,
        description="Path to the application that needs to be executed. For openEO this is "
        "referring to the public URL of the UDP (JSON) to execute. For OGC API Processes, this "
        "field should include the URL path pointing to the hosted service.",
        examples=[
            "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/32ea3c9a6fa24fe063cb59164cd318cceb7209b0/openeo_udp/variabilitymap/variabilitymap.json"
        ],
    )


class ProcessingJobSummary(BaseModel):
    id: int = Field(
        ..., description="Unique identifier of the processing job", examples=[1]
    )
    title: str = Field(
        ..., description="Title of the job", examples=["Test Processing Job"]
    )
    label: ProcessTypeEnum = Field(
        ...,
        description="Label that is representing the type of the service that will be executed",
        examples=[ProcessTypeEnum.OPENEO],
    )
    status: ProcessingStatusEnum = Field(
        ...,
        description="Current status of the processing job",
        examples=[ProcessingStatusEnum.RUNNING],
    )


class ProcessingJobDetails(BaseModel):
    service: ServiceDetails = Field(
        ..., description="Details of the service to be executed"
    )
    parameters: dict = Field(
        ...,
        description="JSON representing the parameters for the service execution",
        examples=[{"param1": "value1", "param2": "value2"}],
    )
    result_link: Optional[str] = Field(
        ...,
        description="URL to the results of the processing job",
        examples=[
            "https://openeofed.dataspace.copernicus.eu/jobs/cdse-j-25082106161041f1a151bd539f614130/results"
        ],
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
        ...,
        description="JSON representing the parameters for the service execution",
    )
