"""Timestamp handling and training-faithful hourly regularization.

Reproduces the preprocessing used in the training notebook:
hourly reindex over [min, max], then time-based interpolation limited to
3 consecutive hours and only inside the series (long gaps stay missing and
are never treated as zero consumption).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Sequence, Tuple

import pandas as pd

from ..schemas.common import DataQualityWarning

INTERPOLATION_LIMIT_HOURS = 3


def to_naive_utc(value: datetime) -> datetime:
    """Normalize a timestamp to naive UTC (documented rule: naive = UTC)."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def hourly_grid_series(
    timestamps: Sequence[datetime],
    energy_kwh: Sequence[float],
) -> Tuple[pd.Series, List[DataQualityWarning]]:
    """Regularize readings onto a contiguous hourly grid.

    Returns ``(series, warnings)`` where the series is indexed by naive-UTC
    hourly timestamps.  Missing hours are interpolated only when the gap is
    <= 3 hours and strictly inside the series; remaining gaps stay ``NaN``.
    """
    index = pd.DatetimeIndex(pd.to_datetime(list(timestamps)))
    series = pd.Series(list(energy_kwh), index=index, dtype="float64")
    series = series.sort_index()

    warnings: List[DataQualityWarning] = []
    if series.index.min() == series.index.max():
        grid = pd.DatetimeIndex([series.index.min()])
    else:
        grid = pd.date_range(start=series.index.min(), end=series.index.max(), freq="h")

    regularized = series.reindex(grid)
    regularized.index.name = "timestamp"

    missing_before = int(regularized.isna().sum())
    if missing_before > 0 and len(grid) > 1:
        filled = regularized.interpolate(
            method="time",
            limit=INTERPOLATION_LIMIT_HOURS,
            limit_area="inside",
        )
    else:
        filled = regularized

    imputed = missing_before - int(filled.isna().sum())
    still_missing = int(filled.isna().sum())

    if missing_before > 0:
        warnings.append(
            DataQualityWarning(
                code="hourly_grid_imputed",
                message=(
                    f"{missing_before} hourly slot(s) were absent from the input. "
                    f"{imputed} short gap hour(s) were linearly interpolated (max "
                    f"{INTERPOLATION_LIMIT_HOURS}h, training-time rule); "
                    f"{still_missing} hour(s) remain missing and are never treated as zero."
                ),
                count=missing_before,
            )
        )
    return filled, warnings
