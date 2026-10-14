"""Shared test fixtures.

⚠ ALL model fixtures and meter series here are **SYNTHETIC** — generated in
process for tests only.  They are not trained on BDG2, are never serialized to
the artifacts directory, and are labeled ``test_fixture`` in every response
version field.  Tests never require the production artifacts.
"""

from __future__ import annotations

import contextlib
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest

from app.core.config import Settings
from app.main import create_app
from app.services.model_registry import ModelRegistry

FORECAST_FEATURES = [
    "hour",
    "day_of_week",
    "month",
    "lag_1",
    "lag_24",
    "lag_168",
    "rolling_mean_24",
]
ANOMALY_FEATURES = ["energy_kwh", "hour", "day_of_week", "month"]

SYNTHETIC_DATASET_LABEL = "SYNTHETIC_TEST_FIXTURE_NOT_BDG2"


def make_settings(**overrides) -> Settings:
    """Build test settings; environment file disabled and artifacts isolated.

    ``model_artifacts_dir`` defaults to a NON-EXISTENT path so local artifact
    state (real export or synthetic demo files) can never leak into tests.
    """
    base = dict(
        environment="test",
        log_level="WARNING",
        log_format="text",
        cors_allow_origins="http://localhost:5173,http://localhost:3000",
        model_artifacts_dir=Path("nonexistent_test_artifacts_dir"),
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


@contextlib.contextmanager
def make_client(
    settings: Optional[Settings] = None,
    registry: Optional[ModelRegistry] = None,
) -> Iterator[TestClient]:
    """App + TestClient with lifespan executed (model load happens here)."""
    settings = settings or make_settings()
    registry = registry or ModelRegistry(settings.model_artifacts_dir)
    app = create_app(settings=settings, registry=registry)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def empty_registry(artifacts_dir: Path) -> ModelRegistry:
    """Registry pointing at a directory with no artifacts (degraded path)."""
    return ModelRegistry(artifacts_dir)


def fixture_registry(
    anomaly_model,
    forecast_model,
    config_overrides: Optional[dict] = None,
) -> ModelRegistry:
    """Registry with in-memory synthetic models injected (dependency injection)."""
    registry = ModelRegistry(Path("nonexistent_test_artifacts_dir"))
    config = {
        "project": "Fluxora",
        "dataset": SYNTHETIC_DATASET_LABEL,
        "artifact_source": "test_fixture",
        "synthetic": True,
        "target_column": "energy_kwh",
        "forecast_features": FORECAST_FEATURES,
        "anomaly_features": ANOMALY_FEATURES,
        "forecast_horizon_hours": 1,
        "data_frequency": "hourly",
    }
    if config_overrides:
        config.update(config_overrides)
    registry.set_config(config)
    registry.set_model(
        "anomaly",
        model=anomaly_model,
        feature_names=ANOMALY_FEATURES,
        version="test_fixture_anomaly",
        dataset=SYNTHETIC_DATASET_LABEL,
    )
    registry.set_model(
        "forecast",
        model=forecast_model,
        feature_names=FORECAST_FEATURES,
        version="test_fixture_forecast",
        dataset=SYNTHETIC_DATASET_LABEL,
    )
    return registry


# --------------------------------------------------------------------------
# SYNTHETIC data
# --------------------------------------------------------------------------
def synthetic_hourly_readings(hours: int = 24 * 30, start: Optional[datetime] = None):
    """SYNTHETIC hourly readings (not BDG2). All values strictly positive."""
    start = start or datetime(2026, 1, 5, 0, 0)  # a Monday
    readings = []
    for h in range(hours):
        ts = start + timedelta(hours=h)
        value = (
            100.0
            + 20.0 * math.sin(2 * math.pi * ts.hour / 24)
            + 8.0 * math.cos(2 * math.pi * h / 168)
            + 2.0 * math.sin(2 * math.pi * h / 36)
        )
        readings.append(
            {
                "timestamp": ts.isoformat() + "Z",
                "energy_kwh": round(value, 4),
            }
        )
    return readings


@pytest.fixture
def readings_720h():
    """SYNTHETIC: 30 days of hourly readings."""
    return synthetic_hourly_readings(hours=24 * 30)


@pytest.fixture
def tiny_anomaly_model():
    """SYNTHETIC IsolationForest test double (in-memory, labeled)."""
    rng = np.random.default_rng(42)
    n = 500
    frame = pd.DataFrame(
        {
            "energy_kwh": rng.normal(100.0, 5.0, n),
            "hour": rng.integers(0, 24, n),
            "day_of_week": rng.integers(0, 7, n),
            "month": rng.integers(1, 13, n),
        }
    )
    model = IsolationForest(n_estimators=100, contamination=0.02, random_state=42)
    model.fit(frame)
    return model


@pytest.fixture
def tiny_forecast_model():
    """SYNTHETIC HistGradientBoostingRegressor test double (in-memory)."""
    rng = np.random.default_rng(7)
    n = 800
    features = {
        "hour": rng.integers(0, 24, n).astype(float),
        "day_of_week": rng.integers(0, 7, n).astype(float),
        "month": rng.integers(1, 13, n).astype(float),
        "lag_1": rng.uniform(50, 200, n),
        "lag_24": rng.uniform(50, 200, n),
        "lag_168": rng.uniform(50, 200, n),
        "rolling_mean_24": rng.uniform(50, 200, n),
    }
    y = (
        12.0
        + 0.5 * features["lag_1"]
        + 0.15 * features["lag_24"]
        + 0.1 * features["lag_168"]
        + 0.05 * features["rolling_mean_24"]
        + 0.05 * features["hour"]
    )
    frame = pd.DataFrame({name: features[name] for name in FORECAST_FEATURES})
    model = HistGradientBoostingRegressor(
        max_iter=60, learning_rate=0.1, random_state=42
    )
    model.fit(frame, y)
    return model


@pytest.fixture
def loaded_registry(tiny_anomaly_model, tiny_forecast_model) -> ModelRegistry:
    """Fully-loaded registry with synthetic models (labeled test_fixture)."""
    return fixture_registry(tiny_anomaly_model, tiny_forecast_model)


@pytest.fixture
def degraded_registry(tmp_path) -> ModelRegistry:
    """Registry over an empty artifacts directory (missing models)."""
    return ModelRegistry(tmp_path / "empty_artifacts")
