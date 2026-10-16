"""POST /anomalies/detect — anomaly labels + relative scores for readings.

Shares inference logic with /energy/analyze via ``anomaly_service``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...schemas.anomaly import AnomaliesDetectRequest, AnomaliesDetectResponse
from ...schemas.common import ErrorResponse, ModelInfo
from ...services import anomaly_service, data_validation

router = APIRouter(tags=["anomalies"])

RESPONSES = {
    400: {"model": ErrorResponse, "description": "Malformed JSON body"},
    413: {"model": ErrorResponse, "description": "Request body too large"},
    422: {"model": ErrorResponse, "description": "Validation failure"},
    503: {"model": ErrorResponse, "description": "Anomaly model artifact unavailable (see /api/v1/ready)"},
}


@router.post(
    "/anomalies/detect",
    response_model=AnomaliesDetectResponse,
    responses=RESPONSES,
    summary="Detect unusual readings (IsolationForest labels + relative scores)",
)
def detect(request: Request, payload: AnomaliesDetectRequest) -> AnomaliesDetectResponse:
    settings = request.app.state.settings
    registry = request.app.state.registry
    entry = registry.anomaly_model_entry()  # raises 503 when unavailable

    data_validation.check_readings_count(len(payload.readings), settings.max_readings_per_request)
    validated = data_validation.normalize_readings(payload.readings)
    results = anomaly_service.detect(validated, entry)

    return AnomaliesDetectResponse(
        meter_id=payload.meter_id,
        model=ModelInfo(
            name="anomaly",
            status="loaded",
            version=entry.version,
            dataset=entry.dataset,
        ),
        results=results,
        anomaly_count=sum(1 for r in results if r.model_output == -1),
        warnings=list(validated.warnings),
        interpretation=anomaly_service.ANOMALY_INTERPRETATION,
    )
