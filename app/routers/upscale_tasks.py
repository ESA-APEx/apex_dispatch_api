import asyncio
import json
from typing import Annotated
from fastapi import (
    BackgroundTasks,
    Body,
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from loguru import logger
from sqlalchemy.orm import Session

from app.auth import oauth2_scheme, websocket_authenticate
from app.database.db import SessionLocal, get_db
from app.schemas.enum import OutputFormatEnum, ProcessTypeEnum
from app.schemas.unit_job import (
    ServiceDetails,
)
from app.schemas.upscale_task import (
    ParameterDimension,
    UpscalingTask,
    UpscalingTaskRequest,
    UpscalingTaskSummary,
)
from app.schemas.websockets import WSTaskStatusMessage
from app.services.upscaling import (
    create_upscaling_processing_jobs,
    create_upscaling_task,
    get_upscaling_task_by_user_id,
)

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
                        format=OutputFormatEnum.GEOTIFF,
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> UpscalingTaskSummary:
    """Create a new upscaling job with the provided data."""
    try:
        task = create_upscaling_task(token, db, payload)
        background_tasks.add_task(
            create_upscaling_processing_jobs,
            token=token,
            database=db,
            request=payload,
            upscaling_task_id=task.id,
        )
        return task
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Error creating upscale task: {e}")
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
    task_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> UpscalingTask:
    try:
        job = await get_upscaling_task_by_user_id(token, db, task_id)
        if not job:
            logger.error(f"Upscale task {task_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"Upscale task {task_id} not found",
            )
        return job
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Error retrieving upscale task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving the upscale task {task_id}: {e}",
        )


@router.websocket(
    "/ws/upscale_tasks/{task_id}",
)
async def ws_task_status(
    websocket: WebSocket,
    task_id: int,
    interval: int = 10,
):
    token = await websocket_authenticate(websocket)
    if not token:
        return

    logger.info("WebSocket connected", extra={"token": token, "task_id": task_id})

    try:
        await websocket.send_json(
            WSTaskStatusMessage(
                type="init", task_id=task_id, message="Starting status stream"
            ).model_dump()
        )
        while True:
            with SessionLocal() as db:
                await websocket.send_json(
                    WSTaskStatusMessage(
                        type="loading",
                        task_id=task_id,
                        message="Starting retrieval of status",
                    ).model_dump()
                )
                status = await get_upscale_task(task_id, db, token)
                if not status:
                    await websocket.send_json(
                        WSTaskStatusMessage(
                            type="error",
                            task_id=task_id,
                            message="Task not found",
                        ).model_dump()
                    )
                    await websocket.close(
                        code=1011, reason=f"Upscale task {task_id} not found"
                    )
                    break
                await websocket.send_json(
                    WSTaskStatusMessage(
                        type="status",
                        task_id=task_id,
                        data=json.loads(status.model_dump_json()),
                    ).model_dump()
                )
                await asyncio.sleep(interval)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception(f"Error in upscaling task status websocket: {e}")
        await websocket.close(code=1011, reason=f"Error in job status websocket: {e}")
