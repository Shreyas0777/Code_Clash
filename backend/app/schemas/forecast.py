"""Forecast schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from .common import DataQualityWarning, ModelInfo, Period
from .energy import Reading


class ForecastRequest(BaseModel):
    meter_id: str = Field(min_length=1, max_length=128)
    readings: List[Reading] = Field(
        min_length=1,
        description=(
            "Historical hourly readings. At least 168 hours of coverage before "
            "the forecast timestamp are required for the trained feature set."
        ),
    )
    horizon_hours: int = Field(
        default=1,
        ge=1,
        description="Forecast horizon. The trained model supports next-hour only (1).",
    )


class ForecastResponse(BaseModel):
    meter_id: str
    forecast_timestamp: datetime = Field(description="Timestamp of the predicted hour")
    predicted_energy_kwh: float = Field(description="Predicted energy for the forecast hour, in kWh")
    horizon_hours: int
    unit: str = "kWh"
    prediction_type: str = Field(
        default="estimate",
        description="Always 'estimate' — model output, not a measurement",
    )
    model: ModelInfo
    input_period: Period
    warnings: List[DataQualityWarning] = Field(default_factory=list)
    interpretation_note: str = Field(
        description="Statement that the value is a model-generated estimate",
    )
