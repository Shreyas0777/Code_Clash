"""Structured logging for the Fluxora API.

JSON by default (one object per line) so logs can be shipped/parsed without
extra dependencies; a human-readable ``text`` format is available for local
development via ``LOG_FORMAT=text``.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional

# Attributes present on every LogRecord; anything else is treated as a
# structured field supplied via ``logger.info("msg", extra={...})``.
_RESERVED = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Format a log record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_type"] = getattr(record.exc_info[0], "__name__", "Exception")
            # Full traceback stays in the server log only — never in API
            # responses.
            payload["traceback"] = self.formatException(record.exc_info)
        try:
            return json.dumps(payload, default=str)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return json.dumps({"ts": payload["ts"], "level": payload["level"], "msg": payload["msg"]})


class TextFormatter(logging.Formatter):
    """Human-readable single-line format with structured fields appended."""

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()} "
            f"{record.levelname:<7} {record.name}: {record.getMessage()}"
        )
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _RESERVED and not k.startswith("_")
        }
        if extras:
            base += " | " + " ".join(f"{k}={v}" for k, v in extras.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging(level: str = "INFO", log_format: str = "json") -> None:
    """Configure the root logger exactly once."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if log_format.lower() == "json" else TextFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn duplicates its own access logs; keep them but route them through
    # our handler at the configured level.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Emit a structured log event: ``{"msg": ..., "event": "..."}``."""
    logger.log(level, event, extra={"event": event, **fields})


__all__ = [
    "JsonFormatter",
    "TextFormatter",
    "setup_logging",
    "get_logger",
    "log_event",
    "Optional",
]
