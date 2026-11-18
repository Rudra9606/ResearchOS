"""Structured application logging for ResearchOS."""

import logging
import json
import re
import sys
from datetime import datetime, timezone

from app.utils.request_context import request_id_context


_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*")
_SECRET_FIELD = re.compile(
    r"(?i)(\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*)([^\s,;]+)"
)


def _redact(value: str) -> str:
    value = _BEARER.sub(r"\1[REDACTED]", value)
    return _SECRET_FIELD.sub(r"\1[REDACTED]", value)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = _redact(record.getMessage())
        if record.exc_info:
            message = f"{message} ({record.exc_info[0].__name__})"
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_context.get(),
            "message": message,
        }, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    log_format: str | None = None,
) -> None:
    """Set up JSON logs with request correlation and basic secret redaction."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


# Initialize logging on import
setup_logging()
