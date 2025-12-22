from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from app.schemas.enum import ProcessTypeEnum
from app.schemas.unit_job import ServiceDetails


class ParamTypeEnum(str, Enum):
    DATE_INTERVAL = "date-interval"
    BOUNDING_BOX = "bounding-box"
    BOOLEAN = "boolean"
    STRING = "string"


class ParamRequest(BaseModel):
    label: ProcessTypeEnum = Field(
        ...,
        description="Label representing the type of the service",
    )
    service: ServiceDetails = Field(
        ..., description="Details of the service for which to retrieve the parameters"
    )


class Parameter(BaseModel):
    name: str = Field(..., description="Name of the parameter", examples=["param1"])
    type: ParamTypeEnum = Field(
        ...,
        description="Data type of the parameter",
        examples=[ParamTypeEnum.DATE_INTERVAL],
    )
    optional: bool = Field(
        ...,
        description="Indicates whether the parameter is optional",
        examples=[False],
    )
    description: str = Field(
        ...,
        description="Description of the parameter",
        examples=["This parameter specifies the ..."],
    )
    default: Any = Field(
        None,
        description="Default value of the parameter, if any",
        examples=["default_value"],
    )
