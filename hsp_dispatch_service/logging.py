import json
import logging
import logging.config
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_LOG_DIR = Path("/root/hsp/logs")
LOG_FILE_NAME = "hsp-dispatch-service.log"

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "set-cookie",
    "token",
    "x-api-key",
    "x-auth-token",
}


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload["fields"] = sanitize_log_value(fields)

        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_value),
                "traceback": "".join(traceback.format_exception(*record.exc_info)),
            }
            if exc_traceback is None:
                payload["exception"]["traceback"] = None

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(
    log_level: str,
    log_dir: Path | str = DEFAULT_LOG_DIR,
) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(build_json_log_config(log_level=log_level, log_dir=log_dir))


def build_json_log_config(
    log_level: str,
    log_dir: Path | str = DEFAULT_LOG_DIR,
) -> dict[str, Any]:
    resolved_log_dir = Path(log_dir)
    log_file = resolved_log_dir / LOG_FILE_NAME
    normalized_level = log_level.upper()

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "hsp_dispatch_service.logging.JsonLogFormatter",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": str(log_file),
                "maxBytes": 10485760,
                "backupCount": 10,
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": normalized_level,
            "handlers": ["default", "file"],
        },
        "loggers": {
            "grpc": {
                "level": normalized_level,
                "propagate": True,
            },
            "hsp_dispatch_service": {
                "level": normalized_level,
                "propagate": True,
            },
            "uvicorn": {
                "level": normalized_level,
                "propagate": True,
            },
            "uvicorn.access": {
                "level": normalized_level,
                "propagate": True,
            },
            "uvicorn.error": {
                "level": normalized_level,
                "propagate": True,
            },
        },
    }


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    logger.log(level, event, extra={"event": event, "fields": sanitize_log_value(fields)})


def sanitize_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _REDACTED if _is_sensitive_key(key) else sanitize_log_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple | set):
        return [sanitize_log_value(item) for item in value]
    return value


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower()
    return normalized in _SENSITIVE_KEYS or any(part in normalized for part in _SENSITIVE_KEYS)
