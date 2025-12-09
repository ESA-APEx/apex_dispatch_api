from typing import Annotated, List
from fastapi import Body, APIRouter, Depends, HTTPException, Response, status
from loguru import logger

from app.schemas.enum import ProcessTypeEnum
from app.schemas.parameters import ParamRequest, Parameter
from app.schemas.unit_job import (
    ServiceDetails,
)
from app.auth import oauth2_scheme
from app.services.processing import retrieve_service_parameters


# from app.auth import get_current_user

router = APIRouter()


@router.post(
    "/params",
    status_code=status.HTTP_200_OK,
    tags=["Unit Jobs"],
    summary="Get the parameters of a specific processing service.",
)
async def get_job_params(
    payload: Annotated[
        ParamRequest,
        Body(
            openapi_examples={
                "openEO Example": {
                    "summary": "Retrieving the parameters for an openEO-based service",
                    "description": "The following example demonstrates how to retrieve the "
                    "parameters for a processing job using an openEO-based service.",
                    "value": ParamRequest(
                        label=ProcessTypeEnum.OPENEO,
                        service=ServiceDetails(
                            endpoint="https://openeofed.dataspace.copernicus.eu",
                            application="https://raw.githubusercontent.com/ESA-APEx/apex_algorithms"
                            "/32ea3c9a6fa24fe063cb59164cd318cceb7209b0/openeo_udp/variabilitymap/"
                            "variabilitymap.json",
                        ),
                    ).model_dump(),
                }
            },
        ),
    ],
    token: str = Depends(oauth2_scheme),
) -> List[Parameter]:
    """Retrieve the parameters required for a specific processing service."""
    try:
        return await retrieve_service_parameters(token, payload)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Error retrieving service parameters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving service parameters: {e}",
        )
