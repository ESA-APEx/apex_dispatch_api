from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas.unit_job import BaseJobRequest, ProcessingJob, ProcessingJobSummary
from app.services.processing import create_processing_job, get_processing_job_by_user_id

# from app.auth import get_current_user

router = APIRouter()


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
        logger.exception(f"Error creating unit job for user {user}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the processing job: {e}",
        )


@router.get(
    "/unit_jobs/{job_id}",
    tags=["Unit Jobs"],
    responses={404: {"description": "Processing job not found"}},
)
async def get_job(
    job_id: int, db: Session = Depends(get_db), user: str = "foobar"
) -> ProcessingJob:
    job = get_processing_job_by_user_id(db, job_id, user)
    if not job:
        logger.error(f"Processing job {job_id} not found for user {user}")
        raise HTTPException(
            status_code=404,
            detail=f"Processing job {job_id} not found",
        )
    return job
