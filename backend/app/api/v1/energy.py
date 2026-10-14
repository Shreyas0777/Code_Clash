"""POST /energy/analyze — validated readings → statistics + anomaly flags."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...schemas.common import ErrorResponse
from ...schemas.energy import EnergyAnalyzeRequest, EnergyAnalyzeResponse
from ...services import energy_service

router = APIRouter(tags=["energy"])

RESPONSES = {
    400: {"model": ErrorResponse, "description": "Malformed JSON body"},
    413: {"model": ErrorResponse, "description": "Request body too large"},
    422: {"model": ErrorResponse, "description": "Validation failure (NaN/inf/negative values, bad timestamps, too many readings, mixed timezones)"},
}


@router.post(
    "/energy/analyze",
    response_model=EnergyAnalyzeResponse,
    responses=RESPONSES,
    summary="Analyze energy readings (statistics + anomaly flags when available)",
)
def analyze(request: Request, payload: EnergyAnalyzeRequest) -> EnergyAnalyzeResponse:
    settings = request.app.state.settings
    registry = request.app.state.registry
    return energy_service.analyze(
        payload,
        registry=registry,
        max_readings=settings.max_readings_per_request,
    )
