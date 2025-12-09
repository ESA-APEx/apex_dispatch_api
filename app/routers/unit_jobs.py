from typing import Annotated
from fastapi import Body, APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.auth import oauth2_scheme
from app.database.db import get_db
from app.error import (
    AuthException,
    DispatcherException,
    ErrorResponse,
    InternalException,
    JobNotFoundException,
)
from app.middleware.error_handling import get_dispatcher_error_response
from app.schemas.enum import OutputFormatEnum, ProcessTypeEnum
from app.schemas.unit_job import (
    BaseJobRequest,
    ProcessingJob,
    ProcessingJobSummary,
    ServiceDetails,
)
from app.services.processing import (
    create_processing_job,
    get_processing_job_by_user_id,
    get_processing_job_results,
)

from stac_pydantic import Collection

# from app.auth import get_current_user

router = APIRouter()


@router.post(
    "/unit_jobs",
    status_code=status.HTTP_201_CREATED,
    tags=["Unit Jobs"],
    summary="Create a new processing job",
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
async def create_unit_job(
    payload: Annotated[
        BaseJobRequest,
        Body(
            openapi_examples={
                "openEO Example": {
                    "summary": "Valid openEO job request",
                    "description": "The following example demonstrates how to create a processing "
                    "job using an openEO-based service. This example triggers the "
                    "[`variability map`](https://github.com/ESA-APEx/apex_algorithms/blob/main/algo"
                    "rithm_catalog/vito/variabilitymap/records/variabilitymap.json) "
                    "process using the CDSE openEO Federation. In this case the `endpoint`"
                    "represents the URL of the openEO backend and the `application` refers to the "
                    "User Defined Process (UDP) that is being executed on the backend.",
                    "value": BaseJobRequest(
                        label=ProcessTypeEnum.OPENEO,
                        title="Example openEO Job",
                        service=ServiceDetails(
                            endpoint="https://openeofed.dataspace.copernicus.eu",
                            application="https://raw.githubusercontent.com/ESA-APEx/apex_algorithms"
                            "/32ea3c9a6fa24fe063cb59164cd318cceb7209b0/openeo_udp/variabilitymap/"
                            "variabilitymap.json",
                        ),
                        format=OutputFormatEnum.GEOTIFF,
                        parameters={
                            "spatial_extent": {
                                "type": "FeatureCollection",
                                "features": [
                                    {
                                        "type": "Feature",
                                        "properties": {},
                                        "geometry": {
                                            "coordinates": [
                                                [
                                                    [
                                                        5.170043941798298,
                                                        51.25050990858725,
                                                    ],
                                                    [
                                                        5.171035037521989,
                                                        51.24865722468999,
                                                    ],
                                                    [
                                                        5.178521828188366,
                                                        51.24674578027137,
                                                    ],
                                                    [
                                                        5.179084341977159,
                                                        51.24984764553983,
                                                    ],
                                                    [
                                                        5.170043941798298,
                                                        51.25050990858725,
                                                    ],
                                                ]
                                            ],
                                            "type": "Polygon",
                                        },
                                    }
                                ],
                            },
                            "temporal_extent": ["2025-05-01", "2025-05-01"],
                        },
                    ).model_dump(),
                }
            },
        ),
    ],
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> ProcessingJobSummary:
    """Create a new processing job with the provided data."""
    try:
        return await create_processing_job(token, db, payload)
    except DispatcherException as de:
        raise de
    except Exception as e:
        logger.error(f"Error creating processing job: {e}")
        raise InternalException(
            message="An error occurred while creating processing job."
        )


@router.get(
    "/unit_jobs/{job_id}",
    tags=["Unit Jobs"],
    responses={
        JobNotFoundException.http_status: {
            "description": "Job not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        JobNotFoundException(), "request-id"
                    )
                }
            },
        },
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
async def get_job(
    job_id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> ProcessingJob:
    try:
        job = await get_processing_job_by_user_id(token, db, job_id)
        if not job:
            raise JobNotFoundException()
        return job
    except DispatcherException as de:
        raise de
    except Exception as e:
        logger.error(f"Error retrieving processing job {job_id}: {e}")
        raise InternalException(
            message="An error occurred while retrieving the processing job."
        )


@router.get(
    "/unit_jobs/{job_id}/results",
    tags=["Unit Jobs"],
    responses={
        JobNotFoundException.http_status: {
            "description": "Job not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": get_dispatcher_error_response(
                        JobNotFoundException(), "request-id"
                    )
                }
            },
        },
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
async def get_job_results(
    job_id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> Collection | None:
    try:
        result = await get_processing_job_results(token, db, job_id)
        if not result:
            raise JobNotFoundException()
        return result
    except DispatcherException as de:
        raise de
    except Exception as e:
        logger.error(f"Error getting results for processing job {job_id}: {e}")
        raise InternalException(
            message="An error occurred while retrieving processing job results."
        )
