from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models.processing_job import ProcessingJobRecord

router = APIRouter()


def check_db_status(db: Session) -> dict:
    try:
        if db.is_active:
            db.query(ProcessingJobRecord).limit(1).all()
            db_status = "ok"
            db_message = None
        else:
            raise Exception("Database session is not active")
    except Exception as e:
        logger.exception("Database connection check failed")
        db_status = "error"
        db_message = str(e)

    status = {
        "status": db_status,
    }
    if db_message:
        status["message"] = db_message
    return status


@router.get("/health")
async def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "database": check_db_status(db),
    }
