import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas import JobsStatusResponse
from app.services.processing import get_processing_jobs_by_user_id

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/jobs_status",
    tags=["Upscale Tasks", "Unit Jobs"],
    summary="Get a list of all upscaling tasks & processing jobs for the authenticated user",
)
async def jobs_status(
    db: Session = Depends(get_db),
    user: str = "foobar",
) -> JobsStatusResponse:
    """
    Return combined list of upscaling tasks and processing jobs for the authenticated user.
    """
    logger.debug(f"Fetching jobs list for user {user}")
    processing_jobs = get_processing_jobs_by_user_id(db, user)
    print(processing_jobs)
    return JobsStatusResponse(
        upscaling_tasks=[], processing_jobs=get_processing_jobs_by_user_id(db, user)
    )
