from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
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


async def request_validation_error_handler(
    request: Request,
    exc: Exception,
) -> ORJSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = [
        {
            "location": [str(part) for part in error["loc"]],
            "message": error["msg"],
            "error_type": error["type"],
        }
        for error in exc.errors()
    ]
    return ORJSONResponse(
        status_code=422,
        content={
            "type": "https://api.macrolens.local/problems/request_validation_error",
            "title": "请求参数无效",
            "status": 422,
            "detail": "请求路径、查询参数或请求体未通过校验。",
            "instance": str(request.url.path),
            "code": "request_validation_error",
            "errors": errors,
        },
    )
