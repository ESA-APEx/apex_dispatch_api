from typing import Annotated
from fastapi import Body, APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas.enum import ProcessTypeEnum
from app.schemas.unit_job import (
    ServiceDetails,
)
from app.schemas.upscale_task import (
    ParameterDimension,
    UpscalingTask,
    UpscalingTaskRequest,
    UpscalingTaskSummary,
)
from app.services.upscaling import create_upscaling_task, get_upscaling_task_by_user_id

# from app.auth import get_current_user

router = APIRouter()


@router.post(
    "/upscale_tasks",
    status_code=status.HTTP_201_CREATED,
    tags=["Upscale Tasks"],
    summary="Create a new upscaling task",
)
async def create_upscale_task(
    payload: Annotated[
        UpscalingTaskRequest,
        Body(
            openapi_examples={
                "openEO Example": {
                    "summary": "Valid openEO job request",
                    "description": "The following example demonstrates how to create an upscaling "
                    "task using an openEO-based service. This example triggers the "
                    "[`variability map`](https://github.com/ESA-APEx/apex_algorithms/blob/main/algo"
                    "rithm_catalog/vito/variabilitymap/records/variabilitymap.json) "
                    "process using the CDSE openEO Federation. In this case the `endpoint`"
                    "represents the URL of the openEO backend and the `application` refers to the "
                    "User Defined Process (UDP) that is being executed on the backend.",
                    "value": UpscalingTaskRequest(
                        label=ProcessTypeEnum.OPENEO,
                        title="Example openEO Job",
                        service=ServiceDetails(
                            endpoint="https://openeofed.dataspace.copernicus.eu",
                            application="https://raw.githubusercontent.com/ESA-APEx/apex_algorithms"
                            "/32ea3c9a6fa24fe063cb59164cd318cceb7209b0/openeo_udp/variabilitymap/"
                            "variabilitymap.json",
                        ),
                        parameters={
                            "temporal_extent": ["2025-05-01", "2025-05-01"],
                        },
                        dimension=ParameterDimension(
                            name="spatial_extent",
                            values=[
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
                        ),
                    ).model_dump(),
                }
            },
        ),
    ],
    db: Session = Depends(get_db),
    user: str = "foobar",
) -> UpscalingTaskSummary:
    """Create a new upscaling job with the provided data."""
    try:
        return create_upscaling_task(db, user, payload)
    except Exception as e:
        logger.exception(f"Error creating upscale task for user {user}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the upscale task: {e}",
        )


@router.get(
    "/upscale_tasks/{task_id}",
    tags=["Upscale Tasks"],
    responses={404: {"description": "Upscale task not found"}},
)
async def get_upscale_task(
    task_id: int, db: Session = Depends(get_db), user: str = "foobar"
) -> UpscalingTask:
    job = get_upscaling_task_by_user_id(db, task_id, user)
    if not job:
        logger.error(f"Upscale task {task_id} not found for user {user}")
        raise HTTPException(
            status_code=404,
            detail=f"Upscale task {task_id} not found",
        )
    return job
