from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models.processing_job import ProcessingJobRecord
from fastapi.responses import JSONResponse
from fastapi import status as http_status

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
    db_status = check_db_status(db)
    general_status = "ok" if db_status["status"] == "ok" else "error"
    status_code = (
        http_status.HTTP_200_OK
        if general_status == "ok"
        else http_status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "status": general_status,
            "database": db_status,
        },
    )
