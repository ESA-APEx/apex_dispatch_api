
import logging
from app.platforms.dispatcher import get_processing_platform
from app.schemas import BaseJobRequest, ProcessingJobSummary 


logger = logging.getLogger(__name__)

def create_processing_job(summary: BaseJobRequest) -> ProcessingJobSummary:
    logger.info(f"Creating processing job with summary: {summary}")
    
    platform = get_processing_platform(summary.label)
    
    return platform.execute_job(
        service_id=summary.service.id,
        parameters=summary.parameters
    )