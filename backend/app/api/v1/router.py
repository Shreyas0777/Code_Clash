"""Version 1 API router aggregation (prefix /api/v1)."""

from __future__ import annotations

from fastapi import APIRouter

from . import anomalies, carbon, energy, forecasts, health, scenarios

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(energy.router)
api_router.include_router(forecasts.router)
api_router.include_router(anomalies.router)
api_router.include_router(carbon.router)
api_router.include_router(scenarios.router)
