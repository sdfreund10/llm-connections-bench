"""Structured application logging for Cloud Logging and local CLI.

Emits JSON lines when ``DATA_BUCKET`` is set (or ``LOG_FORMAT=json``);
otherwise a compact text form. Call ``configure_logging()`` from the CLI.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date
from typing import Any

LOGGER_NAME = "llm_connections"

_RESERVED_RECORD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}

_configured = False


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


class _TextFormatter(logging.Formatter):
    _FIELD_ORDER = (
        "stage",
        "model",
        "date",
        "status",
        "outcome",
        "ran",
        "skipped",
        "failed",
        "returncode",
        "mistakes",
    )

    def format(self, record: logging.LogRecord) -> str:
        parts = [record.getMessage()]
        for key in self._FIELD_ORDER:
            value = record.__dict__.get(key)
            if value is not None:
                parts.append(f"{key}={value}")
        return " ".join(parts)


def configure_logging(*, force: bool = False) -> None:
    """Attach a stdout handler to the app logger (idempotent unless force)."""
    global _configured
    if _configured and not force:
        return

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter() if _use_json() else _TextFormatter())
    logger.addHandler(handler)
    _configured = True


def event(
    message: str,
    *,
    stage: str,
    level: int = logging.INFO,
    model: str | None = None,
    game_date: date | str | None = None,
    status: str | None = None,
    **fields: Any,
) -> None:
    """Log one structured event with the Phase 3 fields (stage/model/date/status)."""
    extra: dict[str, Any] = {"stage": stage}
    if model is not None:
        extra["model"] = model
    if game_date is not None:
        # Field name in the log payload is ``date`` (plan); param avoids shadowing datetime.date.
        if isinstance(game_date, date):
            extra["date"] = game_date.isoformat()
        else:
            extra["date"] = str(game_date)
    if status is not None:
        extra["status"] = status
    for key, value in fields.items():
        if value is not None:
            extra[key] = value

    _logger().log(level, message, extra=extra)


def _logger() -> logging.Logger:
    if not _configured:
        configure_logging()
    return logging.getLogger(LOGGER_NAME)


def _use_json() -> bool:
    fmt = os.environ.get("LOG_FORMAT", "auto").strip().lower()
    if fmt in ("json", "1", "true", "yes"):
        return True
    if fmt in ("text", "plain", "0", "false", "no"):
        return False
    return bool(os.environ.get("DATA_BUCKET", "").strip())
