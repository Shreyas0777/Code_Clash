"""Tests: optimization scenario simulator — deterministic math + validation."""

from __future__ import annotations

import pytest

from .conftest import make_client

BASE_SCENARIO = {
    "scenario_name": "led_retrofit",
    "intervention_description": "LED lighting retrofit in common areas",
    "baseline_energy_kwh": 1000.0,
    "reduction_percent": 15.0,
    "tariff_per_kwh": 8.5,
    "currency": "INR",
    "emission_factor_kg_co2_per_kwh": 0.7,
    "emission_factor_source": "caller-supplied assumption for planning",
}


def _post(client, **overrides):
    payload = {**BASE_SCENARIO, **overrides}
    return client.post("/api/v1/scenarios/simulate", json=payload)


def test_deterministic_example_exact_values():
    with make_client() as client:
        response = _post(client)
    assert response.status_code == 200
    body = response.json()
    assert body["projected_energy_kwh"] == 850.0
    assert body["energy_savings_kwh"] == 150.0
    assert body["cost_savings"] == 1275.0        # 150 * 8.5
    assert body["emissions_reduction_kg_co2"] == 105.0  # 150 * 0.7
    assert body["baseline_energy_kwh"] == 1000.0
    assert body["reduction_percent"] == 15.0
    assert body["currency"] == "INR"
    assert body["parameters"] == BASE_SCENARIO


def test_zero_reduction_yields_zero_savings():
    with make_client() as client:
        body = _post(client, reduction_percent=0).json()
    assert body["projected_energy_kwh"] == 1000.0
    assert body["energy_savings_kwh"] == 0.0
    assert body["cost_savings"] == 0.0
    assert body["emissions_reduction_kg_co2"] == 0.0


def test_full_reduction_projects_zero_energy():
    with make_client() as client:
        body = _post(client, reduction_percent=100).json()
    assert body["projected_energy_kwh"] == 0.0
    assert body["energy_savings_kwh"] == 1000.0


def test_results_are_labeled_projections_not_measurements():
    with make_client() as client:
        body = _post(client).json()
    note = body["interpretation_note"].lower()
    assert "not measured" in note
    assert "projection" in note
    assert any("projections" in a.lower() for a in body["assumptions"])


@pytest.mark.parametrize(
    "overrides",
    [
        {"reduction_percent": 150.0},      # above 100
        {"reduction_percent": -5.0},       # negative
        {"baseline_energy_kwh": 0.0},      # non-positive baseline
        {"baseline_energy_kwh": -100.0},
        {"tariff_per_kwh": -1.0},          # negative tariff
        {"emission_factor_kg_co2_per_kwh": 0.0},  # non-positive factor
        {"emission_factor_kg_co2_per_kwh": -0.5},
        {"currency": None},                # missing required field
    ],
    ids=[
        "reduction_over_100",
        "reduction_negative",
        "baseline_zero",
        "baseline_negative",
        "tariff_negative",
        "factor_zero",
        "factor_negative",
        "currency_missing",
    ],
)
def test_invalid_parameters_rejected(overrides):
    with make_client() as client:
        payload = {**BASE_SCENARIO, **overrides}
        if overrides.get("currency") is None:
            payload.pop("currency", None)
        response = client.post("/api/v1/scenarios/simulate", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] in {
        "request_validation_error",
        "invalid_json",
    }


def test_non_finite_parameters_rejected():
    """NaN / Infinity literals in the raw body must fail validation (422)."""
    import json as _json

    for bad_value in ("NaN", "Infinity"):
        payload = {**BASE_SCENARIO, "tariff_per_kwh": bad_value}
        body = _json.dumps(payload)  # strings survive serialization verbatim
        with make_client() as client:
            response = client.post(
                "/api/v1/scenarios/simulate",
                content=body,
                headers={"content-type": "application/json"},
            )
        assert response.status_code == 422, bad_value
        assert response.json()["error"]["code"] == "request_validation_error"


def test_scenario_missing_required_field_rejected():
    with make_client() as client:
        payload = dict(BASE_SCENARIO)
        payload.pop("emission_factor_kg_co2_per_kwh")
        response = client.post("/api/v1/scenarios/simulate", json=payload)
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert any(d["field"] == "emission_factor_kg_co2_per_kwh" for d in details)


def test_scenario_without_factor_source_still_documents_assumption():
    payload = dict(BASE_SCENARIO)
    payload.pop("emission_factor_source")
    with make_client() as client:
        response = client.post("/api/v1/scenarios/simulate", json=payload)
    assert response.status_code == 200
    assumptions = " ".join(response.json()["assumptions"])
    assert "no source provided" in assumptions
