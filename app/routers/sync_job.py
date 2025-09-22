from typing import Annotated, Any
from fastapi import Body, APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas.enum import OutputFormatEnum, ProcessTypeEnum
from app.schemas.unit_job import (
    BaseJobRequest,
    ProcessingJob,
    ProcessingJobSummary,
    ServiceDetails,
)
from app.services.processing import (
    create_processing_job,
    create_synchronous_job,
    get_processing_job_by_user_id,
    get_processing_job_results,
)

from stac_pydantic import Collection

# from app.auth import get_current_user

router = APIRouter()


@router.post(
    "/sync_jobs",
    status_code=status.HTTP_201_CREATED,
    tags=["Unit Jobs"],
    summary="Create a new processing job",
)
async def create_sync_job(
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
    user: str = "ge-poc",
) -> Any:
    """Initiate a synchronous processing job with the provided data and return the result."""
    try:
        return create_synchronous_job(user, payload)
    except Exception as e:
        logger.exception(f"Error creating synchronous job for user {user}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the synchronous job: {e}",
        )
