"""POST /forecast — next-hour energy estimate from historical readings."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...schemas.common import ErrorResponse, ModelInfo
from ...schemas.forecast import ForecastRequest, ForecastResponse
from ...services import forecast_service

router = APIRouter(tags=["forecast"])

RESPONSES = {
    400: {"model": ErrorResponse, "description": "Malformed JSON body"},
    413: {"model": ErrorResponse, "description": "Request body too large"},
    422: {"model": ErrorResponse, "description": "Validation failure, unsupported horizon (horizon_hours != 1), or insufficient history"},
    503: {"model": ErrorResponse, "description": "Forecast model artifact unavailable (see /api/v1/ready)"},
}


@router.post(
    "/forecast",
    response_model=ForecastResponse,
    responses=RESPONSES,
    summary="Next-hour energy forecast (single-step model, estimates only)",
)
def forecast(request: Request, payload: ForecastRequest) -> ForecastResponse:
    settings = request.app.state.settings
    registry = request.app.state.registry
    entry = registry.forecast_model_entry()  # raises 503 when unavailable

    outcome = forecast_service.forecast_from_raw(
        payload.readings,
        entry=entry,
        horizon_hours=payload.horizon_hours,
        max_readings=settings.max_readings_per_request,
    )

    return ForecastResponse(
        meter_id=payload.meter_id,
        forecast_timestamp=outcome.forecast_timestamp,
        predicted_energy_kwh=outcome.predicted_energy_kwh,
        horizon_hours=outcome.horizon_hours,
        model=ModelInfo(
            name="forecast",
            status="loaded",
            version=entry.version,
            dataset=entry.dataset,
        ),
        input_period={"start": outcome.input_period_start, "end": outcome.input_period_end},
        warnings=outcome.warnings,
        interpretation_note=forecast_service.FORECAST_INTERPRETATION,
    )
