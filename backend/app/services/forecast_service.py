"""Next-hour energy forecasting.

Reproduces the training-time feature engineering exactly:

- ``hour`` / ``day_of_week`` / ``month`` of the **target** hour ``T``.
- ``lag_1`` = value at ``T-1h``; ``lag_24`` = ``T-24h``; ``lag_168`` = ``T-168h``.
- ``rolling_mean_24`` = mean of the 24 hours ``T-24h .. T-1h`` (the training
  code used ``shift(1).rolling(24)``, i.e. the current hour is excluded —
  no leakage from the value being predicted).

The one-step model only supports ``horizon_hours == 1``; anything else is
rejected with an explicit error instead of silently extrapolating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List

import pandas as pd

from ..core.exceptions import AppError, InsufficientHistoryError
from ..schemas.common import DataQualityWarning, ValidatedReadings
from .model_registry import ModelEntry
from .data_validation import normalize_readings
from ..utils.timestamps import hourly_grid_series

SUPPORTED_HORIZON_HOURS = 1
REQUIRED_HISTORY_HOURS = 168  # lag_168 from the training feature set

FORECAST_INTERPRETATION = (
    "This value is a model-generated estimate for the next hour based on "
    "historical patterns — it is not a measurement and not a guarantee."
)


@dataclass
class ForecastOutcome:
    forecast_timestamp: datetime
    predicted_energy_kwh: float
    horizon_hours: int
    input_period_start: datetime
    input_period_end: datetime
    warnings: List[DataQualityWarning] = field(default_factory=list)


def _insufficient(missing: List[str], start: datetime, end: datetime) -> InsufficientHistoryError:
    return InsufficientHistoryError(
        message=(
            "Not enough valid hourly history to build the trained features. "
            f"Required: {REQUIRED_HISTORY_HOURS} hours of coverage before the "
            "forecast timestamp with no gap longer than 3 consecutive hours."
        ),
        details=[
            {
                "field": "readings",
                "message": f"missing required values for: {', '.join(missing)}",
                "type": "insufficient_history",
            },
            {
                "field": "readings",
                "message": (
                    f"input covers {start.isoformat()} to {end.isoformat()} "
                    "(naive UTC)"
                ),
                "type": "input_coverage",
            },
        ],
    )


def predict_next_hour(
    readings: ValidatedReadings,
    entry: ModelEntry,
    horizon_hours: int,
) -> ForecastOutcome:
    """Produce a next-hour estimate from validated readings."""
    if horizon_hours != SUPPORTED_HORIZON_HOURS:
        raise AppError(
            code="unsupported_forecast_horizon",
            message=(
                f"The trained model supports a {SUPPORTED_HORIZON_HOURS}-hour "
                f"(next-hour) horizon only; {horizon_hours}h was requested. "
                "Request horizon_hours=1."
            ),
            status_code=422,
            details=[
                {
                    "field": "horizon_hours",
                    "message": f"unsupported horizon {horizon_hours}h",
                    "type": "unsupported_forecast_horizon",
                }
            ],
        )

    if len(readings.timestamps) == 0:
        raise AppError(
            code="request_validation_error",
            message="At least one reading is required.",
            status_code=422,
        )

    series, grid_warnings = hourly_grid_series(readings.timestamps, readings.energy_kwh)
    input_start = pd.Timestamp(readings.timestamps[0]).to_pydatetime()
    input_end = pd.Timestamp(max(readings.timestamps)).to_pydatetime()

    if series.isna().all():
        raise _insufficient(["any valid hourly value"], input_start, input_end)

    last = series.index.max().to_pydatetime()
    target = last + timedelta(hours=SUPPORTED_HORIZON_HOURS)

    # --- required lag values at target-relative offsets ------------------
    required_offsets = {"lag_1": 1, "lag_24": 24, "lag_168": 168}
    lags: dict[str, float] = {}
    missing: List[str] = []
    for name, hours_back in required_offsets.items():
        stamp = pd.Timestamp(target - timedelta(hours=hours_back))
        if stamp not in series.index or pd.isna(series.loc[stamp]):
            missing.append(f"{name} ({stamp.isoformat()})")
        else:
            lags[name] = float(series.loc[stamp])

    # rolling window: the 24 hours strictly before the target hour
    window_index = pd.date_range(
        start=target - timedelta(hours=24),
        end=target - timedelta(hours=1),
        freq="h",
    )
    if len(window_index) != 24 or not window_index.isin(series.index).all():
        missing.append("rolling_mean_24 (24-hour window before target)")
        rolling: float = float("nan")
    else:
        window_values = series.loc[window_index]
        if window_values.isna().any():
            missing.append("rolling_mean_24 (missing values inside window)")
            rolling = float("nan")
        else:
            rolling = float(window_values.mean())

    if missing:
        raise _insufficient(sorted(set(missing)), input_start, input_end)

    target_ts = pd.Timestamp(target)
    features = {
        "hour": int(target_ts.hour),
        "day_of_week": int(target_ts.dayofweek),
        "month": int(target_ts.month),
        "lag_1": lags["lag_1"],
        "lag_24": lags["lag_24"],
        "lag_168": lags["lag_168"],
        "rolling_mean_24": rolling,
    }

    feature_names = list(entry.feature_names or [])
    unknown = [f for f in feature_names if f not in features]
    if unknown:
        raise AppError(
            code="incompatible_model_features",
            message=(
                "The loaded model requires features this API cannot engineer: "
                + ", ".join(unknown)
            ),
            status_code=503,
        )

    frame = pd.DataFrame(
        [{name: features[name] for name in feature_names}],
        columns=feature_names,
        dtype="float64",
    )

    prediction = entry.model.predict(frame)[0]
    predicted = float(prediction)
    if not pd.notna(predicted):
        raise AppError(
            code="forecast_failed",
            message="The model returned a non-finite prediction for this input.",
            status_code=500,
        )

    warnings: List[DataQualityWarning] = list(grid_warnings)
    warnings.extend(readings.warnings)

    return ForecastOutcome(
        forecast_timestamp=target,
        predicted_energy_kwh=predicted,
        horizon_hours=SUPPORTED_HORIZON_HOURS,
        input_period_start=input_start,
        input_period_end=input_end,
        warnings=warnings,
    )


def forecast_from_raw(
    raw_readings,
    entry: ModelEntry,
    horizon_hours: int,
    max_readings: int,
) -> ForecastOutcome:
    """Convenience wrapper used by the route: validate then predict."""
    from .data_validation import check_readings_count

    check_readings_count(len(raw_readings), max_readings)
    validated = normalize_readings(raw_readings)
    return predict_next_hour(validated, entry, horizon_hours)
