"""Tests: carbon summary — known-factor math and configuration failures."""

from __future__ import annotations

from datetime import datetime, timedelta

from .conftest import make_client, make_settings

BASE = datetime(2026, 3, 2, 0, 0)

READINGS = [
    {"timestamp": BASE.isoformat(), "energy_kwh": 100.0},
    {"timestamp": (BASE + timedelta(hours=1)).isoformat(), "energy_kwh": 150.0},
    {"timestamp": (BASE + timedelta(hours=2)).isoformat(), "energy_kwh": 50.0},
]

CARBON_SETTINGS = dict(
    carbon_emission_factor=0.713,
    carbon_factor_source="TEST_FACTOR_DOCS Example Grid Factors 2024",
    carbon_factor_region="Test Region",
    carbon_factor_year=2024,
    carbon_factor_effective_date="2024-04-01",
)


def _payload() -> dict:
    return {"meter_id": "meter_demo_01", "readings": READINGS}


def test_carbon_math_with_known_factor():
    with make_client(settings=make_settings(**CARBON_SETTINGS)) as client:
        response = client.post("/api/v1/carbon/summary", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["energy_total_kwh"] == 300.0
    assert abs(body["emissions_kg_co2"] - (300.0 * 0.713)) < 1e-9
    assert body["emission_factor"]["value"] == 0.713
    assert body["emission_factor"]["units"] == "kg_CO2_per_kwh"
    assert body["emission_factor"]["source"] == "TEST_FACTOR_DOCS Example Grid Factors 2024"
    assert body["emission_factor"]["region"] == "Test Region"
    assert body["emission_factor"]["year"] == 2024
    assert body["emission_factor"]["effective_date"] == "2024-04-01"
    assert "×" in body["calculation"] or "*" in body["calculation"]
    assert "Test Region" in body["provenance"]
    assert body["assumptions"]
    assert body["period"]["start"] is not None


def test_carbon_factor_not_configured_returns_error():
    """No default factor is shipped — an unconfigured deployment refuses."""
    with make_client() as client:
        response = client.post("/api/v1/carbon/summary", json=_payload())
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "emission_factor_not_configured"
    assert "CARBON_EMISSION_FACTOR" in body["error"]["message"]


def test_carbon_missing_source_rejected():
    settings = make_settings(
        carbon_emission_factor=0.5,
        carbon_factor_region="Test Region",
        carbon_factor_source="",
    )
    with make_client(settings=settings) as client:
        response = client.post("/api/v1/carbon/summary", json=_payload())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "emission_factor_metadata_incomplete"


def test_carbon_unsupported_units_rejected():
    settings = make_settings(
        carbon_emission_factor=0.5,
        carbon_factor_source="Test source",
        carbon_factor_region="Test region",
        carbon_factor_units="lbs_per_mwh",
    )
    with make_client(settings=settings) as client:
        response = client.post("/api/v1/carbon/summary", json=_payload())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_emission_factor_units"


def test_carbon_invalid_factor_rejected():
    settings = make_settings(
        carbon_emission_factor=-1.0,
        carbon_factor_source="Test source",
        carbon_factor_region="Test region",
    )
    with make_client(settings=settings) as client:
        response = client.post("/api/v1/carbon/summary", json=_payload())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_emission_factor"


def test_carbon_invalid_readings_rejected():
    with make_client(settings=make_settings(**CARBON_SETTINGS)) as client:
        response = client.post(
            "/api/v1/carbon/summary",
            json={"meter_id": "m", "readings": [{"timestamp": BASE.isoformat(), "energy_kwh": -1}]},
        )
    assert response.status_code == 422
