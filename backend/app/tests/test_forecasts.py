"""Tests: forecasting — feature engineering, horizons, history requirements."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from .conftest import (
    FORECAST_FEATURES,
    ExplodingModel,
    fixture_registry,
    make_client,
    synthetic_hourly_readings,
)


def _manual_expected(readings, model) -> tuple[datetime, float]:
    """Recompute the training-time features by hand and predict directly."""
    index = pd.DatetimeIndex([pd.Timestamp(r["timestamp"].replace("Z", "")) for r in readings])
    series = pd.Series([r["energy_kwh"] for r in readings], index=index).sort_index()
    target = series.index.max() + pd.Timedelta(hours=1)
    features = {
        "hour": int(target.hour),
        "day_of_week": int(target.dayofweek),
        "month": int(target.month),
        "lag_1": float(series.loc[target - pd.Timedelta(hours=1)]),
        "lag_24": float(series.loc[target - pd.Timedelta(hours=24)]),
        "lag_168": float(series.loc[target - pd.Timedelta(hours=168)]),
        "rolling_mean_24": float(
            series.loc[
                target - pd.Timedelta(hours=24) : target - pd.Timedelta(hours=1)
            ].mean()
        ),
    }
    frame = pd.DataFrame(
        [{name: features[name] for name in FORECAST_FEATURES}],
        columns=FORECAST_FEATURES,
    )
    return target.to_pydatetime(), float(model.predict(frame)[0])


def test_next_hour_forecast_exact_value(loaded_registry, readings_720h):
    """The API value must equal a direct model.predict on hand-built features."""
    expected_ts, expected_value = _manual_expected(
        readings_720h, loaded_registry.get("forecast").model
    )
    payload = {"meter_id": "m", "readings": readings_720h}
    with make_client(registry=loaded_registry) as client:
        response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["forecast_timestamp"] == expected_ts.isoformat()
    assert abs(body["predicted_energy_kwh"] - expected_value) < 1e-9
    assert body["horizon_hours"] == 1
    assert body["unit"] == "kWh"
    assert body["prediction_type"] == "estimate"
    assert "not a measurement" in body["interpretation_note"]
    assert body["model"]["status"] == "loaded"
    assert body["model"]["version"] == "test_fixture_forecast"
    assert body["input_period"]["start"] is not None
    assert body["input_period"]["end"] is not None


def test_insufficient_history_short_input(loaded_registry):
    """48 hours < 168 required lag hours → explicit 422, no prediction."""
    readings = synthetic_hourly_readings(hours=48)
    payload = {"meter_id": "m", "readings": readings}
    with make_client(registry=loaded_registry) as client:
        response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "insufficient_history"
    serialized = str(body)
    assert "168" in serialized
    assert "predicted_energy_kwh" not in body


def test_unsupported_horizon_rejected(loaded_registry, readings_720h):
    payload = {"meter_id": "m", "readings": readings_720h, "horizon_hours": 6}
    with make_client(registry=loaded_registry) as client:
        response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_forecast_horizon"


def test_forecast_503_without_model(degraded_registry, readings_720h):
    payload = {"meter_id": "m", "readings": readings_720h}
    with make_client(registry=degraded_registry) as client:
        response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 503
    assert response.json()["error"]["code"] in {
        "model_unavailable",
        "model_artifact_missing",
        "model_config_missing",
    }


def test_short_gap_interpolated_and_reported(loaded_registry):
    """A 2-hour gap (<= 3h training limit) is interpolated and disclosed."""
    readings = synthetic_hourly_readings(hours=24 * 8)
    # Remove readings 100 and 101 (a 2-hour gap, before the lag window).
    dropped = {100, 101}
    gappy = [r for i, r in enumerate(readings) if i not in dropped]
    payload = {"meter_id": "m", "readings": gappy}
    with make_client(registry=loaded_registry) as client:
        response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 200
    body = response.json()
    codes = {w["code"] for w in body["warnings"]}
    assert "hourly_grid_imputed" in codes
    warning = next(w for w in body["warnings"] if w["code"] == "hourly_grid_imputed")
    assert "never treated as zero" in warning["message"]


def test_long_gap_in_lag_window_rejected_not_filled(loaded_registry):
    """A >3h gap inside the rolling window stays missing → 422, never zero."""
    readings = synthetic_hourly_readings(hours=24 * 10)
    # Remove hours 230..235 (6 consecutive hours) near the end.
    dropped = set(range(230, 236))
    gappy = [r for i, r in enumerate(readings) if i not in dropped]
    payload = {"meter_id": "m", "readings": gappy}
    with make_client(registry=loaded_registry) as client:
        response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "insufficient_history"


def test_duplicate_readings_do_not_break_forecast(loaded_registry, readings_720h):
    duplicated = list(readings_720h) + [dict(readings_720h[100])]
    payload = {"meter_id": "m", "readings": duplicated}
    with make_client(registry=loaded_registry) as client:
        response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 200
    codes = {w["code"] for w in response.json()["warnings"]}
    assert "duplicate_timestamps_aggregated" in codes


def test_forecast_input_period_reported(loaded_registry, readings_720h):
    payload = {"meter_id": "m", "readings": readings_720h}
    with make_client(registry=loaded_registry) as client:
        body = client.post("/api/v1/forecast", json=payload).json()
    assert body["input_period"]["start"] == "2026-01-05T00:00:00"
    assert body["input_period"]["end"] == "2026-02-03T23:00:00"
    assert body["forecast_timestamp"] == "2026-02-04T00:00:00"


def test_forecast_inference_failure_returns_structured_500(
    readings_720h, tiny_anomaly_model
):
    """A model whose predict() raises yields a safe 500, never a leaked traceback."""
    registry = fixture_registry(tiny_anomaly_model, ExplodingModel())
    payload = {"meter_id": "m", "readings": readings_720h}
    with make_client(registry=registry) as client:
        response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "model_inference_failed"
    assert "simulated model failure" not in response.text
    assert "Traceback" not in response.text
