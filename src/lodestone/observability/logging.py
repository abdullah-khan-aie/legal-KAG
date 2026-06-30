from __future__ import annotations

import datetime as dt
import json
import logging
from logging.config import dictConfig
from typing import Any

from src.lodestone.config.settings import IngestionSettings

# Human-readable line for local development: time | LEVEL | logger | file:line | func | message
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s"

# Standard LogRecord attributes, so we can detect (and promote) only the
# structured context a caller passes via ``logger.info(..., extra={...})``.
_RESERVED_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Render a ``LogRecord`` as a single line of JSON.

    Emits a stable field set (timestamp, level, logger, file, line, function,
    message), attaches exception and stack info when present (as fields, so a
    traceback stays one log event), and promotes any ``extra={...}`` context.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": dt.datetime.fromtimestamp(record.created, dt.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
            "message": record.getMessage(),
        }
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_value) if exc_value else None,
                "traceback": self.formatException(record.exc_info),
            }
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: IngestionSettings) -> None:
    """Configure root logging to stdout, using the format from settings.

    Call once at the process entry point (e.g. FastAPI ``lifespan`` startup).
    Safe to call again: ``dictConfig`` resets the configured loggers' handlers
    rather than appending, so it never duplicates handlers or log lines.
    """
    formatter = "json" if settings.log_format == "json" else "console"
    dictConfig(
        {
            "version": 1,
            # Keep loggers created before this call (e.g. by imported libraries).
            "disable_existing_loggers": False,
            "formatters": {
                "console": {"format": CONSOLE_FORMAT},
                "json": {"()": f"{__name__}.JsonFormatter"},
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": formatter,
                },
            },
            "root": {"level": settings.log_level, "handlers": ["stdout"]},
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module logger; use ``get_logger(__name__)`` at module top."""
    return logging.getLogger(name)
