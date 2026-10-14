"""Tests: energy analysis — validation, stats, warnings, graceful degradation."""

from __future__ import annotations

from datetime import datetime, timedelta

from .conftest import make_client, make_settings, synthetic_hourly_readings


def _reading(ts: datetime, value: float) -> dict:
    return {"timestamp": ts.isoformat(), "energy_kwh": value}


BASE = datetime(2026, 3, 2, 0, 0)  # naive (assumed UTC)


def test_valid_payload_statistics_exact():
    payload = {
        "meter_id": "meter_demo_01",
        "readings": [
            _reading(BASE, 10.0),
            _reading(BASE + timedelta(hours=1), 20.0),
            _reading(BASE + timedelta(hours=2), 30.0),
        ],
    }
    with make_client() as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["meter_id"] == "meter_demo_01"
    assert body["valid_readings"] == 3
    assert body["stats"] == {
        "count": 3,
        "mean_kwh": 20.0,
        "min_kwh": 10.0,
        "max_kwh": 30.0,
        "total_kwh": 60.0,
    }
    assert body["period"]["start"] == "2026-03-02T00:00:00"
    assert body["period"]["end"] == "2026-03-02T02:00:00"
    # No *data-quality* warnings; the only warning is the honest
    # model-unavailable notice (default registry has no models loaded).
    assert [w["code"] for w in body["warnings"]] == ["anomaly_model_unavailable"]


def test_analyze_degrades_without_anomaly_model(degraded_registry):
    payload = {
        "meter_id": "m",
        "readings": [_reading(BASE, 42.0)],
    }
    with make_client(registry=degraded_registry) as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    # Statistics still returned...
    assert body["stats"]["mean_kwh"] == 42.0
    # ...but anomaly fields are honestly null, with an explicit warning.
    assert body["anomaly_count"] is None
    assert body["flagged_readings"] is None
    assert body["anomaly_model"]["status"] == "unavailable"
    assert any(w["code"] == "anomaly_model_unavailable" for w in body["warnings"])
    assert body["anomaly_interpretation"] is None


def test_analyze_with_model_reports_anomalies_and_provenance(loaded_registry):
    readings = synthetic_hourly_readings(hours=48)
    readings.append({"timestamp": "2026-01-07T00:00:00Z", "energy_kwh": 99999.0})
    payload = {"meter_id": "m", "readings": readings}
    with make_client(registry=loaded_registry) as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["anomaly_count"] is not None
    assert isinstance(body["flagged_readings"], list)
    assert body["anomaly_model"]["status"] == "loaded"
    assert body["anomaly_model"]["version"] == "test_fixture_anomaly"
    assert body["dataset_provenance"] == "SYNTHETIC_TEST_FIXTURE_NOT_BDG2"
    assert "not a confirmed equipment fault" in body["anomaly_interpretation"]


def test_duplicate_timestamps_aggregated_with_warning():
    payload = {
        "meter_id": "m",
        "readings": [
            _reading(BASE, 10.0),
            _reading(BASE, 20.0),
            _reading(BASE + timedelta(hours=1), 30.0),
        ],
    }
    with make_client() as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    # Duplicate aggregated to (10+20)/2 = 15, then [15, 30].
    assert body["valid_readings"] == 2
    assert body["stats"]["mean_kwh"] == 22.5
    assert body["stats"]["total_kwh"] == 45.0
    warnings = {w["code"]: w for w in body["warnings"]}
    assert "duplicate_timestamps_aggregated" in warnings
    assert warnings["duplicate_timestamps_aggregated"]["count"] == 1


def test_out_of_order_readings_sorted_with_warning():
    payload = {
        "meter_id": "m",
        "readings": [
            _reading(BASE + timedelta(hours=2), 30.0),
            _reading(BASE, 10.0),
            _reading(BASE + timedelta(hours=1), 20.0),
        ],
    }
    with make_client() as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["period"]["start"] == "2026-03-02T00:00:00"
    assert body["period"]["end"] == "2026-03-02T02:00:00"
    assert any(w["code"] == "readings_reordered" for w in body["warnings"])


def test_negative_energy_rejected():
    payload = {
        "meter_id": "m",
        "readings": [_reading(BASE, -1.0)],
    }
    with make_client() as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request_validation_error"
    assert any("energy_kwh" in (d["field"] or "") for d in body["error"]["details"])


def test_nan_energy_rejected():
    # Raw body: strict JSON clients refuse NaN, but permissive parsers accept
    # the literal — the API must still reject it with 422.
    body = f'{{"meter_id": "m", "readings": [{{"timestamp": "{BASE.isoformat()}", "energy_kwh": NaN}}]}}'
    with make_client() as client:
        response = client.post(
            "/api/v1/energy/analyze",
            content=body,
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


def test_infinite_energy_rejected():
    body = f'{{"meter_id": "m", "readings": [{{"timestamp": "{BASE.isoformat()}", "energy_kwh": Infinity}}]}}'
    with make_client() as client:
        response = client.post(
            "/api/v1/energy/analyze",
            content=body,
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


def test_invalid_timestamp_rejected():
    payload = {"meter_id": "m", "readings": [{"timestamp": "not-a-timestamp", "energy_kwh": 1.0}]}
    with make_client() as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


def test_empty_readings_rejected():
    with make_client() as client:
        response = client.post("/api/v1/energy/analyze", json={"meter_id": "m", "readings": []})
    assert response.status_code == 422


def test_missing_field_rejected_with_detail():
    with make_client() as client:
        response = client.post(
            "/api/v1/energy/analyze",
            json={"readings": [{"timestamp": BASE.isoformat(), "energy_kwh": 1.0}]},
        )
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert any(d["field"] == "meter_id" for d in details)


def test_mixed_timezone_timestamps_rejected():
    payload = {
        "meter_id": "m",
        "readings": [
            {"timestamp": "2026-03-02T00:00:00Z", "energy_kwh": 1.0},
            {"timestamp": "2026-03-02T01:00:00", "energy_kwh": 2.0},
        ],
    }
    with make_client() as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mixed_timestamp_timezones"


def test_too_many_readings_rejected():
    settings = make_settings(max_readings_per_request=5)
    payload = {
        "meter_id": "m",
        "readings": [
            {"timestamp": (BASE + timedelta(hours=i)).isoformat(), "energy_kwh": 1.0}
            for i in range(10)
        ],
    }
    with make_client(settings=settings) as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "too_many_readings"


def test_aware_and_naive_consistent_accepted():
    payload = {
        "meter_id": "m",
        "readings": [
            {"timestamp": "2026-03-02T00:00:00+05:30", "energy_kwh": 10.0},
            {"timestamp": "2026-03-02T01:00:00+05:30", "energy_kwh": 20.0},
        ],
    }
    with make_client() as client:
        response = client.post("/api/v1/energy/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    # Converted to UTC (documented normalization).
    assert body["period"]["start"] == "2026-03-01T18:30:00"
    assert body["stats"]["total_kwh"] == 30.0
