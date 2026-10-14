"""Optimization scenario schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ScenarioRequest(BaseModel):
    """A hypothetical energy-saving intervention compared to a baseline.

    All parameters are explicit assumptions supplied by the caller; the
    calculation is deterministic arithmetic, independent of any ML model.
    """

    scenario_name: str = Field(default="energy_saving_scenario", min_length=1, max_length=128)
    intervention_description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Free-text description of the hypothetical intervention",
    )
    baseline_energy_kwh: float = Field(
        gt=0,
        allow_inf_nan=False,
        description="Baseline energy consumption for the period (kWh, > 0)",
    )
    reduction_percent: float = Field(
        ge=0,
        le=100,
        allow_inf_nan=False,
        description="Assumed percentage reduction from the intervention (0-100)",
    )
    tariff_per_kwh: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Electricity tariff per kWh (> 0 recommended; 0 allowed)",
    )
    currency: str = Field(
        min_length=1,
        max_length=16,
        description="Currency code for cost figures (e.g. INR, USD) — caller-supplied",
    )
    emission_factor_kg_co2_per_kwh: float = Field(
        gt=0,
        allow_inf_nan=False,
        description="Assumed emission factor (kg CO2 / kWh) — caller-supplied",
    )
    emission_factor_source: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Documented source for the assumed emission factor, when known",
    )


class ScenarioResponse(BaseModel):
    scenario_name: str
    intervention_description: Optional[str] = None
    baseline_energy_kwh: float
    reduction_percent: float
    projected_energy_kwh: float
    energy_savings_kwh: float
    tariff_per_kwh: float
    currency: str
    cost_savings: float
    emission_factor_kg_co2_per_kwh: float
    emissions_reduction_kg_co2: float
    calculation_period: str = Field(
        default="single scenario period (caller-defined)",
        description="Scenarios are period-agnostic; the baseline defines the period",
    )
    assumptions: List[str] = Field(default_factory=list)
    parameters: ScenarioRequest
    interpretation_note: str = Field(
        description="Statement that results are projections, not measured savings",
    )
