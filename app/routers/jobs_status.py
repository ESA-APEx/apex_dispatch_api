import asyncio
import json
from typing import List

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from loguru import logger

from app.database.db import SessionLocal, get_db
from app.schemas.jobs_status import JobsFilter, JobsStatusResponse
from app.schemas.websockets import WSStatusMessage
from app.services.processing import get_processing_jobs_by_user_id
from app.services.upscaling import get_upscaling_tasks_by_user_id
from app.auth import oauth2_scheme, websocket_authenticate

router = APIRouter()

DEFAULT_FILTERS = [JobsFilter.upscaling, JobsFilter.processing]


@router.get(
    "/jobs_status",
    tags=["Upscale Tasks", "Unit Jobs"],
    summary="Get a list of all upscaling tasks & processing jobs for the authenticated user",
)
async def get_jobs_status(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
    filter: List[JobsFilter] = Query(
        DEFAULT_FILTERS,
        description="Filter jobs: upscaling, processing. Can be provided multiple times.",
    ),
) -> JobsStatusResponse:
    """
    Return combined list of upscaling tasks and processing jobs for the authenticated user.
    """
    logger.debug(f"Fetching jobs list")
    upscaling_tasks = (
        await get_upscaling_tasks_by_user_id(token, db)
        if JobsFilter.upscaling in filter
        else []
    )
    processing_jobs = (
        await get_processing_jobs_by_user_id(token, db)
        if JobsFilter.processing in filter
        else []
    )
    return JobsStatusResponse(
        upscaling_tasks=upscaling_tasks,
        processing_jobs=processing_jobs,
    )


@router.websocket(
    "/ws/jobs_status",
)
async def ws_jobs_status(
    websocket: WebSocket,
    interval: int = 10,
    filter: List[JobsFilter] = Query(DEFAULT_FILTERS),
):
    """
    Return combined list of upscaling tasks and processing jobs for the authenticated user.
    """

    token = await websocket_authenticate(websocket)
    if not token:
        return

    await websocket.send_json(
        WSStatusMessage(type="init", message="Starting status stream").model_dump()
    )

    try:
        while True:
            with SessionLocal() as db:
                await websocket.send_json(
                    WSStatusMessage(
                        type="loading",
                        message="Starting retrieval of status",
                    ).model_dump()
                )
                status = await get_jobs_status(db, token, filter=filter)
                await websocket.send_json(
                    WSStatusMessage(
                        type="status",
                        data=json.loads(status.model_dump_json()),
                    ).model_dump()
                )
                await asyncio.sleep(interval)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception(f"Error in jobs_status_ws: {e}")
        await websocket.close(code=1011, reason="Error in job status websocket: {e}")
    finally:
        db.close()
