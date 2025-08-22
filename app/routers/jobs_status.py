import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from loguru import logger

from app.database.db import get_db
from app.schemas.jobs_status import JobsStatusResponse
from app.services.processing import get_processing_jobs_by_user_id
from app.services.upscaling import get_upscaling_tasks_by_user_id

router = APIRouter()


@router.get(
    "/jobs_status",
    tags=["Upscale Tasks", "Unit Jobs"],
    summary="Get a list of all upscaling tasks & processing jobs for the authenticated user",
)
async def get_jobs_status(
    db: Session = Depends(get_db),
    user: str = "foobar",
) -> JobsStatusResponse:
    """
    Return combined list of upscaling tasks and processing jobs for the authenticated user.
    """
    logger.debug(f"Fetching jobs list for user {user}")
    return JobsStatusResponse(
        upscaling_tasks=get_upscaling_tasks_by_user_id(db, user),
        processing_jobs=get_processing_jobs_by_user_id(db, user),
    )


@router.websocket(
    "/ws/jobs_status",
)
async def ws_jobs_status(
    websocket: WebSocket, user: str = "foobar", interval: int = 10
) -> JobsStatusResponse:
    """
    Return combined list of upscaling tasks and processing jobs for the authenticated user.
    """

    await websocket.accept()
    logger.debug(f"WebSocket connected for user {user}")

    await websocket.send_json({"message": "Loading the job status"})

    db = next(get_db())
    try:
        while True:
            status = await get_jobs_status(db, user)
            await websocket.send_json(status.model_dump())

            await asyncio.sleep(interval)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user}")
    except Exception as e:
        logger.exception(f"Error in jobs_status_ws: {e}")
        await websocket.close(code=1011, reason="Error in job status websocket: {e}")
    finally:
        db.close()
