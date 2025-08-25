from datetime import datetime
from typing import Any, List
from pydantic import BaseModel, Field
from app.schemas.enum import ProcessTypeEnum, ProcessingStatusEnum
from app.schemas.unit_job import BaseJobRequest, ProcessingJobSummary, ServiceDetails


class UpscalingTaskSummary(BaseModel):
    id: int = Field(
        ..., description="Unique identifier of the upscaling task", examples=[1]
    )
    title: str = Field(
        ..., description="Title of the upscaling task", examples=["Test Upscaling Task"]
    )
    label: ProcessTypeEnum = Field(
        ...,
        description="Label that is representing the type of the service that was executed",
        examples=[ProcessTypeEnum.OPENEO],
    )
    status: ProcessingStatusEnum = Field(
        ...,
        description="Status of the processing of the upscaling task",
        examples=[ProcessingStatusEnum.RUNNING],
    )


class UpscalingTaskDetails(BaseModel):
    service: ServiceDetails = Field(
        ..., description="Details of the service to be executed"
    )
    created: datetime = Field(..., description="Creation time of the processing job")
    updated: datetime = Field(
        ...,
        description="Timestamp representing the last time that the job details were updated",
    )
    jobs: List[ProcessingJobSummary] = Field(
        ...,
        description="List of processing jobs that were launched with the upscaling request",
        examples=[
            [
                ProcessingJobSummary(
                    id=1,
                    title="Upscaling Job 1",
                    label=ProcessTypeEnum.OPENEO,
                    status=ProcessingStatusEnum.FINISHED,
                    parameters={"param1": "value1", "param2": "value2"},
                ),
                ProcessingJobSummary(
                    id=1,
                    title="Upscaling Job 2",
                    label=ProcessTypeEnum.OPENEO,
                    status=ProcessingStatusEnum.RUNNING,
                    parameters={"param1": "value1", "param2": "value2"},
                ),
            ]
        ],
    )


class ParameterDimension(BaseModel):
    name: str = Field(
        ...,
        description="Name of the parameter for which to loop the multiple values",
        examples=["spatial_extent"],
    )
    values: List[Any] = Field(
        ...,
        min_length=1,
        description="List of values for which to create a processing job",
        examples=[
            [
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [4.813414938308839, 51.231275511382016],
                            [4.968699285344775, 51.231275511382016],
                            [4.968699285344775, 51.12105211672323],
                            [4.78903622852087, 51.123264199758346],
                            [4.813414938308839, 51.231275511382016],
                        ]
                    ],
                },
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [4.836037011633863, 51.331277680080774],
                            [4.968699285344775, 51.34099814769344],
                            [4.968699285344775, 51.231275511382016],
                            [4.813414938308839, 51.231275511382016],
                            [4.836037011633863, 51.331277680080774],
                        ]
                    ],
                },
            ],
        ],
    )


class UpscalingTaskRequest(BaseJobRequest):
    dimension: ParameterDimension = Field(
        ...,
        description="Parameter upon which the upscaling job should be executed",
    )


class UpscalingTask(UpscalingTaskDetails, UpscalingTaskSummary):
    pass
