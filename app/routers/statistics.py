from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.error import DispatcherException, ErrorResponse, InternalException
from app.middleware.error_handling import get_dispatcher_error_response
from app.schemas.statistics import PublicStatisticsResponse
from app.services.statistics import get_public_statistics

router = APIRouter()


@router.get(
    "/statistics",
    tags=["Statistics"],
    summary="Get public statistics for executed processing jobs and upscaling tasks",
    responses={
        InternalException.http_status: {
            "description": "Internal server error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        InternalException(), "request-id"
                    )
                }
            },
        },
    },
)
async def get_statistics(
    db: Session = Depends(get_db),
    date_from: date | None = Query(
        default=None,
        description=(
            "Start date (inclusive) for filtering records by creation date, "
            "format YYYY-MM-DD"
        ),
    ),
    date_to: date | None = Query(
        default=None,
        description=(
            "End date (inclusive) for filtering records by creation date, "
            "format YYYY-MM-DD"
        ),
    ),
) -> PublicStatisticsResponse:
    try:
        if date_from and date_to and date_from > date_to:
            raise HTTPException(
                status_code=400,
                detail="date_from must be before or equal to date_to",
            )

        return get_public_statistics(
            database=db,
            date_from=date_from,
            date_to=date_to,
        )
    except HTTPException as he:
        raise he
    except DispatcherException as de:
        raise de
    except Exception as e:
        logger.error(f"Error retrieving public statistics: {e}")
        raise InternalException(
            message="An error occurred while retrieving public statistics.",
            details={"error": str(e)},
        )
