from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..db import get_engine
from ..errors import AppError
from ..schemas import HealthResponse

router = APIRouter(tags=["System"])


def _response() -> HealthResponse:
    return HealthResponse(time=datetime.now(UTC), version="1.0.2")


async def _database_ready() -> None:
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))


@router.get("/health", response_model=HealthResponse)
@router.get("/live", response_model=HealthResponse, include_in_schema=False)
async def live() -> HealthResponse:
    """Process liveness probe independent from PostgreSQL and external providers."""

    return _response()


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    """Readiness probe that verifies the API can reach its primary database."""

    try:
        await _database_ready()
    except (SQLAlchemyError, OSError, ImportError) as exc:
        raise AppError(
            503,
            "服务尚未就绪",
            "数据库连接暂时不可用，请稍后重试。",
            "database_unavailable",
        ) from exc
    return _response()
