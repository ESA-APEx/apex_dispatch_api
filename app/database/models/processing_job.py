import datetime
import logging
from typing import List
from sqlalchemy import Column, DateTime, Enum, Integer, String
from app.database.db import Base
from sqlalchemy.orm import Session

from app.schemas import ProcessingStatusEnum


logger = logging.getLogger(__name__)


class ProcessingJobRecord(Base):
    __tablename__ = 'processing_jobs'
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, index=True)
    label = Column(String, index=True)
    status = Column(Enum(ProcessingStatusEnum), index=True)
    user_id = Column(String, index=True)
    platform_job_id = Column(String, index=True)
    parameters = Column(String, index=False)
    result_link = Column(String, index=False)
    service_record = Column(String, index=True)
    created = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    updated = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, index=True)

        
    
def save_job_to_db(db_session: Session, job: ProcessingJobRecord) -> ProcessingJobRecord:
    """
    Save a processing job record to the database and update the ID of the job.
    
    :param db_session: The database session to use for saving the job.
    :param job: The ProcessingJobRecord instance to save.
    """ 
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)  # Refresh to get the ID after commit
    logger.debug("Processing job saved with ID: {job.id}") 
    return job
    

def get_jobs_by_user_id(database: Session, user_id: str) -> List[ProcessingJobRecord]:
    logger.info(f"Retrieving all processing jobs for user {user_id}")
    return database.query(ProcessingJobRecord).filter(ProcessingJobRecord.user_id == user_id).all()

def get_job_by_user_id(database: Session, job_id: int, user_id: str) -> ProcessingJobRecord:
    logger.info(f"Retrieving processing job with ID {job_id} for user {user_id}")
    return database.query(ProcessingJobRecord).filter(ProcessingJobRecord.id == job_id, ProcessingJobRecord.user_id == user_id).first()