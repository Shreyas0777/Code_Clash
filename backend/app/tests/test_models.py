"""Tests: model registry initialization, validation, and failure modes."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pytest

from app.core.exceptions import ModelUnavailableError
from app.services.model_registry import ModelRegistry

from .conftest import (
    ANOMALY_FEATURES,
    FORECAST_FEATURES,
    make_client,
    make_settings,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = BACKEND_ROOT / "artifacts"
REAL_ARTIFACT_FILES = ("anomaly_model.joblib", "forecast_model.joblib", "model_config.json")


def _real_artifacts_present() -> bool:
    """True only for a genuine export — SYNTHETIC demo files don't count."""
    if not all((ARTIFACTS_DIR / name).is_file() for name in REAL_ARTIFACT_FILES):
        return False
    try:
        config = json.loads((ARTIFACTS_DIR / "model_config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if config.get("synthetic") is True:
        return False
    return not str(config.get("artifact_source", "")).startswith("synthetic")


REAL_ARTIFACTS_PRESENT = _real_artifacts_present()

BASE_CONFIG = {
    "project": "Fluxora",
    "dataset": "Building Data Genome Project 2",
    "forecast_features": FORECAST_FEATURES,
    "anomaly_features": ANOMALY_FEATURES,
}


def _write_config(directory: Path, config: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "model_config.json").write_text(json.dumps(config), encoding="utf-8")


def test_registry_load_on_empty_directory_does_not_raise(tmp_path):
    registry = ModelRegistry(tmp_path / "does_not_exist")
    registry.load()  # must never raise
    assert registry.config_status == "missing"
    assert registry.all_models_loaded is False
    assert registry.get("anomaly").error_code == "model_config_missing"
    assert registry.get("forecast").error_code == "model_config_missing"


def test_registry_config_present_but_artifacts_missing(tmp_path):
    _write_config(tmp_path, BASE_CONFIG)
    registry = ModelRegistry(tmp_path)
    registry.load()
    assert registry.config_status == "loaded"
    for name in ("anomaly", "forecast"):
        entry = registry.get(name)
        assert entry.status == "missing"
        assert entry.error_code == "model_artifact_missing"
    assert registry.all_models_loaded is False


def test_registry_corrupt_joblib_marked_invalid(tmp_path):
    _write_config(tmp_path, BASE_CONFIG)
    (tmp_path / "anomaly_model.joblib").write_bytes(b"this is not a joblib file")
    registry = ModelRegistry(tmp_path)
    registry.load()
    entry = registry.get("anomaly")
    assert entry.status == "invalid"
    assert entry.error_code == "model_artifact_invalid"
    # Safe message: no filesystem path, no traceback.
    assert str(tmp_path) not in (entry.error_detail or "")


def test_registry_wrong_model_class_marked_invalid(tmp_path):
    _write_config(tmp_path, BASE_CONFIG)
    joblib.dump({"not": "a model"}, tmp_path / "forecast_model.joblib")
    registry = ModelRegistry(tmp_path)
    registry.load()
    entry = registry.get("forecast")
    assert entry.status == "invalid"
    assert "HistGradientBoostingRegressor" in (entry.error_detail or "")


def test_registry_feature_mismatch_detected(tmp_path):
    config = dict(BASE_CONFIG)
    config["forecast_features"] = ["hour", "unknown_custom_feature"]
    _write_config(tmp_path, config)
    joblib.dump({"x": 1}, tmp_path / "forecast_model.joblib")
    registry = ModelRegistry(tmp_path)
    registry.load()
    entry = registry.get("forecast")
    assert entry.status == "feature_mismatch"
    assert entry.error_code == "incompatible_model_features"


def test_registry_require_raises_503_for_missing(tmp_path):
    registry = ModelRegistry(tmp_path / "nothing")
    registry.load()
    with pytest.raises(ModelUnavailableError) as excinfo:
        registry.require("forecast")
    assert excinfo.value.status_code == 503
    assert "model_config" in excinfo.value.code or excinfo.value.code == "model_unavailable"
    assert str(tmp_path) not in excinfo.value.message


def test_endpoints_503_when_models_missing(degraded_registry):
    settings = make_settings()
    with make_client(settings=settings, registry=degraded_registry) as client:
        forecast = client.post(
            "/api/v1/forecast",
            json={"meter_id": "m", "readings": [{"timestamp": "2026-01-01T00:00:00Z", "energy_kwh": 5.0}]},
        )
        anomalies = client.post(
            "/api/v1/anomalies/detect",
            json={"meter_id": "m", "readings": [{"timestamp": "2026-01-01T00:00:00Z", "energy_kwh": 5.0}]},
        )
    assert forecast.status_code == 503
    assert forecast.json()["error"]["code"] in {
        "model_unavailable",
        "model_artifact_missing",
        "model_config_missing",
        "model_artifact_invalid",
        "incompatible_model_features",
    }
    assert anomalies.status_code == 503
    assert "Traceback" not in forecast.text


# --------------------------------------------------------------------------
# Integration tests that need the REAL trained artifacts — skipped while the
# ZIP has not been committed to the repository (see docs/AUDIT_AND_PLAN.md).
# --------------------------------------------------------------------------
@pytest.mark.skipif(
    not REAL_ARTIFACTS_PRESENT,
    reason="trained BDG2 artifacts not present in backend/artifacts/ (synthetic demo files are excluded)",
)
def test_real_artifacts_load_and_ready_reports_ok():
    settings = make_settings(model_artifacts_dir=ARTIFACTS_DIR)
    registry = ModelRegistry(ARTIFACTS_DIR)
    registry.load()
    with make_client(settings=settings, registry=registry) as client:
        response = client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["models"]["anomaly"]["model_class"] == "IsolationForest"
    assert body["models"]["forecast"]["model_class"] == "HistGradientBoostingRegressor"
