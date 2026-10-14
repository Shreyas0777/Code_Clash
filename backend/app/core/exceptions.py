"""Centralized error types and handlers.

Every error response has the same shape::

    {"error": {"code": "...", "message": "...", "details": [...]}}

Diagnostics (paths, stack traces) are written to server logs only; API
responses carry safe, stable messages.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("fluxora.errors")


class AppError(Exception):
    """Base class for errors that map to a structured HTTP response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []

    def to_payload(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ModelUnavailableError(AppError):
    """A required model artifact could not be used for inference."""

    def __init__(
        self,
        message: str = (
            "A required model artifact is not available. Place the exported "
            "artifacts in the configured model directory and restart the API "
            "(see backend/README.md)."
        ),
        code: str = "model_unavailable",
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(code=code, message=message, status_code=503, details=details)


class InsufficientHistoryError(AppError):
    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(
            code="insufficient_history",
            message=message,
            status_code=422,
            details=details,
        )


class ConfigurationError(AppError):
    """Server-side configuration problem reported as a validation failure."""

    def __init__(self, code: str, message: str, details: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(code=code, message=message, status_code=422, details=details)


def _validation_details(exc: RequestValidationError) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", []) if part != "body"]
        details.append(
            {
                "field": ".".join(loc) if loc else None,
                "message": err.get("msg", "invalid value"),
                "type": err.get("type", "value_error"),
            }
        )
    return details


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error(
                "application_error",
                extra={"event": "application_error", "code": exc.code, "status": exc.status_code},
            )
        else:
            logger.warning(
                "application_error",
                extra={"event": "application_error", "code": exc.code, "status": exc.status_code},
            )
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        # Malformed JSON arrives as a validation error of type "json_invalid";
        # the contract reserves 400 for malformed request bodies.
        malformed = bool(errors) and all(e.get("type") == "json_invalid" for e in errors)
        code = "invalid_json" if malformed else "request_validation_error"
        status = 400 if malformed else 422
        message = (
            "Request body is not valid JSON."
            if malformed
            else "Request failed schema validation."
        )
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "details": [] if malformed else _validation_details(exc),
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            404: "not_found",
            405: "method_not_allowed",
        }.get(exc.status_code, "http_error")
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": detail,
                    "details": [],
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        # Full traceback goes to server logs only.
        logger.exception(
            "unhandled_server_error",
            extra={"event": "unhandled_server_error", "error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected server error occurred.",
                    "details": [],
                }
            },
        )
