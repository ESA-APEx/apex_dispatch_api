import logging
from fastapi import APIRouter, Query
from app.schemas import JobsStatusResponse


router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/jobs_status", response_model=JobsStatusResponse, tags=["Upscale Tasks", "Unit Jobs"], summary="Get a list of all upscaling tasks & processing jobs for the authenticated user")
async def jobs_status(
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
):
    """
    Return combined list of upscaling tasks and processing jobs for the authenticated user.
    """
    logger.debug(f"Fetching jobs status with limit={limit}, offset={offset}")
    return JobsStatusResponse(
        upscalingTasks=[],
        processingJobs=[]
    )
