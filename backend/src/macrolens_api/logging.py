from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import UTC, datetime
from typing import Any


class JsonLogger:
    """Small structured logger that keeps the runtime dependency surface minimal."""

    def __init__(self, name: str = "macrolens") -> None:
        self._logger = logging.getLogger(name)

    def _emit(self, level: int, event: str, *, exc_info: bool = False, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": logging.getLevelName(level).lower(),
            "event": event,
            **fields,
        }
        if exc_info:
            payload["exception"] = traceback.format_exc()
        self._logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))

    def debug(self, event: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, **fields)

    def exception(self, event: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, exc_info=True, **fields)


def configure_logging(level: str) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper(), force=True)


def get_logger(name: str = "macrolens") -> JsonLogger:
    return JsonLogger(name)
