"""Health (liveness) and readiness endpoints — deliberately distinct.

``/health`` reports that the process is running.
``/ready`` reports whether required model artifacts loaded successfully;
it returns 503 while degraded so orchestrators/probes can tell the difference.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/ready",
    summary="Readiness probe (models + configuration)",
    responses={
        200: {"description": "All required model artifacts loaded"},
        503: {"description": "Degraded: one or more required artifacts unavailable"},
    },
)
def ready(request: Request, response: Response) -> dict:
    settings = request.app.state.settings
    registry = request.app.state.registry
    report = registry.readiness_report()
    payload = {
        "ready": report["ready"],
        "model_config_status": report["model_config_status"],
        "models": report["models"],
        "carbon_factor_configured": settings.carbon_factor_configured,
        "notes": report["notes"],
        "api_version": settings.app_version,
    }
    if not report["ready"]:
        response.status_code = 503
    return payload
