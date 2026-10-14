"""Fluxora API application factory.

- Models load **once** during lifespan startup (never retrained, never
  downloaded); failures degrade readiness instead of crashing the process.
- Centralized structured error handling (see ``core.exceptions``).
- Explicit CORS origins, request-size limits, structured request logging.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from .api.v1.router import api_router
from .core.config import Settings, get_settings
from .core.exceptions import register_exception_handlers
from .core.logging import setup_logging
from .services.model_registry import ModelRegistry

logger = logging.getLogger("fluxora.request")

TAGS_METADATA = [
    {"name": "health", "description": "Liveness and readiness probes (readiness reflects model artifacts)."},
    {"name": "energy", "description": "Validation, statistics and optional anomaly flags for submitted readings."},
    {"name": "forecast", "description": "Next-hour demand estimates (single-step model; estimates, not measurements)."},
    {"name": "anomalies", "description": "IsolationForest anomaly labels and relative scores (unusual readings, not confirmed faults)."},
    {"name": "carbon", "description": "Operational emissions estimates using a configured, sourced emission factor."},
    {"name": "scenarios", "description": "Deterministic energy-saving scenario projections (no ML involved)."},
]

API_DESCRIPTION = """
**Fluxora — Energy Intelligence & Carbon Optimization.**
Decode Energy. Design a Greener Future.

REST API for analyzing hourly electricity readings, forecasting next-hour
demand, flagging unusual readings, estimating operational carbon emissions,
and simulating energy-saving interventions.

**Honesty rules baked into this API:**
* Predictions are labeled `estimate`; anomaly flags are not confirmed faults.
* Missing model artifacts degrade specific endpoints with `503` — the API
  never fabricates predictions. Check `GET /api/v1/ready`.
* Carbon estimates require a configured emission factor with provenance; no
  default factor is bundled.
* Scenario results are deterministic projections of caller-supplied
  assumptions, never measured savings.
"""


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized bodies early (413) using Content-Length."""

    def __init__(self, app, max_bytes: int) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "request_too_large",
                        "message": (
                            f"Request body exceeds the {self.max_bytes}-byte limit. "
                            "Split the payload or raise MAX_REQUEST_BYTES."
                        ),
                        "details": [],
                    }
                },
            )
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Structured per-request logs with a request id; bodies are never logged."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "request_failed",
                extra={
                    "event": "request_failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request",
            extra={
                "event": "request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


def create_app(
    settings: Optional[Settings] = None,
    registry: Optional[ModelRegistry] = None,
) -> FastAPI:
    """Application factory (also used by tests for dependency injection)."""
    settings = settings or get_settings()
    setup_logging(level=settings.log_level, log_format=settings.log_format)

    registry = registry or ModelRegistry(settings.model_artifacts_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load artifacts exactly once; failures degrade /ready, not startup.
        registry.load()
        logger.info(
            "startup",
            extra={
                "event": "startup",
                "environment": settings.environment,
                "artifacts_ready": registry.all_models_loaded,
                "model_config_status": registry.config_status,
            },
        )
        yield
        logger.info("shutdown", extra={"event": "shutdown"})

    app = FastAPI(
        title=settings.app_name,
        description=API_DESCRIPTION,
        version=settings.app_version,
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.registry = registry

    register_exception_handlers(app)

    # Order: size limit (inner) … CORS (outermost) so error responses still
    # receive CORS headers for allowed origins.
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["content-type", "x-request-id"],
        expose_headers=["x-request-id"],
        max_age=600,
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "api": settings.api_v1_prefix,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
            "ready": f"{settings.api_v1_prefix}/ready",
        }

    return app


app = create_app()
