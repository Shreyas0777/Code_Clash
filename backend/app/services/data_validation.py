"""Input validation and normalization for energy readings.

Rules (documented, never silent):
- Timezone-aware timestamps are converted to UTC; naive timestamps are
  assumed to be UTC.  Mixing naive and aware timestamps is rejected (422).
- Out-of-order readings are sorted and reported as a warning.
- Duplicate timestamps are aggregated by mean (matching the training-time
  rule) and reported as a warning.
- Negative / NaN / infinite values are rejected earlier by the Pydantic
  schema with 422 — they are never silently transformed.
"""

from __future__ import annotations

from typing import List, Sequence

from ..core.exceptions import AppError
from ..schemas.common import DataQualityWarning, ValidatedReadings
from ..schemas.energy import Reading
from ..utils.timestamps import to_naive_utc


def check_readings_count(count: int, max_readings: int) -> None:
    if count > max_readings:
        raise AppError(
            code="too_many_readings",
            message=(
                f"Request contains {count} readings; the maximum allowed is "
                f"{max_readings} per request."
            ),
            status_code=422,
            details=[
                {
                    "field": "readings",
                    "message": f"{count} > {max_readings}",
                    "type": "too_many_readings",
                }
            ],
        )


def normalize_readings(readings: Sequence[Reading]) -> ValidatedReadings:
    """Sort, deduplicate and timezone-normalize raw readings."""
    if not readings:
        raise AppError(
            code="request_validation_error",
            message="At least one reading is required.",
            status_code=422,
        )

    warnings: List[DataQualityWarning] = []

    aware = [r.timestamp.tzinfo is not None for r in readings]
    if any(aware) and not all(aware):
        raise AppError(
            code="mixed_timestamp_timezones",
            message=(
                "Timestamps mix timezone-aware and naive values. Provide all "
                "timestamps with an offset (e.g. Z) or all naive (assumed UTC)."
            ),
            status_code=422,
            details=[
                {
                    "field": "readings.timestamp",
                    "message": "mixed naive and timezone-aware timestamps",
                    "type": "mixed_timestamp_timezones",
                }
            ],
        )

    normalized = [(to_naive_utc(r.timestamp), float(r.energy_kwh)) for r in readings]

    # Out-of-order detection (before sorting).
    ordered = all(normalized[i][0] <= normalized[i + 1][0] for i in range(len(normalized) - 1))
    if not ordered:
        warnings.append(
            DataQualityWarning(
                code="readings_reordered",
                message="Input readings were not in chronological order; they were sorted.",
                count=None,
            )
        )
    normalized.sort(key=lambda pair: pair[0])

    # Duplicate aggregation: mean per timestamp (training-time rule).
    deduped: List[tuple] = []
    duplicates = 0
    for ts, value in normalized:
        if deduped and deduped[-1][0] == ts:
            prev_ts, prev_value = deduped[-1]
            duplicates += 1
            deduped[-1] = (prev_ts, (prev_value + value) / 2.0)
        else:
            deduped.append((ts, value))
    if duplicates:
        warnings.append(
            DataQualityWarning(
                code="duplicate_timestamps_aggregated",
                message=(
                    f"{duplicates} duplicate-timestamp reading(s) were aggregated "
                    "by mean (training-time rule)."
                ),
                count=duplicates,
            )
        )

    return ValidatedReadings(
        timestamps=[pair[0] for pair in deduped],
        energy_kwh=[pair[1] for pair in deduped],
        warnings=warnings,
    )
