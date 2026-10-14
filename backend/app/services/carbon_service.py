"""Carbon emissions summary — transparent arithmetic with sourced factors.

``emissions_kg_co2 = energy_kwh × emission_factor_kg_co2_per_kwh``

The emission factor comes exclusively from environment configuration.  No
default factor is shipped: if none is configured the endpoint returns a clear
422 configuration error rather than an unsupported estimate.  A factor must
carry source, region and units (year / effective date when available).
"""

from __future__ import annotations

from typing import List

from ..core.config import CARBON_FACTOR_UNITS_SUPPORTED, Settings
from ..core.exceptions import ConfigurationError
from ..schemas.carbon import CarbonSummaryRequest, CarbonSummaryResponse, EmissionFactorInfo
from ..schemas.common import Period
from . import data_validation, statistics_service


def _require_factor(settings: Settings) -> EmissionFactorInfo:
    if settings.carbon_emission_factor is None:
        raise ConfigurationError(
            code="emission_factor_not_configured",
            message=(
                "No emission factor is configured for this deployment, so no "
                "carbon estimate can be produced. Set CARBON_EMISSION_FACTOR "
                "with CARBON_FACTOR_SOURCE, CARBON_FACTOR_REGION and "
                "CARBON_FACTOR_UNITS (see backend/.env.example)."
            ),
            details=[
                {
                    "field": "CARBON_EMISSION_FACTOR",
                    "message": "environment variable not set",
                    "type": "missing_configuration",
                }
            ],
        )
    if settings.carbon_emission_factor <= 0:
        raise ConfigurationError(
            code="invalid_emission_factor",
            message="CARBON_EMISSION_FACTOR must be a positive number.",
        )
    if settings.carbon_factor_units != CARBON_FACTOR_UNITS_SUPPORTED:
        raise ConfigurationError(
            code="unsupported_emission_factor_units",
            message=(
                f"CARBON_FACTOR_UNITS must be '{CARBON_FACTOR_UNITS_SUPPORTED}' "
                f"for this calculation; got "
                f"'{settings.carbon_factor_units}'. Unit conversion is not "
                "performed automatically."
            ),
        )
    missing = [
        name
        for name, value in (
            ("CARBON_FACTOR_SOURCE", settings.carbon_factor_source),
            ("CARBON_FACTOR_REGION", settings.carbon_factor_region),
        )
        if not value
    ]
    if missing:
        raise ConfigurationError(
            code="emission_factor_metadata_incomplete",
            message=(
                "The configured emission factor lacks required provenance: "
                + ", ".join(missing)
                + ". A factor must be accompanied by its source and region."
            ),
            details=[
                {"field": name, "message": "not configured", "type": "missing_configuration"}
                for name in missing
            ],
        )
    return EmissionFactorInfo(
        value=float(settings.carbon_emission_factor),
        units=settings.carbon_factor_units or CARBON_FACTOR_UNITS_SUPPORTED,
        source=str(settings.carbon_factor_source),
        region=str(settings.carbon_factor_region),
        year=settings.carbon_factor_year,
        effective_date=settings.carbon_factor_effective_date,
    )


def summarize(
    request: CarbonSummaryRequest,
    settings: Settings,
    max_readings: int,
) -> CarbonSummaryResponse:
    factor = _require_factor(settings)

    data_validation.check_readings_count(len(request.readings), max_readings)
    validated = data_validation.normalize_readings(request.readings)
    stats, start, end = statistics_service.compute_stats(
        validated.timestamps, validated.energy_kwh
    )

    emissions = stats.total_kwh * factor.value

    assumptions = [
        "All validated readings are attributed to operational electricity "
        "consumption for the stated period.",
        "A single flat emission factor is applied to the entire period; "
        "time-of-day or seasonal grid variation is not modeled.",
        "Emissions are operational (Scope 2 style) estimates, not verified "
        "or audited figures.",
    ]
    if factor.effective_date is None and factor.year is None:
        assumptions.append(
            "The configured factor carries no year/effective date; consider "
            "adding CARBON_FACTOR_YEAR or CARBON_FACTOR_EFFECTIVE_DATE."
        )

    provenance = (
        f"{factor.source} — region: {factor.region}, units: {factor.units}"
        + (f", year: {factor.year}" if factor.year else "")
        + (f", effective: {factor.effective_date}" if factor.effective_date else "")
    )

    warnings = list(validated.warnings)

    return CarbonSummaryResponse(
        meter_id=request.meter_id,
        period=Period(start=start, end=end),
        energy_total_kwh=stats.total_kwh,
        emission_factor=factor,
        emissions_kg_co2=emissions,
        calculation="emissions_kg_co2 = energy_kwh × emission_factor_kg_co2_per_kwh",
        assumptions=assumptions,
        provenance=provenance,
        warnings=warnings,
    )
