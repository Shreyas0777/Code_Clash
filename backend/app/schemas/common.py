"""Shared response building blocks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class DataQualityWarning(BaseModel):
    """A documented data-quality event; never applied silently."""

    code: str = Field(description="Stable machine-readable warning code")
    message: str
    count: Optional[int] = Field(
        default=None,
        description="Number of affected readings/hours, when meaningful",
    )


class Period(BaseModel):
    start: Optional[datetime] = Field(default=None, description="First timestamp analyzed")
    end: Optional[datetime] = Field(default=None, description="Last timestamp analyzed")


class ModelInfo(BaseModel):
    """Model version + availability surfaced in API responses."""

    name: str
    status: Literal["loaded", "unavailable", "error", "feature_mismatch", "config_missing"]
    version: Optional[str] = Field(
        default=None,
        description="Content hash of the artifact file (sha256-<12 hex>) or an explicit fixture label",
    )
    dataset: Optional[str] = Field(
        default=None,
        description="Training dataset label from model_config.json, when available",
    )


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str
    type: Optional[str] = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: List[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Standard error envelope used by every non-2xx response."""

    error: ErrorBody


@dataclass
class ValidatedReadings:
    """Normalized readings shared across services.

    ``timestamps`` and ``energy_kwh`` are aligned, sorted ascending,
    duplicate-timestamp aggregated.  Timestamps are naive and assumed UTC
    (documented rule).
    """

    timestamps: List[datetime]
    energy_kwh: List[float]
    warnings: List[DataQualityWarning]
