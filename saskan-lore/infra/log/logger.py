# saskan-lore/infra/log/logger.py
from __future__ import annotations

import json
import logging
import logging.config
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from logging import LogRecord
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """
    One JSON object per log line.
    Core fields: ts, level, logger, message.
    In development, adds module, func, and line for easier tracing.
    """

    def format(self, record: LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if os.getenv("APP_ENV", "development").lower() == "development":
            payload["module"] = record.module
            payload["func"] = record.funcName
            payload["line"] = record.lineno
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure(
    *,
    log_dir: Optional[str] = os.getenv("LOG_DIR"),
    log_level: str = os.getenv("LOG_LEVEL", "INFO"),
) -> None:
    """
    Call once at process start (CLI entrypoint or test session).

    Console output is always active.
    File output (rotating JSONL) is added when LOG_DIR is set.

    Both LOG_DIR and LOG_LEVEL are read from the environment by default;
    callers may override them explicitly.
    """
    handlers: dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "level": log_level,
            "formatter": "json",
        }
    }
    handler_names = ["console"]

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(log_dir, "saskan_lore.jsonl"),
            "maxBytes": 5 * 1024 * 1024,  # 5 MB per file
            "backupCount": 3,
            "encoding": "utf-8",
            "level": log_level,
            "formatter": "json",
        }
        handler_names.append("file")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {"()": f"{__name__}.JSONFormatter"},
            },
            "handlers": handlers,
            "root": {
                "level": log_level,
                "handlers": handler_names,
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger. Typical use:

        from saskan_lore.infra.log.logger import get_logger
        log = get_logger(__name__)
    """
    return logging.getLogger(name)
