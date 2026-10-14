"""Energy analysis schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .common import DataQualityWarning, ModelInfo, Period


class Reading(BaseModel):
    """A single meter reading.

    Validation: ``energy_kwh`` must be a finite number >= 0 (NaN, infinity and
    negative values are rejected with 422).  Timestamps are ISO-8601; naive
    timestamps are interpreted as UTC (documented rule).
    """

    timestamp: datetime = Field(description="ISO-8601 timestamp; naive values assumed UTC")
    energy_kwh: float = Field(
        allow_inf_nan=False,
        ge=0,
        description="Energy consumption for the hour in kWh (>= 0, finite)",
    )


class EnergyAnalyzeRequest(BaseModel):
    meter_id: str = Field(min_length=1, max_length=128)
    readings: List[Reading] = Field(min_length=1)


class EnergyStats(BaseModel):
    count: int = Field(description="Number of valid readings included")
    mean_kwh: float
    min_kwh: float
    max_kwh: float
    total_kwh: float


class FlaggedReading(BaseModel):
    timestamp: datetime
    energy_kwh: float
    anomaly_score: Optional[float] = Field(
        default=None,
        description="Relative anomaly score (higher = more unusual). Not a calibrated probability.",
    )


class EnergyAnalyzeResponse(BaseModel):
    meter_id: str
    period: Period
    valid_readings: int
    stats: EnergyStats
    anomaly_count: Optional[int] = Field(
        default=None,
        description="Number of flagged readings; null when the anomaly model is unavailable",
    )
    flagged_readings: Optional[List[FlaggedReading]] = None
    warnings: List[DataQualityWarning] = Field(default_factory=list)
    dataset_provenance: Optional[str] = Field(
        default=None,
        description="Training dataset label from model_config.json, when artifacts are loaded",
    )
    anomaly_model: ModelInfo
    anomaly_interpretation: Optional[str] = Field(
        default=None,
        description="Caveat attached whenever anomaly flags are returned",
    )
