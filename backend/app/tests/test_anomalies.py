"""Tests: anomaly detection — label interpretation, scores, degradation."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from .conftest import ANOMALY_FEATURES, make_client


BASE = datetime(2026, 3, 2, 10, 0)  # 10:00, matched to training-time hour feature


def _payload(readings: list[dict]) -> dict:
    return {"meter_id": "m", "readings": readings}


def test_labels_and_scores_for_typical_vs_outlier(loaded_registry):
    """A far-out reading must be labeled -1/anomaly; a normal one 1/typical."""
    readings = [
        {"timestamp": BASE.isoformat(), "energy_kwh": 101.0},        # typical (training N(100,5))
        {"timestamp": (BASE + timedelta(hours=1)).isoformat(), "energy_kwh": 98.0},
        {"timestamp": (BASE + timedelta(hours=2)).isoformat(), "energy_kwh": 5000.0},  # outlier
    ]
    with make_client(registry=loaded_registry) as client:
        response = client.post("/api/v1/anomalies/detect", json=_payload(readings))
    assert response.status_code == 200
    body = response.json()

    by_value = {r["energy_kwh"]: r for r in body["results"]}
    assert by_value[5000.0]["model_output"] == -1
    assert by_value[5000.0]["label"] == "anomaly"
    assert by_value[101.0]["model_output"] == 1
    assert by_value[101.0]["label"] == "typical"

    # Score direction: more unusual ⇒ higher score (-score_samples).
    assert by_value[5000.0]["anomaly_score"] > by_value[101.0]["anomaly_score"]

    assert body["anomaly_count"] == 1
    assert body["model"]["version"] == "test_fixture_anomaly"
    assert "not a confirmed equipment fault" in body["interpretation"]
    assert "not" in body["interpretation"] and "waste" in body["interpretation"]


def test_score_equals_negated_score_samples(loaded_registry):
    """Score must match the documented formula: -score_samples(X)."""
    readings = [{"timestamp": BASE.isoformat(), "energy_kwh": 103.5}]
    with make_client(registry=loaded_registry) as client:
        body = client.post("/api/v1/anomalies/detect", json=_payload(readings)).json()

    entry = loaded_registry.get("anomaly")
    ts = pd.Timestamp(BASE)
    frame = pd.DataFrame(
        [
            {
                "energy_kwh": 103.5,
                "hour": ts.hour,
                "day_of_week": ts.dayofweek,
                "month": ts.month,
            }
        ],
        columns=ANOMALY_FEATURES,
    )
    expected = -float(entry.model.score_samples(frame)[0])
    assert abs(body["results"][0]["anomaly_score"] - expected) < 1e-9


def test_detect_sorts_and_deduplicates_like_training(loaded_registry):
    readings = [
        {"timestamp": (BASE + timedelta(hours=1)).isoformat(), "energy_kwh": 100.0},
        {"timestamp": BASE.isoformat(), "energy_kwh": 102.0},
        {"timestamp": BASE.isoformat(), "energy_kwh": 104.0},
    ]
    with make_client(registry=loaded_registry) as client:
        response = client.post("/api/v1/anomalies/detect", json=_payload(readings))
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2  # duplicate aggregated
    codes = {w["code"] for w in body["warnings"]}
    assert codes == {"readings_reordered", "duplicate_timestamps_aggregated"}


def test_detect_503_without_model(degraded_registry):
    readings = [{"timestamp": BASE.isoformat(), "energy_kwh": 100.0}]
    with make_client(registry=degraded_registry) as client:
        response = client.post("/api/v1/anomalies/detect", json=_payload(readings))
    assert response.status_code == 503
    assert response.json()["error"]["code"] in {
        "model_unavailable",
        "model_artifact_missing",
        "model_config_missing",
    }


def test_detect_validation_errors_same_contract(degraded_registry):
    with make_client(registry=degraded_registry) as client:
        response = client.post(
            "/api/v1/anomalies/detect",
            json={"meter_id": "m", "readings": [{"timestamp": BASE.isoformat(), "energy_kwh": -5}]},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


def test_shared_service_same_labels_as_energy_analyze(loaded_registry):
    """Both endpoints must agree (single shared inference path)."""
    readings = [
        {"timestamp": BASE.isoformat(), "energy_kwh": 5000.0},
        {"timestamp": (BASE + timedelta(hours=1)).isoformat(), "energy_kwh": 100.0},
    ]
    with make_client(registry=loaded_registry) as client:
        detect = client.post("/api/v1/anomalies/detect", json=_payload(readings)).json()
        analyze = client.post("/api/v1/energy/analyze", json=_payload(readings)).json()
    assert detect["anomaly_count"] == analyze["anomaly_count"]
    flagged = {r["energy_kwh"] for r in detect["results"] if r["model_output"] == -1}
    flagged_analyze = {r["energy_kwh"] for r in analyze["flagged_readings"]}
    assert flagged == flagged_analyze
