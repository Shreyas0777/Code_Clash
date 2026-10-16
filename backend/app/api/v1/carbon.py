"""POST /carbon/summary — estimated operational emissions with factor provenance."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...schemas.carbon import CarbonSummaryRequest, CarbonSummaryResponse
from ...schemas.common import ErrorResponse
from ...services import carbon_service

router = APIRouter(tags=["carbon"])

RESPONSES = {
    400: {"model": ErrorResponse, "description": "Malformed JSON body"},
    413: {"model": ErrorResponse, "description": "Request body too large"},
    422: {
        "model": ErrorResponse,
        "description": "Validation failure, or emission factor not configured / missing provenance",
    },
}


@router.post(
    "/carbon/summary",
    response_model=CarbonSummaryResponse,
    responses=RESPONSES,
    summary="Estimate operational carbon emissions (configured factor required)",
)
def summary(request: Request, payload: CarbonSummaryRequest) -> CarbonSummaryResponse:
    settings = request.app.state.settings
    return carbon_service.summarize(
        payload,
        settings=settings,
        max_readings=settings.max_readings_per_request,
    )
