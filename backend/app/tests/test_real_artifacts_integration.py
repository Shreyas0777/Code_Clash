"""Real-model integration test suite.

Validates that the genuine Google Colab-trained model artifacts from the Building
Data Genome Project 2 (BDG2) are loaded, validated, and used for inference
with exact feature parity and numerical consistency.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from app.core.config import Settings
from app.schemas.energy import Reading
from app.services.anomaly_service import build_feature_frame
from app.services.forecast_service import predict_next_hour
from app.services.model_registry import ModelRegistry
from app.services.data_validation import normalize_readings

from .conftest import make_client

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = BACKEND_ROOT / "artifacts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "synthetic_artifacts"

EXPECTED_ANOMALY_SHA256 = "7dd68ffe830aaa9d83075c0fc61e567ba2507e1972897380aee2844efedc8f7f"
EXPECTED_FORECAST_SHA256 = "00e6bfe3d3d046b70f66ef3c18c5d0bf62d1b0d69c0ce1eee55af1ea7e7abc29"
EXPECTED_METER = "Robin_public_Carolina"
EXPECTED_DATASET = "Building Data Genome Project 2"


def _real_artifacts_present() -> bool:
    config_file = ARTIFACTS_DIR / "model_config.json"
    if not config_file.is_file():
        return False
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except Exception:
        return False
    if config.get("synthetic") is True:
        return False
    if config.get("selected_meter") != EXPECTED_METER:
        return False
    return (
        (ARTIFACTS_DIR / "anomaly_model.joblib").is_file()
        and (ARTIFACTS_DIR / "forecast_model.joblib").is_file()
    )


pytestmark = pytest.mark.skipif(
    not _real_artifacts_present(),
    reason="Genuine BDG2 model artifacts not present in backend/artifacts/ "
    "(install with: python scripts/install_artifacts.py <zip>)",
)


@pytest.fixture(scope="module")
def real_registry() -> ModelRegistry:
    registry = ModelRegistry(ARTIFACTS_DIR)
    registry.load()
    return registry


@pytest.fixture(scope="module")
def real_settings() -> Settings:
    return Settings(
        model_artifacts_dir=ARTIFACTS_DIR,
        carbon_emission_factor=0.713,
        carbon_factor_source="EPA eGRID 2024",
        carbon_factor_region="US-SERC",
        carbon_factor_year=2024,
    )


# --------------------------------------------------------------------------
# 1. Manifest and Artifact Integrity Tests
# --------------------------------------------------------------------------
def test_real_artifact_manifest_and_checksums(real_registry: ModelRegistry):
    """Verify that the genuine Colab-exported files exist and match known hashes."""
    assert (ARTIFACTS_DIR / "model_config.json").is_file()
    assert (ARTIFACTS_DIR / "forecast_metrics.json").is_file()
    assert (ARTIFACTS_DIR / "anomaly_model.joblib").is_file()
    assert (ARTIFACTS_DIR / "forecast_model.joblib").is_file()

    anomaly_entry = real_registry.get("anomaly")
    forecast_entry = real_registry.get("forecast")

    assert anomaly_entry.status == "loaded"
    assert forecast_entry.status == "loaded"

    assert anomaly_entry.metadata.get("sha256_full") == EXPECTED_ANOMALY_SHA256
    assert forecast_entry.metadata.get("sha256_full") == EXPECTED_FORECAST_SHA256

    assert real_registry.config["selected_meter"] == EXPECTED_METER
    assert real_registry.config["dataset"] == EXPECTED_DATASET
    assert real_registry.config.get("synthetic") is not True

    # Documented notebook evaluation metrics
    metrics = real_registry.metrics
    assert "model" in metrics and "baseline" in metrics
    assert abs(metrics["model"]["MAE"] - 5.34367) < 1e-4
    assert abs(metrics["model"]["RMSE"] - 7.94606) < 1e-4
    assert abs(metrics["model"]["R2"] - 0.96543) < 1e-4


# --------------------------------------------------------------------------
# 2. Readiness Endpoint with Real Artifacts
# --------------------------------------------------------------------------
def test_real_readiness_endpoint(real_settings: Settings, real_registry: ModelRegistry):
    with make_client(settings=real_settings, registry=real_registry) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["model_config_status"] == "loaded"
    assert body["notes"] == []  # No synthetic disclosure

    anomaly_info = body["models"]["anomaly"]
    forecast_info = body["models"]["forecast"]

    assert anomaly_info["status"] == "loaded"
    assert anomaly_info["model_class"] == "IsolationForest"
    assert anomaly_info["dataset"] == EXPECTED_DATASET
    assert anomaly_info["version"] == f"sha256-{EXPECTED_ANOMALY_SHA256[:12]}"

    assert forecast_info["status"] == "loaded"
    assert forecast_info["model_class"] == "HistGradientBoostingRegressor"
    assert forecast_info["dataset"] == EXPECTED_DATASET
    assert forecast_info["version"] == f"sha256-{EXPECTED_FORECAST_SHA256[:12]}"


# --------------------------------------------------------------------------
# 3. Anomaly Model Direct Inference vs API Parity
# --------------------------------------------------------------------------
def test_real_anomaly_direct_vs_api_parity(real_settings: Settings, real_registry: ModelRegistry):
    """Test that direct IsolationForest calls match /api/v1/anomalies/detect output."""
    entry = real_registry.anomaly_model_entry()
    estimator = entry.model

    # Construct test readings, including known row 15876 from notebook cell 14
    # (timestamp: 2017-10-23 12:00:00, energy_kwh: 223.876)
    timestamps = [
        "2017-10-23T11:00:00Z",
        "2017-10-23T12:00:00Z",  # cell 14 flagged anomaly
        "2017-10-23T13:00:00Z",  # cell 14 normal reading
        "2017-10-23T14:00:00Z",
    ]
    energies = [120.0, 223.876, 233.937, 125.0]

    raw_payload = [
        {"timestamp": ts, "energy_kwh": e}
        for ts, e in zip(timestamps, energies)
    ]

    # 1. Direct estimator inference using production feature builder
    reading_objs = [Reading(**item) for item in raw_payload]
    validated = normalize_readings(reading_objs)
    feature_frame = build_feature_frame(validated, entry.feature_names)

    direct_preds = estimator.predict(feature_frame)
    direct_scores = -estimator.score_samples(feature_frame)

    # Verify cell 14 row directly (row index 1 in our test)
    assert direct_preds[1] == -1
    assert abs(direct_scores[1] - 0.622164) < 1e-4

    # 2. API call
    with make_client(settings=real_settings, registry=real_registry) as client:
        response = client.post(
            "/api/v1/anomalies/detect",
            json={"meter_id": EXPECTED_METER, "readings": raw_payload},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["meter_id"] == EXPECTED_METER
    assert body["model"]["status"] == "loaded"
    assert body["model"]["dataset"] == EXPECTED_DATASET
    assert len(body["results"]) == len(raw_payload)

    # Compare each item
    for i, item in enumerate(body["results"]):
        assert item["model_output"] == int(direct_preds[i])
        expected_label = "anomaly" if direct_preds[i] == -1 else "typical"
        assert item["label"] == expected_label
        assert abs(item["anomaly_score"] - float(direct_scores[i])) < 1e-7

    # Verify cell 14 specific row via API response
    assert body["results"][1]["label"] == "anomaly"
    assert abs(body["results"][1]["anomaly_score"] - 0.622164) < 1e-4


# --------------------------------------------------------------------------
# 4. Forecast Model Direct Inference vs API Parity
# --------------------------------------------------------------------------
def test_real_forecast_direct_vs_api_parity(real_settings: Settings, real_registry: ModelRegistry):
    """Test that direct HistGradientBoostingRegressor calls match /api/v1/forecast output."""
    entry = real_registry.forecast_model_entry()

    # Build 170 consecutive hourly readings (exceeding 168 hours required)
    start_time = datetime(2017, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    readings = []
    # Use realistic hourly values around Robin_public_Carolina base range (~100 - 150 kWh)
    for i in range(170):
        t = start_time + timedelta(hours=i)
        # Synthetic diurnal cycle around realistic base
        val = 120.0 + 20.0 * np.sin(2 * np.pi * t.hour / 24.0) + (i % 5)
        readings.append({"timestamp": t.isoformat(), "energy_kwh": round(val, 3)})

    # 1. Direct prediction using forecast service logic
    reading_objs = [Reading(**item) for item in readings]
    validated = normalize_readings(reading_objs)
    outcome_direct = predict_next_hour(validated, entry, horizon_hours=1)
    direct_prediction = outcome_direct.predicted_energy_kwh

    assert np.isfinite(direct_prediction)
    assert direct_prediction > 0

    # 2. API call
    with make_client(settings=real_settings, registry=real_registry) as client:
        response = client.post(
            "/api/v1/forecast",
            json={
                "meter_id": EXPECTED_METER,
                "readings": readings,
                "horizon_hours": 1,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["meter_id"] == EXPECTED_METER
    assert body["horizon_hours"] == 1
    assert body["model"]["dataset"] == EXPECTED_DATASET
    assert body["model"]["status"] == "loaded"

    api_prediction = body["predicted_energy_kwh"]
    assert np.isfinite(api_prediction)

    # Direct model inference vs API comparison within tight numerical tolerance
    assert abs(api_prediction - direct_prediction) < 1e-9


# --------------------------------------------------------------------------
# 5. Energy Analysis Endpoint with Real Anomaly Model
# --------------------------------------------------------------------------
def test_real_energy_analyze_with_anomalies(real_settings: Settings, real_registry: ModelRegistry):
    timestamps = [
        "2017-10-23T11:00:00Z",
        "2017-10-23T12:00:00Z",  # cell 14 anomaly
        "2017-10-23T13:00:00Z",
    ]
    energies = [120.0, 223.876, 125.0]
    readings = [{"timestamp": ts, "energy_kwh": e} for ts, e in zip(timestamps, energies)]

    with make_client(settings=real_settings, registry=real_registry) as client:
        response = client.post(
            "/api/v1/energy/analyze",
            json={"meter_id": EXPECTED_METER, "readings": readings},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_provenance"] == EXPECTED_DATASET
    assert body["anomaly_model"]["status"] == "loaded"
    assert body["anomaly_count"] == 1
    assert len(body["flagged_readings"]) == 1
    assert body["flagged_readings"][0]["energy_kwh"] == 223.876
    assert abs(body["flagged_readings"][0]["anomaly_score"] - 0.622164) < 1e-4


# --------------------------------------------------------------------------
# 6. Insufficient History and Validation Errors
# --------------------------------------------------------------------------
def test_real_forecast_insufficient_history(real_settings: Settings, real_registry: ModelRegistry):
    """Must reject history < 168 hours with structured 422 error."""
    start_time = datetime(2017, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    short_readings = [
        {"timestamp": (start_time + timedelta(hours=i)).isoformat(), "energy_kwh": 120.0}
        for i in range(24)  # Only 24 hours
    ]

    with make_client(settings=real_settings, registry=real_registry) as client:
        response = client.post(
            "/api/v1/forecast",
            json={"meter_id": EXPECTED_METER, "readings": short_readings, "horizon_hours": 1},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "insufficient_history"


def test_real_forecast_unsupported_horizon(real_settings: Settings, real_registry: ModelRegistry):
    """Must reject horizon != 1."""
    start_time = datetime(2017, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    readings = [
        {"timestamp": (start_time + timedelta(hours=i)).isoformat(), "energy_kwh": 120.0}
        for i in range(170)
    ]

    with make_client(settings=real_settings, registry=real_registry) as client:
        response = client.post(
            "/api/v1/forecast",
            json={"meter_id": EXPECTED_METER, "readings": readings, "horizon_hours": 24},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "unsupported_forecast_horizon"
