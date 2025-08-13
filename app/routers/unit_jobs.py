import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas import BaseJobRequest, ProcessingJobSummary, ProcessingJob
from app.services.processing import create_processing_job, get_processing_job_by_user_id

# from app.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/unit_jobs",
    status_code=status.HTTP_201_CREATED,
    tags=["Unit Jobs"],
    summary="Create a new processing job",
)
async def create_unit_job(
    payload: BaseJobRequest, db: Session = Depends(get_db), user: str = "foobar"
) -> ProcessingJobSummary:
    """Create a new processing job with the provided data."""
    try:
        return create_processing_job(db, user, payload)
    except Exception as e:
        logger.error(f"Error creating unit job for user {user}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the processing job: {e}",
        )


@router.get("/unit_jobs/{job_id}", tags=["Unit Jobs"])
async def get_job(
    job_id: int, db: Session = Depends(get_db), user: str = "foobar"
) -> ProcessingJob:
    job = get_processing_job_by_user_id(db, job_id, user)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Processing job {job_id} not found",
        )
    return job
