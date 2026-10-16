"""Anomaly detection schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field

from .common import DataQualityWarning, ModelInfo
from .energy import EnergyAnalyzeRequest


# Reuses the energy request shape: same readings, same validation rules.
AnomaliesDetectRequest = EnergyAnalyzeRequest


class AnomalyResult(BaseModel):
    timestamp: datetime
    energy_kwh: float
    label: Literal["anomaly", "typical"] = Field(
        description="'anomaly' when the model returned -1, 'typical' when it returned 1"
    )
    model_output: int = Field(description="Raw IsolationForest output: -1 (anomaly) or 1 (typical)")
    anomaly_score: float = Field(
        description=(
            "Relative anomaly score = -score_samples(). Higher = more unusual. "
            "Not a calibrated probability."
        )
    )


class AnomaliesDetectResponse(BaseModel):
    meter_id: str
    model: ModelInfo
    results: List[AnomalyResult]
    anomaly_count: int
    warnings: List[DataQualityWarning] = Field(default_factory=list)
    interpretation: str = Field(
        description="Caveat: flags indicate unusual readings, not confirmed faults"
    )
