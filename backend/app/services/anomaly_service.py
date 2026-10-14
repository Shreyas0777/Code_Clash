"""Anomaly inference — shared by ``/energy/analyze`` and ``/anomalies/detect``.

Feature engineering and output interpretation follow the training notebook:
- Features: ``energy_kwh``, ``hour``, ``day_of_week`` (Monday=0), ``month``.
- ``predict()`` → ``-1`` = anomaly, ``1`` = typical.
- Score = ``-score_samples()`` (higher = more unusual) — a *relative* score,
  not a calibrated probability.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ..schemas.anomaly import AnomalyResult
from ..schemas.common import ValidatedReadings
from .model_registry import ModelEntry

ANOMALY_INTERPRETATION = (
    "An anomaly flag indicates a reading that is unusual relative to the "
    "model's training data. It is not a confirmed equipment fault and not "
    "proof of energy waste; investigate before acting on it."
)

SUPPORTED_BASE_FEATURES = ("energy_kwh", "hour", "day_of_week", "month")


def build_feature_frame(
    readings: ValidatedReadings,
    feature_names: List[str],
) -> pd.DataFrame:
    """Build the training-time anomaly feature frame in the configured order."""
    index = pd.DatetimeIndex(pd.to_datetime(list(readings.timestamps)))
    base = pd.DataFrame(
        {
            "energy_kwh": list(readings.energy_kwh),
            "hour": index.hour,
            "day_of_week": index.dayofweek,
            "month": index.month,
        },
        index=index,
    )
    return base[feature_names]


def detect(
    readings: ValidatedReadings,
    entry: ModelEntry,
) -> List[AnomalyResult]:
    """Run anomaly inference for every validated reading.

    ``entry`` must be a loaded model entry (callers use
    ``registry.anomaly_model_entry()``, which raises 503 otherwise).
    """
    feature_names = list(entry.feature_names or [])
    frame = build_feature_frame(readings, feature_names)

    raw_labels: Any = entry.model.predict(frame)
    raw_scores: Any = entry.model.score_samples(frame)
    scores = [-float(s) for s in raw_scores]  # score = -score_samples (training rule)

    results: List[AnomalyResult] = []
    for ts, energy, label, score in zip(
        readings.timestamps, readings.energy_kwh, raw_labels, scores
    ):
        model_output = int(label)
        results.append(
            AnomalyResult(
                timestamp=ts,
                energy_kwh=energy,
                label="anomaly" if model_output == -1 else "typical",
                model_output=model_output,
                anomaly_score=score,
            )
        )
    return results


def flagged_readings(results: List[AnomalyResult]) -> List[Dict[str, Any]]:
    return [
        {
            "timestamp": r.timestamp,
            "energy_kwh": r.energy_kwh,
            "anomaly_score": r.anomaly_score,
        }
        for r in results
        if r.model_output == -1
    ]
