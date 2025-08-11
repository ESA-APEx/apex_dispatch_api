
import json
import logging
from typing import List
from app.database.models.processing_job import ProcessingJobRecord, get_jobs_by_user_id, save_job_to_db
from app.platforms.dispatcher import get_processing_platform
from app.schemas import BaseJobRequest, ProcessingJobSummary, ProcessingStatusEnum 
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

def create_processing_job(database: Session, user: str, summary: BaseJobRequest) -> ProcessingJobSummary:
    logger.info(f"Creating processing job with summary: {summary}")
    
    platform = get_processing_platform(summary.label)
    
    job_id = platform.execute_job(
        title=summary.title,
        details=summary.service,
        parameters=summary.parameters
    )
    
    record = ProcessingJobRecord(
        title=summary.title,
        status=ProcessingStatusEnum.CREATED,
        user_id=user,
        platform_job_id=job_id,
        parameters=json.dumps(summary.parameters), 
        result_link=None,
        service_record=json.dumps(summary.service.model_dump_json()),  # Assuming service is a dict
    ) 
    record = save_job_to_db(database, record)
    return ProcessingJobSummary(
        id=record.id,
        title=record.title,
        status=record.status
    )


def get_processing_jobs_by_user_id(database: Session, user: str) -> List[ProcessingJobSummary]:
    logger.info(f"Retrieving processing jobs for user: {user}")
    return list(map(lambda x: ProcessingJobSummary(id=x.id, title=x.title, status=x.status) , get_jobs_by_user_id(database, user)))