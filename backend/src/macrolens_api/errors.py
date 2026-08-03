from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import ORJSONResponse


@dataclass(slots=True)
class AppError(Exception):
    status_code: int
    title: str
    detail: str
    code: str = "application_error"
    extra: dict[str, Any] | None = None


async def app_error_handler(request: Request, exc: AppError) -> ORJSONResponse:
    body: dict[str, Any] = {
        "type": f"https://api.macrolens.local/problems/{exc.code}",
        "title": exc.title,
        "status": exc.status_code,
        "detail": exc.detail,
        "instance": str(request.url.path),
        "code": exc.code,
    }
    if exc.extra:
        body["extra"] = exc.extra
    return ORJSONResponse(status_code=exc.status_code, content=body)
