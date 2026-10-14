"""Deterministic energy statistics (no ML involved)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Sequence, Tuple

from ..schemas.energy import EnergyStats


def compute_stats(
    timestamps: Sequence[datetime],
    energy_kwh: Sequence[float],
) -> Tuple[EnergyStats, datetime, datetime]:
    """Compute summary statistics over validated (deduplicated) readings."""
    if not energy_kwh:
        raise ValueError("compute_stats requires at least one reading")
    values = list(energy_kwh)
    count = len(values)
    total = float(sum(values))
    return (
        EnergyStats(
            count=count,
            mean_kwh=total / count,
            min_kwh=float(min(values)),
            max_kwh=float(max(values)),
            total_kwh=total,
        ),
        timestamps[0],
        timestamps[-1],
    )
