"""POST /scenarios/simulate — deterministic baseline-vs-intervention comparison."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.common import ErrorResponse
from ...schemas.scenario import ScenarioRequest, ScenarioResponse
from ...services import scenario_service

router = APIRouter(tags=["scenarios"])

RESPONSES = {
    400: {"model": ErrorResponse, "description": "Malformed JSON body"},
    413: {"model": ErrorResponse, "description": "Request body too large"},
    422: {"model": ErrorResponse, "description": "Invalid scenario parameters (out-of-range reduction, non-positive baseline, non-finite values)"},
}


@router.post(
    "/scenarios/simulate",
    response_model=ScenarioResponse,
    responses=RESPONSES,
    summary="Simulate an energy-saving intervention (deterministic projection)",
)
def simulate(payload: ScenarioRequest) -> ScenarioResponse:
    return scenario_service.simulate(payload)
