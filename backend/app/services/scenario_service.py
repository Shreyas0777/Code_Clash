"""Deterministic optimization-scenario simulator.

Pure arithmetic — independent of the ML models.  Results are projections
based on caller-supplied assumptions, never measured or verified savings.
"""

from __future__ import annotations

from typing import List

from ..schemas.scenario import ScenarioRequest, ScenarioResponse

SCENARIO_INTERPRETATION = (
    "These results are deterministic projections from the parameters you "
    "supplied. They are not measured, verified, or guaranteed savings."
)


def simulate(request: ScenarioRequest) -> ScenarioResponse:
    baseline = float(request.baseline_energy_kwh)
    reduction = float(request.reduction_percent)
    tariff = float(request.tariff_per_kwh)
    factor = float(request.emission_factor_kg_co2_per_kwh)

    projected = baseline * (1.0 - reduction / 100.0)
    savings_kwh = baseline - projected
    cost_savings = savings_kwh * tariff
    emissions_reduction = savings_kwh * factor

    assumptions: List[str] = [
        f"Baseline consumption of {baseline:g} kWh for the scenario period.",
        (
            f"The intervention reduces consumption by {reduction:g}% uniformly; "
            "no rebound, degradation, or implementation-cost effects are modeled."
        ),
        f"Electricity tariff held constant at {tariff:g} {request.currency}/kWh.",
        (
            f"Emission factor held constant at {factor:g} kg CO2/kWh"
            + (
                f" (source: {request.emission_factor_source})"
                if request.emission_factor_source
                else " (caller-supplied assumption; no source provided)"
            )
            + "."
        ),
        "Savings are projections for planning comparison only.",
    ]

    return ScenarioResponse(
        scenario_name=request.scenario_name,
        intervention_description=request.intervention_description,
        baseline_energy_kwh=baseline,
        reduction_percent=reduction,
        projected_energy_kwh=projected,
        energy_savings_kwh=savings_kwh,
        tariff_per_kwh=tariff,
        currency=request.currency,
        cost_savings=cost_savings,
        emission_factor_kg_co2_per_kwh=factor,
        emissions_reduction_kg_co2=emissions_reduction,
        assumptions=assumptions,
        parameters=request,
        interpretation_note=SCENARIO_INTERPRETATION,
    )
