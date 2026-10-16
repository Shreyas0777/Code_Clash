"""Energy analysis orchestration.

Shared validation/normalization and statistics; anomaly inference is
delegated to the shared ``anomaly_service`` and degrades gracefully (fields
``null`` + explicit warning/status) when the anomaly model is unavailable —
``/energy/analyze`` must still return statistics in that case.
"""

from __future__ import annotations

from typing import List, Optional

from ..schemas.common import DataQualityWarning, ModelInfo, Period
from ..schemas.energy import EnergyAnalyzeRequest, EnergyAnalyzeResponse, FlaggedReading
from . import anomaly_service, data_validation, statistics_service
from .model_registry import ModelEntry, ModelRegistry

NO_MODEL_INFO = ModelInfo(name="anomaly", status="unavailable")


def analyze(
    request: EnergyAnalyzeRequest,
    registry: ModelRegistry,
    max_readings: int,
) -> EnergyAnalyzeResponse:
    data_validation.check_readings_count(len(request.readings), max_readings)
    validated = data_validation.normalize_readings(request.readings)
    stats, start, end = statistics_service.compute_stats(
        validated.timestamps, validated.energy_kwh
    )

    warnings: List[DataQualityWarning] = list(validated.warnings)
    dataset_provenance: Optional[str] = None
    if registry.config_status == "loaded":
        dataset = registry.config.get("dataset")
        if isinstance(dataset, str) and dataset:
            dataset_provenance = dataset

    anomaly_count: Optional[int] = None
    flagged: Optional[List[FlaggedReading]] = None
    interpretation: Optional[str] = None

    entry: Optional[ModelEntry] = registry.get("anomaly")
    if entry.available:
        results = anomaly_service.detect(validated, entry)
        anomaly_count = sum(1 for r in results if r.model_output == -1)
        flagged = [
            FlaggedReading(
                timestamp=r.timestamp,
                energy_kwh=r.energy_kwh,
                anomaly_score=r.anomaly_score,
            )
            for r in results
            if r.model_output == -1
        ]
        interpretation = anomaly_service.ANOMALY_INTERPRETATION
        model_info = ModelInfo(
            name="anomaly",
            status="loaded",
            version=entry.version,
            dataset=entry.dataset,
        )
    else:
        warnings.append(
            DataQualityWarning(
                code="anomaly_model_unavailable",
                message=(
                    "The anomaly model is not available; anomaly_count and "
                    "flagged_readings are null. Statistics are unaffected. "
                    "See GET /api/v1/ready."
                ),
            )
        )
        model_info = NO_MODEL_INFO

    return EnergyAnalyzeResponse(
        meter_id=request.meter_id,
        period=Period(start=start, end=end),
        valid_readings=stats.count,
        stats=stats,
        anomaly_count=anomaly_count,
        flagged_readings=flagged,
        warnings=warnings,
        dataset_provenance=dataset_provenance,
        anomaly_model=model_info,
        anomaly_interpretation=interpretation,
    )
