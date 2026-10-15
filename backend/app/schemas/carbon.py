"""Carbon summary schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from .common import DataQualityWarning, Period
from .energy import Reading


class CarbonSummaryRequest(BaseModel):
    meter_id: str = Field(min_length=1, max_length=128)
    readings: List[Reading] = Field(min_length=1)


class EmissionFactorInfo(BaseModel):
    value: float = Field(description="Emission factor in kg CO2 per kWh")
    units: str = "kg_CO2_per_kwh"
    source: str = Field(description="Documented source of the factor")
    region: str = Field(description="Grid region the factor applies to")
    year: Optional[int] = None
    effective_date: Optional[str] = None


class CarbonSummaryResponse(BaseModel):
    meter_id: str
    period: Period
    energy_total_kwh: float
    emission_factor: EmissionFactorInfo
    emissions_kg_co2: float = Field(
        description="energy_kwh x emission_factor_kg_co2_per_kwh (kg CO2)"
    )
    calculation: str = Field(description="Formula actually applied")
    assumptions: List[str] = Field(default_factory=list)
    provenance: str = Field(description="Where the emission factor came from")
    warnings: List[DataQualityWarning] = Field(default_factory=list)
