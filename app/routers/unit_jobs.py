import logging
from app.services.processing import create_processing_job
from fastapi import APIRouter, status, HTTPException
from app.schemas import BaseJobRequest, ProcessingJobSummary 
# from app.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/unit_jobs", response_model=ProcessingJobSummary, status_code=status.HTTP_201_CREATED, tags=["Unit Jobs"], summary="Create a new processing job")
async def create_unit_job(
    payload: BaseJobRequest, 
    ): 
    """Create a new processing job with the provided data."""
    try:
        return create_processing_job(payload)
    except Exception as e:
        logger.error(f"Error creating unit job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the processing job: {e}"
        )